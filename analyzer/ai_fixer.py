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


def _line_index(code: str, one_based_line: Optional[int]) -> int:
    lines = code.splitlines()
    if not lines:
        return -1
    if one_based_line and 1 <= one_based_line <= len(lines):
        return one_based_line - 1
    return 0


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
    error_message = str(execution.get("error_message") or execution.get("traceback") or "")
    error_blob = f"{error_type} {error_message}".lower()

    line_idx = _line_index(code, execution.get("error_line"))
    if line_idx < 0:
        return result

    target = lines[line_idx]
    updated = target
    reason = ""

    # Common beginner typo: print("hi",/)
    candidate = re.sub(r"print\(([^\n)]*?),/\)", r"print(\1)", updated)
    if candidate != updated:
        updated = candidate
        reason = "Removed invalid '/)' punctuation in print call."

    # Common typo: block opener ends with ';' instead of ':'
    block_pattern = r"^(\s*(?:if|elif|else|for|while|try|except|finally|with|def|class)\b.*?);(\s*)$"
    candidate = re.sub(block_pattern, r"\1:\2", updated)
    if candidate != updated:
        updated = candidate
        reason = "Replaced trailing semicolon with colon for Python block syntax."

    # Fix odd quote count on the errored line for unterminated strings.
    if "unterminated string" in error_blob or "eol while scanning string literal" in error_blob:
        for quote in ("'", '"'):
            if updated.count(quote) % 2 == 1:
                updated = f"{updated}{quote}"
                reason = "Closed unterminated string literal."
                break

    # Another common typo: stray slash before ')'.
    candidate = re.sub(r"/\)", ")", updated)
    if candidate != updated and not reason:
        updated = candidate
        reason = "Removed stray slash before closing parenthesis."

    # Missing colon on control/class/def lines.
    if (
        "syntaxerror" in error_blob
        and re.match(r"\s*(if|elif|else|for|while|try|except|finally|with|def|class)\b", updated)
        and not updated.rstrip().endswith(":")
    ):
        updated = f"{updated.rstrip()}:"
        reason = "Added missing colon at end of Python block statement."

    if updated == target:
        return result

    lines[line_idx] = updated
    fixed_code = "\n".join(lines)

    return {
        "fix_available": True,
        "fixed_code": fixed_code,
        "correct_line": updated,
        "reason": reason or "Applied deterministic syntax correction.",
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


def ai_fix_code(code: str, error: str) -> str:
    if not code or not str(code).strip():
        return ""

    prompt = _build_prompt(str(code), str(error or ""))

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

    fallback = deterministic_fix(
        str(code),
        {
            "error_type": "SyntaxError",
            "error_message": str(error or ""),
            "traceback": str(error or ""),
            "error_line": None,
        },
    )
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
    ai_code = ai_fix_code(code, error_text)
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
