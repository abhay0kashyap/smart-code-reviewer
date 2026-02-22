from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template, request

from analyzer.ai_fixer import ai_fix_with_local_model
from analyzer.error_explainer import explain_error
from analyzer.executor import execute_code


API_PATHS = {"/run", "/ai_fix", "/ai-fix"}


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
                return jsonify({"execution": execution, "explanation": explanation}), 400

            execution = execute_code(code)
            if not execution.get("success"):
                error_text = execution.get("traceback") or execution.get("error_message") or ""
                explanation = explain_error(code, str(error_text), execution.get("error_line"))

            return jsonify({"execution": execution, "explanation": explanation}), 200
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /run error")
            execution["error_message"] = str(exc)
            execution["traceback"] = str(exc)
            explanation = explain_error("", str(exc), execution.get("error_line"))
            return jsonify({"execution": execution, "explanation": explanation}), 500

    @app.post("/ai_fix")
    @app.post("/ai-fix")
    def ai_fix():
        try:
            payload = request.get_json(silent=True) or {}
            code = str(payload.get("code", ""))

            if not code.strip():
                return jsonify(
                    {
                        "execution": {
                            "success": False,
                            "error_type": "InputError",
                            "error_message": "No code provided.",
                            "error_line": None,
                            "traceback": "",
                        },
                        "explanation": {
                            "explanation": "Please write some code before running AI Auto Fix.",
                            "concept": "Type Python code in the editor and try again.",
                            "fix_available": False,
                        },
                        "autofix": {
                            "fix_available": False,
                            "fixed_code": code,
                            "reason": "No code provided.",
                            "changed_lines": [],
                            "source": "none",
                        },
                    }
                ), 400

            execution = execute_code(code)
            explanation = None
            autofix = {
                "fix_available": False,
                "fixed_code": code,
                "reason": "Code already runs successfully.",
                "changed_lines": [],
                "source": "none",
            }

            if not execution.get("success"):
                error_text = execution.get("traceback") or execution.get("error_message") or ""
                explanation = explain_error(code, str(error_text), execution.get("error_line"))
                autofix = ai_fix_with_local_model(code, execution)

            return jsonify(
                {
                    "execution": execution,
                    "explanation": explanation,
                    "autofix": autofix,
                }
            ), 200
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /ai_fix error")
            execution = {
                "success": False,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "error_line": None,
                "traceback": str(exc),
            }
            explanation = explain_error("", str(exc), execution.get("error_line"))
            return jsonify(
                {
                    "execution": execution,
                    "explanation": explanation,
                    "autofix": {
                        "fix_available": False,
                        "fixed_code": "",
                        "reason": str(exc),
                        "changed_lines": [],
                        "source": "none",
                    },
                }
            ), 500

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
