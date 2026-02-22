from __future__ import annotations

import re
from typing import Any, Dict, Optional

import requests

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT_SECONDS = 45


def _looks_like_code_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    code_prefixes = (
        "import ",
        "from ",
        "def ",
        "class ",
        "if ",
        "elif ",
        "else:",
        "for ",
        "while ",
        "try:",
        "except",
        "with ",
        "return ",
        "print(",
        "raise ",
    )

    return (
        stripped.startswith(code_prefixes)
        or "=" in stripped
        or stripped.endswith(":")
        or stripped.endswith(")")
        or stripped in {"pass", "break", "continue"}
    )


def _extract_python_code(text: str) -> str:
    if not text:
        return ""

    cleaned = text.strip()
    fenced_blocks = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced_blocks:
        cleaned = max(fenced_blocks, key=len).strip()

    lines = cleaned.splitlines()
    if not lines:
        return ""

    start_index = 0
    for index, line in enumerate(lines):
        if _looks_like_code_line(line):
            start_index = index
            break

    code_candidate = "\n".join(lines[start_index:]).strip()
    code_candidate = re.sub(r"^python\s*", "", code_candidate, flags=re.IGNORECASE)
    return code_candidate.strip()


def _request_ollama(prompt: str, model: str) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {
            "success": False,
            "error": f"Could not connect to Ollama at {OLLAMA_GENERATE_URL}: {exc}",
            "response_text": "",
        }

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"Ollama returned HTTP {response.status_code}: {response.text[:300]}",
            "response_text": "",
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "success": False,
            "error": "Ollama returned non-JSON response.",
            "response_text": response.text,
        }

    response_text = str(data.get("response", "") or "")
    if not response_text.strip():
        return {
            "success": False,
            "error": "Ollama returned an empty response.",
            "response_text": "",
        }

    return {"success": True, "error": None, "response_text": response_text}


def _error_line_from_execution(execution: Dict[str, Any]) -> Optional[int]:
    if execution.get("error_line"):
        return int(execution["error_line"])

    traceback_text = str(execution.get("traceback", "") or "")
    matches = re.findall(r"line\s+(\d+)", traceback_text)
    if matches:
        return int(matches[-1])

    return None


def _replace_line(code: str, line_number: int, replacement: str) -> str:
    lines = code.splitlines()
    if line_number < 1 or line_number > len(lines):
        return code
    lines[line_number - 1] = replacement
    return "\n".join(lines)


def _rule_based_fix(code: str, execution: Dict[str, Any]) -> str:
    error_type = str(execution.get("error_type") or "")
    error_message = str(execution.get("error_message") or "")
    error_line = _error_line_from_execution(execution)

    lines = code.splitlines()
    target_line = lines[error_line - 1] if error_line and 1 <= error_line <= len(lines) else ""
    stripped_target = target_line.strip()

    if error_type == "SyntaxError" and error_line:
        if stripped_target.endswith(";"):
            return _replace_line(code, error_line, target_line.rstrip(";") + ":")

        if stripped_target.startswith(("if ", "for ", "while ", "def ", "elif ", "else")) and not stripped_target.endswith(":"):
            return _replace_line(code, error_line, target_line + ":")

        if stripped_target.startswith(("if ", "while ")) and " = " in stripped_target and "==" not in stripped_target:
            return _replace_line(code, error_line, target_line.replace(" = ", " == ", 1))

    if error_type in {"IndentationError", "TabError"}:
        return code.replace("\t", "    ")

    if error_type == "NameError":
        match = re.search(r"name '(.+?)' is not defined", error_message)
        if match:
            missing_name = match.group(1)
            token_pattern = rf"(?<!['\"])\b{re.escape(missing_name)}\b(?!['\"])"
            for index, line in enumerate(lines, start=1):
                if re.search(rf"\b{re.escape(missing_name)}\b\s*=", line):
                    continue
                candidate = re.sub(token_pattern, f'"{missing_name}"', line, count=1)
                if candidate != line:
                    return _replace_line(code, index, candidate)

    if error_type == "TypeError" and error_line and target_line:
        if "concatenate str" in error_message or "unsupported operand type(s) for +" in error_message:
            rewritten = re.sub(r"\+\s*([A-Za-z_]\w*)", r"+ str(\1)", target_line, count=1)
            if rewritten != target_line:
                return _replace_line(code, error_line, rewritten)

        if "object is not callable" in error_message:
            rewritten = re.sub(r"\b([A-Za-z_]\w*)\((\d+)\)", r"\1[\2]", target_line, count=1)
            if rewritten != target_line:
                return _replace_line(code, error_line, rewritten)

    if error_type == "IndexError" and error_line and target_line:
        rewritten = re.sub(
            r"\b([A-Za-z_]\w*)\[(\d+)\]",
            lambda m: f"({m.group(1)}[{m.group(2)}] if len({m.group(1)}) > {m.group(2)} else None)",
            target_line,
            count=1,
        )
        if rewritten != target_line:
            return _replace_line(code, error_line, rewritten)

    if error_type == "KeyError" and error_line and target_line:
        rewritten = re.sub(r"([A-Za-z_]\w*)\[(\"[^\"]+\"|'[^']+')\]", r"\1.get(\2)", target_line, count=1)
        if rewritten != target_line:
            return _replace_line(code, error_line, rewritten)

    if error_type == "AttributeError" and error_line and target_line:
        if ".add(" in target_line and "list" in error_message:
            rewritten = target_line.replace(".add(", ".append(", 1)
            return _replace_line(code, error_line, rewritten)

    if error_type == "ZeroDivisionError" and error_line and target_line:
        rewritten = target_line.replace("/ 0", "/ 1")
        if rewritten != target_line:
            return _replace_line(code, error_line, rewritten)

    return code


def _build_fix_prompt(code: str, execution: Dict[str, Any]) -> str:
    error_type = execution.get("error_type") or "ExecutionError"
    error_message = execution.get("error_message") or "Unknown error"
    traceback_text = execution.get("traceback") or ""

    return f"""
You are a precise Python code repair engine.
Return ONLY valid corrected Python code.
Do not include explanations, markdown, or comments.

Requirements:
1. Preserve the user's intent.
2. Fix syntax and runtime errors.
3. Keep output behavior sensible for beginners.
4. Return complete runnable code.

Python code:
{code}

Error type:
{error_type}

Error message:
{error_message}

Traceback:
{traceback_text}
""".strip()


def generate_fixed_code(
    code: str,
    execution: Dict[str, Any],
    model: str = "llama3",
    use_ollama: bool = True,
) -> Dict[str, Any]:
    """Generate fixed code using Ollama first, then deterministic fallback."""
    original_code = "" if code is None else str(code)
    ollama_error = None

    if use_ollama:
        prompt = _build_fix_prompt(original_code, execution)
        ollama_result = _request_ollama(prompt=prompt, model=model)

        if ollama_result["success"]:
            candidate = _extract_python_code(ollama_result["response_text"])
            if candidate.strip() and candidate.strip() != original_code.strip():
                return {
                    "success": True,
                    "fixed_code": candidate,
                    "source": "ollama",
                    "model": model,
                    "error": None,
                    "ollama_error": None,
                }
            ollama_error = "Ollama returned code but no meaningful changes were produced."
        else:
            ollama_error = ollama_result["error"]

    fallback_code = _rule_based_fix(original_code, execution)
    if fallback_code.strip() != original_code.strip():
        return {
            "success": True,
            "fixed_code": fallback_code,
            "source": "rule_based",
            "model": model,
            "error": None,
            "ollama_error": ollama_error,
        }

    return {
        "success": False,
        "fixed_code": original_code,
        "source": "none",
        "model": model,
        "error": ollama_error or "No automatic fix could be generated.",
        "ollama_error": ollama_error,
    }
