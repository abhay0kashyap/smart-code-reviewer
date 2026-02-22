from __future__ import annotations

import ast
import re

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def _clean_fixed_code(text: str) -> str:
    cleaned = (text or "").strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = max(fenced, key=len).strip()
    cleaned = re.sub(r"^python\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _is_valid_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _fallback_fix(code: str, error: str) -> str:
    lines = code.splitlines()
    if not lines:
        return code

    # Fix common punctuation mistake: print("hi",/)
    repaired = code.replace(",/)", ")")
    if repaired != code and _is_valid_python(repaired):
        return repaired

    # Fix trailing semicolon in simple control line
    repaired_lines = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped.endswith(";") and stripped.startswith(("if ", "for ", "while ", "def ", "elif ", "else")):
            repaired_lines.append(line.rstrip(";") + ":")
            changed = True
        else:
            repaired_lines.append(line)
    if changed:
        candidate = "\n".join(repaired_lines)
        if _is_valid_python(candidate):
            return candidate

    # Fix missing closing quote on the error line when possible
    error_line_match = re.findall(r"line\s+(\d+)", error or "")
    if error_line_match:
        idx = int(error_line_match[-1]) - 1
        if 0 <= idx < len(lines):
            line = lines[idx]
            single_quotes = line.count("'")
            double_quotes = line.count('"')

            if single_quotes % 2 == 1 and double_quotes % 2 == 0:
                if line.rstrip().endswith(")"):
                    lines[idx] = line[:-1] + "'" + ")"
                else:
                    lines[idx] = line + "'"
                candidate = "\n".join(lines)
                if _is_valid_python(candidate):
                    return candidate
                lines[idx] = line

            if double_quotes % 2 == 1 and single_quotes % 2 == 0:
                if line.rstrip().endswith(")"):
                    lines[idx] = line[:-1] + '"' + ")"
                else:
                    lines[idx] = line + '"'
                candidate = "\n".join(lines)
                if _is_valid_python(candidate):
                    return candidate
                lines[idx] = line

    return code


def ai_fix_code(code, error):
    prompt = f"""You are an expert Python developer.
Fix the following Python code completely.

Return ONLY the corrected full code.

Code:
{code}

Error:
{error}"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "deepseek-coder",
                "prompt": prompt,
                "stream": False,
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        fixed_code = _clean_fixed_code(str(payload.get("response") or ""))
    except Exception:
        fixed_code = ""

    if fixed_code.strip() and fixed_code.strip() != str(code).strip():
        return fixed_code

    return _fallback_fix(str(code), str(error))
