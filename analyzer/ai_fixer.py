from __future__ import annotations

import re
from typing import Any, Dict, Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT_SECONDS = 90


def _strip_markdown_fences(text: str) -> str:
    if not text:
        return ""

    cleaned = text.strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = max(fenced, key=len).strip()

    cleaned = re.sub(r"^python\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def ai_fix_with_ollama(code, error):
    import requests
    import json

    prompt = f"""
You are an expert Python debugger.

Your job is to FIX the user's Python code.

IMPORTANT RULES:

1. You MUST return ONLY corrected FULL Python code
2. DO NOT explain anything
3. DO NOT return original code if it has errors
4. ALWAYS fix syntax, logic, indentation, and runtime errors
5. The output code MUST run successfully in Python
6. DO NOT include markdown
7. DO NOT include ```python
8. RETURN ONLY PURE PYTHON CODE

USER CODE:
{code}

ERROR:
{error}

NOW RETURN THE FULL FIXED CODE:
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "top_p": 1
            }
        },
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    result = response.json()["response"].strip()

    return _strip_markdown_fences(result)


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

        if "/)" in target_line:
            return _replace_line(code, error_line, target_line.replace("/)", ")"))

        if stripped_target.endswith("/"):
            return _replace_line(code, error_line, target_line.rstrip("/"))

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


def generate_fixed_code(
    code: str,
    execution: Dict[str, Any],
    model: str = "llama3",
    use_ollama: bool = True,
) -> Dict[str, Any]:
    """Generate fixed code using strict Ollama prompt, then deterministic fallback."""
    original_code = "" if code is None else str(code)
    error_text = str(execution.get("traceback") or execution.get("error_message") or "")
    ollama_error = None

    if use_ollama:
        try:
            ai_fixed_code = ai_fix_with_ollama(original_code, error_text)
            if ai_fixed_code and ai_fixed_code.strip() != original_code.strip():
                return {
                    "success": True,
                    "fixed_code": ai_fixed_code,
                    "source": "ollama",
                    "model": model,
                    "error": None,
                    "ollama_error": None,
                }
            ollama_error = "Ollama returned unchanged code."
        except Exception as exc:
            ollama_error = str(exc)

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
