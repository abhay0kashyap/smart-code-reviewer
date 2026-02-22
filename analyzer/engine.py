from __future__ import annotations

from typing import Any, Dict, Tuple

from .ai_fixer import generate_fixed_code
from .error_explainer import explain_error
from .executor import execute_code


def _empty_code_response() -> Tuple[Dict[str, Any], int]:
    return (
        {
            "ok": False,
            "error": "No code provided.",
            "execution": None,
            "explanation": None,
        },
        400,
    )


def run_code_workflow(code: str) -> Tuple[Dict[str, Any], int]:
    if not code or not code.strip():
        return _empty_code_response()

    execution = execute_code(code)
    explanation = None

    if not execution["success"]:
        explanation = explain_error(
            error_type=execution.get("error_type"),
            error_message=execution.get("error_message"),
            error_line=execution.get("error_line"),
            traceback_text=execution.get("traceback"),
        )

    return {
        "ok": True,
        "execution": execution,
        "explanation": explanation,
    }, 200


def auto_fix_workflow(code: str, model: str = "llama3", max_rounds: int = 4) -> Tuple[Dict[str, Any], int]:
    if not code or not code.strip():
        return _empty_code_response()

    original_execution = execute_code(code)

    if original_execution["success"]:
        return {
            "ok": True,
            "fix_applied": False,
            "message": "Code already runs successfully.",
            "fixed_code": code,
            "original_execution": original_execution,
            "fixed_execution": original_execution,
            "final_explanation": None,
            "attempts": 0,
            "steps": [],
            "ai_warning": None,
        }, 200

    current_code = code
    current_execution = original_execution
    steps = []
    ai_warning = None
    ollama_enabled = True

    for attempt in range(1, max_rounds + 1):
        fix_result = generate_fixed_code(
            code=current_code,
            execution=current_execution,
            model=model,
            use_ollama=ollama_enabled,
        )

        candidate_code = fix_result["fixed_code"]
        changed = candidate_code.strip() != current_code.strip()

        if fix_result.get("ollama_error"):
            ai_warning = "Ollama unavailable or returned invalid output. Using local fallback rules."
            ollama_enabled = False

        steps.append(
            {
                "attempt": attempt,
                "source": fix_result["source"],
                "changed": changed,
                "error": fix_result.get("error"),
            }
        )

        if not changed:
            break

        current_code = candidate_code
        current_execution = execute_code(current_code)
        if current_execution["success"]:
            break

    final_explanation = None
    if not current_execution["success"]:
        final_explanation = explain_error(
            error_type=current_execution.get("error_type"),
            error_message=current_execution.get("error_message"),
            error_line=current_execution.get("error_line"),
            traceback_text=current_execution.get("traceback"),
        )

    fix_applied = current_code.strip() != code.strip()

    if fix_applied and current_execution["success"]:
        message = "AI Auto Fix applied successfully."
    elif fix_applied:
        message = "Partial fix applied. Code still has an error."
    else:
        message = "No automatic fix could be applied."

    return {
        "ok": True,
        "fix_applied": fix_applied,
        "message": message,
        "fixed_code": current_code,
        "original_execution": original_execution,
        "fixed_execution": current_execution,
        "final_explanation": final_explanation,
        "attempts": len(steps),
        "steps": steps,
        "ai_warning": ai_warning,
    }, 200
