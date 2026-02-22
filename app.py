from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template, request

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
        explanation = None

        try:
            payload = request.get_json(silent=True) or {}
            code = str(payload.get("code", ""))

            if not code.strip():
                execution["error_type"] = "InputError"
                execution["error_message"] = "No code provided."
                explanation = explain_error(code, execution)
                return jsonify({"execution": execution, "explanation": explanation}), 400

            execution = execute_code(code)
            if not execution.get("success"):
                explanation = explain_error(code, execution)

            return jsonify({"execution": execution, "explanation": explanation}), 200
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /run error")
            execution["error_message"] = str(exc)
            execution["traceback"] = str(exc)
            explanation = explain_error("", execution)
            return jsonify({"execution": execution, "explanation": explanation}), 500

    @app.post("/ai_fix")
    @app.post("/ai-fix")
    def ai_fix():
        return jsonify({"fix_available": False, "message": "AI fix endpoint will be enabled in a follow-up commit."}), 200

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
