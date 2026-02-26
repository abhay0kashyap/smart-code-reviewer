from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

try:
    from google import genai
except Exception:  # pragma: no cover
    genai = None  # type: ignore

LOGGER = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-2.0-flash"


def clean_code(text: str) -> str:
    cleaned = (text or "").strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = max(fenced, key=len).strip()
    return cleaned.strip()


def _extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    fragments = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text:
                fragments.append(part_text)

    return "\n".join(fragments).strip()


def _extract_error_line_from_text(error_text: str) -> Optional[int]:
    if not error_text:
        return None

    local_file_matches = re.findall(r'File ".*?main\\.py", line (\d+)', error_text)
    if local_file_matches:
        return int(local_file_matches[-1])

    generic_matches = re.findall(r"line\s+(\d+)", error_text)
    if generic_matches:
        return int(generic_matches[-1])

    return None


def _line_index(code: str, one_based_line: Optional[int]) -> int:
    lines = code.splitlines()
    if not lines:
        return -1
    if one_based_line and 1 <= one_based_line <= len(lines):
        return one_based_line - 1
    return 0


def _extract_name_error_identifier(error_blob: str) -> str:
    match = re.search(r"name\s+'([A-Za-z_][A-Za-z0-9_]*)'\s+is\s+not\s+defined", error_blob)
    return match.group(1) if match else ""


def _extract_key_error_key(error_blob: str) -> str:
    match = re.search(r"KeyError:\s*['\"]?([^'\"\n]+)['\"]?", error_blob)
    return match.group(1) if match else ""


def deterministic_fix(code: str, execution: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "fix_available": False,
        "fixed_code": code,
        "correct_line": "",
        "reason": "No deterministic fix available.",
    }

    if not code or not str(code).strip():
        return result

    lines = str(code).splitlines()
    if not lines:
        return result

    error_type = str(execution.get("error_type") or "")
    error_message = str(execution.get("error_message") or "")
    traceback_text = str(execution.get("traceback") or "")
    error_blob = f"{error_type}\n{error_message}\n{traceback_text}"
    error_blob_lower = error_blob.lower()

    changed = False
    reason = ""

    block_pattern = r"^(\s*(?:if|elif|else|for|while|try|except|finally|with|def|class)\b.*?);(\s*)$"
    for idx, line in enumerate(lines):
        updated = line
        updated = re.sub(r"print\(([^\n)]*?),/\)", r"print(\1)", updated)
        updated = re.sub(r"/\)", ")", updated)
        updated = re.sub(block_pattern, r"\1:\2", updated)
        if updated != line:
            lines[idx] = updated
            changed = True
            if not reason:
                reason = "Applied punctuation and block-syntax corrections."

    error_line = execution.get("error_line")
    if not isinstance(error_line, int):
        error_line = _extract_error_line_from_text(error_blob)
    line_idx = _line_index(code, error_line)

    if line_idx >= 0:
        target = lines[line_idx]
        updated = target

        # Unterminated strings.
        if "unterminated string" in error_blob_lower or "eol while scanning string literal" in error_blob_lower:
            for quote in ("'", '"'):
                if updated.count(quote) % 2 == 1:
                    trimmed = updated.rstrip()
                    if trimmed.endswith(")"):
                        closing_index = updated.rfind(")")
                        if closing_index >= 0:
                            updated = f"{updated[:closing_index]}{quote}{updated[closing_index:]}"
                        else:
                            updated = f"{updated}{quote}"
                    else:
                        updated = f"{updated}{quote}"
                    reason = "Closed unterminated string literal."
                    break

        # NameError for beginner print variables, e.g. print(hello) -> print("hello")
        missing_name = _extract_name_error_identifier(error_blob)
        if missing_name and "nameerror" in error_blob_lower and "print(" in updated:
            safe_word = re.escape(missing_name)
            candidate = re.sub(
                rf"(?<!['\"\.])\b{safe_word}\b(?!['\"])",
                f'"{missing_name}"',
                updated,
            )
            if candidate != updated:
                updated = candidate
                reason = "Converted undefined print token to a string literal."

        # IndexError: replace direct list indexing with a safe conditional expression.
        if "indexerror" in error_blob_lower:
            index_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]", updated)
            if index_match:
                var_name = index_match.group(1)
                index_value = int(index_match.group(2))
                safe_expr = f"({var_name}[{index_value}] if len({var_name}) > {index_value} else None)"
                updated = re.sub(
                    rf"\b{re.escape(var_name)}\[{index_value}\]",
                    safe_expr,
                    updated,
                    count=1,
                )
                reason = "Guarded list indexing to avoid out-of-range access."

        # KeyError: dictionary direct access -> .get(key)
        if "keyerror" in error_blob_lower:
            missing_key = _extract_key_error_key(error_blob)
            if missing_key:
                key_access = rf"\[\s*(['\"])%s\1\s*\]" % re.escape(missing_key)
                if re.search(key_access, updated):
                    updated = re.sub(key_access, f'.get("{missing_key}")', updated)
                    reason = "Replaced dictionary key access with .get() for missing keys."

        # AttributeError: common list typo add -> append
        if "attributeerror" in error_blob_lower and ".add(" in updated:
            updated = updated.replace(".add(", ".append(")
            reason = "Replaced list .add() with .append()."

        if updated != target:
            lines[line_idx] = updated
            changed = True

    if not changed:
        return result

    fixed_code = "\n".join(lines)
    return {
        "fix_available": True,
        "fixed_code": fixed_code,
        "correct_line": lines[line_idx] if line_idx >= 0 else "",
        "reason": reason or "Applied deterministic correction.",
    }


def _build_prompt(code: str, error: str) -> str:
    return f"""
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
""".strip()


def ai_fix_code(code: str, error: str, execution: Optional[Dict[str, Any]] = None) -> str:
    if not code or not str(code).strip():
        return ""

    error_text = str(error or "")
    prompt = _build_prompt(str(code), error_text)

    execution_context: Dict[str, Any]
    if execution and isinstance(execution, dict):
        execution_context = {
            "error_type": str(execution.get("error_type") or ""),
            "error_message": str(execution.get("error_message") or error_text),
            "traceback": str(execution.get("traceback") or error_text),
            "error_line": execution.get("error_line"),
        }
    else:
        execution_context = {
            "error_type": "",
            "error_message": error_text,
            "traceback": error_text,
            "error_line": _extract_error_line_from_text(error_text),
        }

    if genai is not None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            LOGGER.warning("GEMINI_API_KEY is not set. Falling back to deterministic fixer.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                LOGGER.info("Gemini response object: %r", response)
                raw = _extract_response_text(response)
                LOGGER.info("Gemini raw response length: %d", len(raw))
                fixed_code = clean_code(raw)
                LOGGER.info("Gemini response: %s", fixed_code)

                if fixed_code and fixed_code.strip():
                    return fixed_code
                LOGGER.warning("Gemini returned an empty fix response.")
            except Exception as exc:  # pragma: no cover - network/provider failures
                LOGGER.exception("Gemini error: %s", exc)
    else:
        LOGGER.warning("google-genai package is not installed. Falling back to deterministic fixer.")

    fallback = deterministic_fix(str(code), execution_context)
    if fallback.get("fix_available"):
        return str(fallback.get("fixed_code") or "")
    return ""


def generate_fixed_code(
    code: str,
    execution: Dict[str, Any],
    model: str = GEMINI_MODEL,
    use_ollama: bool = False,
) -> Dict[str, Any]:
    _ = model
    _ = use_ollama

    deterministic = deterministic_fix(code, execution)
    if deterministic["fix_available"]:
        return {
            "fixed_code": deterministic["fixed_code"],
            "source": "deterministic",
            "error": None,
            "reason": deterministic["reason"],
        }

    error_text = str(execution.get("traceback") or execution.get("error_message") or "")
    ai_code = ai_fix_code(code, error_text, execution=execution)
    if ai_code and ai_code.strip() and ai_code.strip() != code.strip():
        return {
            "fixed_code": ai_code,
            "source": "gemini",
            "error": None,
            "reason": "Generated by Gemini.",
        }

    return {
        "fixed_code": code,
        "source": "none",
        "error": "No automatic fix generated.",
        "reason": "No deterministic or Gemini fix available.",
    }
