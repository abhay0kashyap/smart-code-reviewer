from __future__ import annotations

import logging
import traceback
from typing import Any, Dict

from analyzer.error_explainer import explain_error
from analyzer.executor import execute_code

LOGGER = logging.getLogger(__name__)


def run_user_code(code: str) -> Dict[str, Any]:
    safe_code = "" if code is None else str(code)
    LOGGER.info("run_user_code invoked. chars=%d", len(safe_code))

    if not safe_code.strip():
        return {
            "success": False,
            "output": "",
            "error": {
                "type": "InputError",
                "message": "No code provided.",
                "line": None,
                "traceback": "",
            },
            "execution": {
                "success": False,
                "stdout": "",
                "stderr": "",
                "output": "",
                "error_type": "InputError",
                "error_message": "No code provided.",
                "error_line": None,
                "error_line_number": None,
                "traceback": "",
                "error": {
                    "type": "InputError",
                    "message": "No code provided.",
                    "line": None,
                    "traceback": "",
                },
                "return_code": None,
                "timed_out": False,
            },
            "explanation": explain_error(safe_code, "InputError: No code provided.", None),
        }

    try:
        execution = execute_code(safe_code)
        execution["error_line_number"] = execution.get("error_line")

        explanation = {
            "explanation": "",
            "concept": "",
            "fix_available": False,
        }

        if not execution.get("success"):
            err_text = execution.get("traceback") or execution.get("error_message") or ""
            explanation = explain_error(safe_code, str(err_text), execution.get("error_line"))

        return {
            "success": bool(execution.get("success")),
            "output": execution.get("output", ""),
            "error": execution.get("error"),
            "execution": execution,
            "explanation": explanation,
        }
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.exception("run_user_code failed unexpectedly")
        error_payload = {
            "type": "ExecutionServiceError",
            "message": str(exc),
            "line": None,
            "traceback": traceback.format_exc(),
        }
        return {
            "success": False,
            "output": "",
            "error": error_payload,
            "execution": {
                "success": False,
                "stdout": "",
                "stderr": "",
                "output": "",
                "error_type": "ExecutionServiceError",
                "error_message": str(exc),
                "error_line": None,
                "error_line_number": None,
                "traceback": error_payload["traceback"],
                "error": error_payload,
                "return_code": None,
                "timed_out": False,
            },
            "explanation": explain_error(safe_code, f"ExecutionServiceError: {exc}", None),
        }
