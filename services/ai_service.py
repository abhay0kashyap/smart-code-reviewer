from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Dict, Optional

from analyzer.ai_fixer import ai_assist, ai_fix_code, ai_tutor_structured_response

LOGGER = logging.getLogger(__name__)

AI_TIMEOUT_SECONDS = 25


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_fix_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    fixed_code = str(payload.get("fixed_code") or "")
    explanation = str(payload.get("explanation") or "")
    improvements = str(payload.get("improvements") or "")
    fix_available = bool(payload.get("fix_available") and fixed_code.strip())
    message = str(payload.get("message") or ("Fix generated." if fix_available else "No usable fix generated."))
    return {
        "fixed_code": fixed_code if fix_available else "",
        "fix_available": fix_available,
        "message": message,
        "explanation": explanation,
        "improvements": improvements,
    }


def generate_structured_fix(
    code: str,
    error_type: str,
    error_message: str,
    error_line: Optional[int],
    traceback_text: str,
) -> Dict[str, Any]:
    safe_code = "" if code is None else str(code)
    safe_error_type = "" if error_type is None else str(error_type)
    safe_error_message = "" if error_message is None else str(error_message)
    safe_traceback = "" if traceback_text is None else str(traceback_text)
    safe_error_line = _safe_int(error_line)

    if not safe_error_message.strip():
        return _validate_fix_payload(
            {
            "fixed_code": "",
            "fix_available": False,
            "message": "No error to fix",
            "explanation": "",
            "improvements": "",
            }
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(
                ai_tutor_structured_response,
                safe_code,
                safe_error_type or "Error",
                safe_error_message,
                safe_error_line,
                safe_traceback,
            )
            tutor_response = future.result(timeout=AI_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        LOGGER.error("AI fix request timed out after %ss", AI_TIMEOUT_SECONDS)
        tutor_response = {
            "explanation": "AI request timed out. Using local fallback.",
            "fixed_code": "",
            "improvements": "Try shorter code blocks or retry in a moment.",
        }
    except Exception:
        LOGGER.exception("AI structured fix crashed")
        tutor_response = {
            "explanation": "AI request failed. Using local fallback.",
            "fixed_code": "",
            "improvements": "Retry and check API key/quota.",
        }

    fixed_code = str(tutor_response.get("fixed_code") or "")

    if not fixed_code.strip():
        execution = {
            "error_type": safe_error_type,
            "error_message": safe_error_message,
            "traceback": safe_traceback,
            "error_line": safe_error_line,
        }
        fallback = ai_fix_code(safe_code, f"{safe_error_message}\n{safe_traceback}", execution=execution)
        fixed_code = str(fallback or "")

    fix_available = bool(fixed_code.strip() and fixed_code.strip() != safe_code.strip())

    return _validate_fix_payload(
        {
        "fixed_code": fixed_code if fix_available else "",
        "fix_available": fix_available,
        "message": "Fix generated." if fix_available else "No usable fix generated.",
        "explanation": str(tutor_response.get("explanation") or ""),
        "improvements": str(tutor_response.get("improvements") or ""),
        }
    )


def generate_tutor_help(code: str, prompt: str, execution: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    safe_code = "" if code is None else str(code)
    safe_prompt = "" if prompt is None else str(prompt)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(ai_assist, safe_code, safe_prompt, execution)
            return future.result(timeout=AI_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        LOGGER.error("AI tutor request timed out after %ss", AI_TIMEOUT_SECONDS)
        return {
            "assistant_message": "AI tutor timed out. Please retry.",
            "suggestions": ["Retry with a shorter prompt."],
            "generated_code": "",
            "can_apply": False,
            "source": "timeout",
        }
    except Exception:
        LOGGER.exception("AI tutor request crashed")
        return {
            "assistant_message": "AI tutor request failed.",
            "suggestions": ["Retry and check API key/quota."],
            "generated_code": "",
            "can_apply": False,
            "source": "error",
        }
