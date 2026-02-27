from __future__ import annotations

import logging
import os
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from services.ai_service import generate_structured_fix, generate_tutor_help
from services.execution_service import run_user_code
from utils.logging_config import configure_logging
from utils.rate_limiter import InMemoryRateLimiter

LOGGER = logging.getLogger(__name__)
API_PATHS = {"/run", "/ai_fix", "/ai-fix", "/ai_assist", "/ai-assist"}
AI_RATE_LIMIT = int(os.getenv("AI_RATE_LIMIT", "20"))
AI_RATE_WINDOW_SECONDS = int(os.getenv("AI_RATE_WINDOW_SECONDS", "60"))


def _json_error(message: str, status_code: int = 400, **extra: Any):
    payload: Dict[str, Any] = {"ok": False, "error": message}
    payload.update(extra)
    return jsonify(payload), status_code


def _client_key() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.remote_addr or "unknown").strip()


def create_app() -> Flask:
    configure_logging(log_dir=os.getenv("LOG_DIR", "logs"))
    app = Flask(__name__)
    limiter = InMemoryRateLimiter()

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/run")
    def run_code():
        payload = request.get_json(silent=True)
        if payload is None or not isinstance(payload, dict):
            return _json_error("Invalid JSON body.")

        code = str(payload.get("code", ""))
        LOGGER.info("/run request ip=%s code_chars=%d", _client_key(), len(code))

        result = run_user_code(code)
        status_code = 200 if result.get("execution", {}).get("error_type") != "InputError" else 400
        return jsonify(result), status_code

    @app.post("/ai_fix")
    @app.post("/ai-fix")
    def ai_fix():
        client_ip = _client_key()
        if not limiter.allow(f"ai_fix:{client_ip}", AI_RATE_LIMIT, AI_RATE_WINDOW_SECONDS):
            LOGGER.warning("AI fix rate limit hit ip=%s", client_ip)
            return _json_error("Rate limit exceeded for AI fix requests.", 429)

        payload = request.get_json(silent=True)
        if payload is None or not isinstance(payload, dict):
            return _json_error("Invalid JSON body.")

        code = str(payload.get("original_code", payload.get("code", "")))
        error_type = str(payload.get("error_type", ""))
        error_message = str(payload.get("error_message", payload.get("error", "")))
        error_line = payload.get("error_line")
        traceback_text = str(payload.get("traceback", ""))

        LOGGER.info(
            "/ai-fix request ip=%s code_chars=%d error_type=%s error_line=%s",
            client_ip,
            len(code),
            error_type or "unknown",
            error_line,
        )

        if not code.strip():
            return _json_error("No code provided.", 400, fix_available=False, fixed_code="")

        fix_result = generate_structured_fix(code, error_type, error_message, error_line, traceback_text)
        return jsonify(fix_result), 200

    @app.post("/ai_assist")
    @app.post("/ai-assist")
    def ai_assist():
        client_ip = _client_key()
        if not limiter.allow(f"ai_assist:{client_ip}", AI_RATE_LIMIT, AI_RATE_WINDOW_SECONDS):
            LOGGER.warning("AI assist rate limit hit ip=%s", client_ip)
            return _json_error("Rate limit exceeded for AI tutor requests.", 429)

        payload = request.get_json(silent=True)
        if payload is None or not isinstance(payload, dict):
            return _json_error("Invalid JSON body.")

        code = str(payload.get("code", ""))
        prompt = str(payload.get("prompt", ""))
        LOGGER.info("/ai-assist request ip=%s code_chars=%d prompt_chars=%d", client_ip, len(code), len(prompt))

        if not code.strip() and not prompt.strip():
            return _json_error("Provide code or a question prompt.")

        run_result = run_user_code(code) if code.strip() else None
        execution = run_result["execution"] if run_result else None
        explanation = run_result["explanation"] if run_result else None

        assistant_payload = generate_tutor_help(code, prompt, execution)
        return jsonify({"assistant": assistant_payload, "execution": execution, "explanation": explanation}), 200

    @app.errorhandler(404)
    def not_found(_error):
        if request.path in API_PATHS:
            return _json_error("Route not found.", 404)
        return render_template("index.html"), 200

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        if request.path in API_PATHS:
            LOGGER.exception("Unhandled API exception path=%s", request.path)
            return _json_error("Unhandled server exception.", 500, details=str(exc))
        raise exc

    return app

