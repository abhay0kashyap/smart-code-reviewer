from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from analyzer.engine import auto_fix_workflow, run_code_workflow


API_PATHS = {"/run", "/ai_fix", "/ai-fix"}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/run")
    def run_code():
        try:
            payload = request.get_json(silent=True) or {}
            code = str(payload.get("code", ""))
            response, status_code = run_code_workflow(code)
            return jsonify(response), status_code
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /run error")
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Internal server error while running code.",
                        "details": str(exc),
                    }
                ),
                500,
            )

    @app.post("/ai_fix")
    @app.post("/ai-fix")
    def ai_fix():
        try:
            payload = request.get_json(silent=True) or {}
            code = str(payload.get("code", ""))
            model = str(payload.get("model", "llama3")).strip() or "llama3"
            response, status_code = auto_fix_workflow(code=code, model=model, max_rounds=4)
            return jsonify(response), status_code
        except Exception as exc:  # pragma: no cover - defensive fallback
            app.logger.exception("Unexpected /ai_fix error")
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Internal server error while fixing code.",
                        "details": str(exc),
                    }
                ),
                500,
            )

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
