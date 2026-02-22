import re

import requests


def _extract_code(text: str) -> str:
    """Return plain python code from model output, handling fenced blocks."""
    if not text:
        return ""

    fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    return text.strip()


def _extract_traceback_line(error: str) -> int | None:
    matches = re.findall(r"line\s+(\d+)", error or "")
    if not matches:
        return None
    return int(matches[-1])


def _replace_line(code: str, line_number: int, new_line: str) -> str:
    lines = code.splitlines()
    if not line_number or line_number < 1 or line_number > len(lines):
        return code
    lines[line_number - 1] = new_line
    return "\n".join(lines)


def _rule_based_fix(code: str, error: str, error_type: str) -> str:
    lines = code.splitlines()
    line_number = _extract_traceback_line(error)

    if error_type == "SyntaxError":
        if line_number and 1 <= line_number <= len(lines):
            current_line = lines[line_number - 1]
            stripped = current_line.strip()

            if stripped.endswith(";"):
                fixed_line = current_line.rstrip(";") + ":"
                return _replace_line(code, line_number, fixed_line)

            if stripped.startswith(("if ", "for ", "while ", "def ", "elif ", "else")) and not stripped.endswith(":"):
                fixed_line = current_line + ":"
                return _replace_line(code, line_number, fixed_line)

            if stripped.startswith(("if ", "while ")) and " = " in stripped and "==" not in stripped:
                fixed_line = current_line.replace(" = ", " == ", 1)
                return _replace_line(code, line_number, fixed_line)

    if error_type == "IndentationError":
        if line_number and 1 <= line_number <= len(lines):
            line = lines[line_number - 1]
            if line and not line.startswith((" ", "\t")) and line_number > 1:
                prev = lines[line_number - 2].rstrip()
                if prev.endswith(":"):
                    return _replace_line(code, line_number, "    " + line)

    if error_type == "TabError":
        return code.replace("\t", "    ")

    if error_type == "NameError":
        match = re.search(r"name '(.+?)' is not defined", error or "")
        if match:
            name = match.group(1)
            token_pattern = rf"(?<!['\"])\b{re.escape(name)}\b(?!['\"])"

            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                if re.search(rf"\b{re.escape(name)}\b\s*=", line):
                    continue
                if stripped.startswith(("def ", "class ", "import ", "from ")):
                    continue
                if re.search(token_pattern, line):
                    fixed_line = re.sub(token_pattern, f'"{name}"', line, count=1)
                    return _replace_line(code, i, fixed_line)

    if error_type == "KeyError":
        if line_number and 1 <= line_number <= len(lines):
            line = lines[line_number - 1]
            # dict["missing"] -> dict.get("missing")
            fixed_line = re.sub(
                r"([A-Za-z_]\w*)\[(\"[^\"]+\"|'[^']+')\]",
                r"\1.get(\2)",
                line,
                count=1,
            )
            if fixed_line != line:
                return _replace_line(code, line_number, fixed_line)

            # dict[key] -> dict.get(key)
            fixed_line = re.sub(
                r"([A-Za-z_]\w*)\[([A-Za-z_]\w*)\]",
                r"\1.get(\2)",
                line,
                count=1,
            )
            if fixed_line != line:
                return _replace_line(code, line_number, fixed_line)

    if error_type == "IndexError":
        if line_number and 1 <= line_number <= len(lines):
            line = lines[line_number - 1]
            # arr[10] -> (arr[10] if len(arr) > 10 else None)
            fixed_line = re.sub(
                r"\b([A-Za-z_]\w*)\[(\d+)\]",
                lambda m: f"({m.group(1)}[{m.group(2)}] if len({m.group(1)}) > {m.group(2)} else None)",
                line,
                count=1,
            )
            if fixed_line != line:
                return _replace_line(code, line_number, fixed_line)

            # arr[i] -> (arr[i] if 0 <= i < len(arr) else None)
            fixed_line = re.sub(
                r"\b([A-Za-z_]\w*)\[([A-Za-z_]\w*)\]",
                lambda m: f"({m.group(1)}[{m.group(2)}] if 0 <= {m.group(2)} < len({m.group(1)}) else None)",
                line,
                count=1,
            )
            if fixed_line != line:
                return _replace_line(code, line_number, fixed_line)

    if error_type == "TypeError":
        if line_number and 1 <= line_number <= len(lines):
            line = lines[line_number - 1]
            msg = error or ""

            # "can only concatenate str ..." -> cast right side variable to str
            if "concatenate str" in msg or "unsupported operand type(s) for +: 'str'" in msg:
                fixed_line = re.sub(r"\+\s*([A-Za-z_]\w*)", r"+ str(\1)", line, count=1)
                if fixed_line != line:
                    return _replace_line(code, line_number, fixed_line)

            # unsupported numeric operations where one side is str
            if "unsupported operand type(s)" in msg and "'str'" in msg:
                fixed_line = re.sub(r"([A-Za-z_]\w*)\s*([\-\*/%])\s*([A-Za-z_]\w*)", r"float(\1) \2 float(\3)", line, count=1)
                if fixed_line != line:
                    return _replace_line(code, line_number, fixed_line)

            # "'list' object is not callable" -> use indexing for single integer arg
            if "object is not callable" in msg:
                fixed_line = re.sub(r"\b([A-Za-z_]\w*)\((\d+)\)", r"\1[\2]", line, count=1)
                if fixed_line != line:
                    return _replace_line(code, line_number, fixed_line)

            # "'int' object is not subscriptable" -> convert to str before indexing
            if "object is not subscriptable" in msg:
                fixed_line = re.sub(r"\b([A-Za-z_]\w*)\[(\d+)\]", r"str(\1)[\2]", line, count=1)
                if fixed_line != line:
                    return _replace_line(code, line_number, fixed_line)

    return code


def ai_fix_with_ollama(code: str, error: str, error_type: str = "", model: str = "phi3") -> str:
    prompt = f"""
You are an expert Python debugger.
Fix the code so it runs successfully.

Code:
{code}

Error type:
{error_type}

Error details:
{error}

Return only corrected Python code.
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=6,
    )
    response.raise_for_status()

    payload = response.json()
    raw_text = payload.get("response", "")
    return _extract_code(raw_text)


def ai_fix_code(
    code: str,
    error: str,
    error_type: str = "",
    model: str = "phi3",
    enable_ollama: bool = True,
) -> dict:
    """Try LLM fix first, then deterministic fallback if LLM is unavailable."""
    if enable_ollama:
        try:
            llm_fixed = ai_fix_with_ollama(code, error, error_type, model=model)
            if llm_fixed and llm_fixed.strip() != code.strip():
                return {"fixed_code": llm_fixed, "source": "ollama", "llm_error": None}
        except Exception as exc:
            llm_error = str(exc)
        else:
            llm_error = None
    else:
        llm_error = None

    fallback_fixed = _rule_based_fix(code, error, error_type)
    source = "rule_based" if fallback_fixed.strip() != code.strip() else "none"
    return {"fixed_code": fallback_fixed, "source": source, "llm_error": llm_error}
