from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template, request

from analyzer.ai_fixer import ai_assist, ai_fix_code, ai_fix_with_openai
from analyzer.error_explainer import explain_error
from analyzer.executor import execute_code


API_PATHS = {"/run", "/ai_fix", "/ai-fix", "/ai_assist", "/ai-assist"}


def create_app() -> Flask:
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/run")
    def run_code():
        execution = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "output": "",
            "error_type": "ExecutionError",
            "error_message": None,
            "error_line": None,
            "error_line_number": None,
            "traceback": "",
            "return_code": None,
            "timed_out": False,
        }
        explanation = {
            "explanation": "",
            "concept": "",
            "fix_available": False,
        }

        try:
            payload = request.get_json(silent=True) or {}
            code = str(payload.get("code", ""))

            if not code.strip():
                execution["error_type"] = "InputError"
                execution["error_message"] = "No code provided."
                explanation = explain_error(code, execution["error_message"], execution["error_line"])
                return jsonify({"success": False, "execution": execution, "explanation": explanation}), 400

            execution = execute_code(code)
            execution["error_line_number"] = execution.get("error_line")
            if not execution.get("success"):
                error_text = execution.get("traceback") or execution.get("error_message") or ""
                explanation = explain_error(code, str(error_text), execution.get("error_line"))

            return jsonify({"success": bool(execution.get("success")), "execution": execution, "explanation": explanation}), 200
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /run error")
            execution["error_message"] = str(exc)
            execution["traceback"] = str(exc)
            explanation = explain_error("", str(exc), execution.get("error_line"))
            return jsonify({"success": False, "execution": execution, "explanation": explanation}), 500

    @app.post("/ai_fix")
    @app.post("/ai-fix")
    def ai_fix():
        try:
            payload = request.get_json(silent=True)
            if payload is None or not isinstance(payload, dict):
                return jsonify({"fixed_code": "", "fix_available": False, "message": "Invalid JSON body."}), 400

            code = str(payload.get("original_code", payload.get("code", "")))
            error_message = str(payload.get("error_message", payload.get("error", "")))
            traceback_text = str(payload.get("traceback", ""))

            if not code.strip():
                return jsonify({"fixed_code": code, "fix_available": False, "message": "No code provided."}), 400

            if not error_message.strip():
                return jsonify({"fixed_code": "", "fix_available": False, "message": "No error to fix"}), 200

            fixed_code = ai_fix_with_openai(code, error_message, traceback_text)

            # If OpenAI fails/unavailable, keep deterministic fallback.
            if not fixed_code.strip():
                execution = {
                    "error_type": "",
                    "error_message": error_message,
                    "traceback": traceback_text,
                    "error_line": None,
                }
                fixed_code = ai_fix_code(code, f"{error_message}\n{traceback_text}", execution=execution)

            fix_available = bool(fixed_code.strip() and fixed_code.strip() != code.strip())
            message = "Fix generated." if fix_available else "No usable fix generated."

            return jsonify(
                {
                    "fixed_code": fixed_code if fix_available else "",
                    "fix_available": fix_available,
                    "message": message,
                }
            ), 200
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /ai_fix error")
            print("AI ERROR:", str(exc))
            return jsonify({"fixed_code": "", "fix_available": False, "error": str(exc)}), 200

    @app.post("/ai_assist")
    @app.post("/ai-assist")
    def ai_assist_route():
        try:
            payload = request.get_json(silent=True)
            if payload is None or not isinstance(payload, dict):
                return jsonify({"assistant": {}, "message": "Invalid JSON body."}), 400

            code = str(payload.get("code", ""))
            prompt = str(payload.get("prompt", ""))

            if not code.strip() and not prompt.strip():
                return jsonify({"assistant": {}, "message": "Provide code or a question prompt."}), 400

            execution = None
            explanation = None
            if code.strip():
                execution = execute_code(code)
                if not execution.get("success"):
                    error_text = execution.get("traceback") or execution.get("error_message") or ""
                    explanation = explain_error(code, str(error_text), execution.get("error_line"))

            assistant_payload = ai_assist(code, prompt, execution=execution)
            return (
                jsonify(
                    {
                        "assistant": assistant_payload,
                        "execution": execution,
                        "explanation": explanation,
                    }
                ),
                200,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /ai_assist error")
            return jsonify({"assistant": {}, "error": str(exc)}), 200

    @app.errorhandler(404)
    def not_found(_error):
        if request.path in API_PATHS:
            return jsonify({"ok": False, "error": "Route not found."}), 404
        return render_template("index.html"), 200

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        if request.path in API_PATHS:
            app.logger.exception("Unhandled API exception")
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Unhandled server exception.",
                        "details": str(exc),
                    }
                ),
                500,
            )
        raise exc

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
