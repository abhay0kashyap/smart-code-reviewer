from __future__ import annotations

import ast
import re
from typing import Any, Dict, Optional

from .llm_fix import try_llama_cpp_fix, try_ollama_fix


FIXABLE_ERROR_TYPES = {
    "SyntaxError",
    "IndentationError",
    "TabError",
    "NameError",
}


def _replace_line(code: str, line_number: int, new_line: str) -> str:
    lines = code.splitlines()
    if line_number < 1 or line_number > len(lines):
        return code
    lines[line_number - 1] = new_line
    return "\n".join(lines)


def _extract_error_line(execution: Dict[str, Any]) -> Optional[int]:
    if execution.get("error_line"):
        return int(execution["error_line"])

    traceback_text = str(execution.get("traceback") or "")
    matches = re.findall(r"line\s+(\d+)", traceback_text)
    if matches:
        return int(matches[-1])

    return None


def _has_valid_ast(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _fix_missing_quote(line: str) -> Optional[str]:
    single_quotes = line.count("'")
    double_quotes = line.count('"')

    if single_quotes % 2 == 1 and double_quotes % 2 == 0:
        if line.rstrip().endswith(")"):
            return f"{line[:-1]}'" + ")"
        return f"{line}'"

    if double_quotes % 2 == 1 and single_quotes % 2 == 0:
        if line.rstrip().endswith(")"):
            return f'{line[:-1]}"' + ")"
        return f'{line}"'

    return None


def _fix_name_error(code: str, error_message: str) -> Optional[tuple[str, str]]:
    match = re.search(r"name '(.+?)' is not defined", error_message)
    if not match:
        return None

    missing_name = match.group(1)
    token_pattern = rf"(?<!['\"])\b{re.escape(missing_name)}\b(?!['\"])"

    lines = code.splitlines()
    for index, line in enumerate(lines, start=1):
        if re.search(rf"\b{re.escape(missing_name)}\b\s*=", line):
            continue
        candidate_line = re.sub(token_pattern, f'"{missing_name}"', line, count=1)
        if candidate_line != line:
            fixed_code = _replace_line(code, index, candidate_line)
            return fixed_code, candidate_line
    return None


def deterministic_fix(code: str, execution: Dict[str, Any]) -> Dict[str, Any]:
    original_code = "" if code is None else str(code)
    error_type = str(execution.get("error_type") or "ExecutionError")
    error_message = str(execution.get("error_message") or "")
    error_line = _extract_error_line(execution)

    if error_type not in FIXABLE_ERROR_TYPES:
        return {
            "fix_available": False,
            "fixed_code": original_code,
            "correct_line": None,
            "reason": f"No deterministic rule for {error_type}.",
        }

    lines = original_code.splitlines()
    target_line = lines[error_line - 1] if error_line and 1 <= error_line <= len(lines) else ""

    candidates: list[tuple[str, str, str]] = []

    if error_line and target_line:
        stripped = target_line.strip()

        if stripped.endswith(";"):
            fixed_line = target_line.rstrip(";") + ":"
            candidates.append((
                _replace_line(original_code, error_line, fixed_line),
                fixed_line,
                "Replaced trailing ';' with ':' in a control statement.",
            ))

        if ",/)" in target_line:
            fixed_line = target_line.replace(",/)", ")")
            candidates.append((
                _replace_line(original_code, error_line, fixed_line),
                fixed_line,
                "Removed invalid punctuation ',/)' from print/function call.",
            ))

        missing_quote_line = _fix_missing_quote(target_line)
        if missing_quote_line:
            candidates.append((
                _replace_line(original_code, error_line, missing_quote_line),
                missing_quote_line,
                "Added missing closing quote.",
            ))

    if error_type == "NameError":
        name_fix = _fix_name_error(original_code, error_message)
        if name_fix:
            fixed_code, fixed_line = name_fix
            candidates.append((fixed_code, fixed_line, "Wrapped undefined name in quotes as likely string literal."))

    for fixed_code, correct_line, reason in candidates:
        if fixed_code.strip() == original_code.strip():
            continue

        # AST validation keeps deterministic changes syntax-safe.
        if _has_valid_ast(fixed_code):
            return {
                "fix_available": True,
                "fixed_code": fixed_code,
                "correct_line": correct_line,
                "reason": reason,
            }

    return {
        "fix_available": False,
        "fixed_code": original_code,
        "correct_line": None,
        "reason": "No safe deterministic fix could be applied.",
    }


def ai_fix_with_local_model(code: str, execution: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic first, then optional local models (Ollama -> llama-cpp)."""
    original_code = "" if code is None else str(code)

    deterministic = deterministic_fix(original_code, execution)
    if deterministic["fix_available"]:
        return {
            "fix_available": True,
            "fixed_code": deterministic["fixed_code"],
            "correct_line": deterministic["correct_line"],
            "reason": deterministic["reason"],
            "changed_lines": [],
            "source": "deterministic",
        }

    error_text = str(execution.get("traceback") or execution.get("error_message") or "")

    ollama_result = try_ollama_fix(original_code, error_text)
    if ollama_result["ok"] and ollama_result["fixed_code"].strip() != original_code.strip():
        return {
            "fix_available": True,
            "fixed_code": ollama_result["fixed_code"],
            "correct_line": None,
            "reason": ollama_result["reason"],
            "changed_lines": ollama_result["changed_lines"],
            "source": "ollama",
        }

    llama_cpp_result = try_llama_cpp_fix(original_code, error_text)
    if llama_cpp_result["ok"] and llama_cpp_result["fixed_code"].strip() != original_code.strip():
        return {
            "fix_available": True,
            "fixed_code": llama_cpp_result["fixed_code"],
            "correct_line": None,
            "reason": llama_cpp_result["reason"],
            "changed_lines": llama_cpp_result["changed_lines"],
            "source": "llama_cpp",
        }

    return {
        "fix_available": False,
        "fixed_code": original_code,
        "correct_line": None,
        "reason": (
            "No deterministic fix available. "
            "Local AI model unavailable or did not produce a valid correction."
        ),
        "changed_lines": [],
        "source": "none",
    }


def generate_fixed_code(code: str, execution: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility wrapper for older callers."""
    result = ai_fix_with_local_model(code, execution)
    return {
        "success": result["fix_available"],
        "fixed_code": result["fixed_code"],
        "source": result["source"],
        "error": None if result["fix_available"] else result["reason"],
        "ollama_error": None,
    }
