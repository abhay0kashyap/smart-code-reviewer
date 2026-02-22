from flask import Flask, request, jsonify, render_template

from analyzer.executor import execute_code
from analyzer.error_explainer import explain_error
from analyzer.ai_fixer import ai_fix_code

app = Flask(__name__)


def run_ai_fixer_for_all_errors(original_code, initial_execution, max_attempts=3):
    """Iteratively apply AI fixes to handle chained errors."""
    current_code = original_code
    current_execution = initial_execution
    attempts = 0
    sources = []
    llm_errors = []
    ollama_enabled = True

    while not current_execution["success"] and attempts < max_attempts:
        fix_result = ai_fix_code(
            current_code,
            current_execution["error_message"],
            current_execution["error_type"],
            enable_ollama=ollama_enabled,
        )
        fixed_code = fix_result["fixed_code"]

        if fix_result["source"] != "none":
            sources.append(fix_result["source"])
        if fix_result.get("llm_error"):
            llm_errors.append(fix_result["llm_error"])
            ollama_enabled = False

        if not fixed_code or fixed_code.strip() == current_code.strip():
            break

        current_code = fixed_code
        attempts += 1
        current_execution = execute_code(current_code)

    return {
        "fixed_code": current_code,
        "attempts": attempts,
        "execution": current_execution,
        "sources": sources,
        "llm_errors": llm_errors,
    }


# Home page
@app.route("/")
def index():
    return render_template("index.html")


# Run code route
@app.route("/run", methods=["POST"])
def run_code():

    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    if not code.strip():
        return jsonify({"error": "No code provided"}), 400

    # execute code
    execution = execute_code(code)

    explanation = None

    # if error → explain and fix
    if not execution["success"]:

        explanation = explain_error(
            execution["error_type"],
            execution["error_message"],
            code,
        )

        explanation["fix_available"] = explanation.get("fix_available", False)


    return jsonify({
        "execution": execution,
        "explanation": explanation
    })


@app.route("/ai-fix", methods=["POST"])
def ai_fix_code_route():
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    if not code.strip():
        return jsonify({"error": "No code provided"}), 400

    execution = execute_code(code)
    if execution["success"]:
        return jsonify({
            "fix_applied": False,
            "message": "Code already runs successfully.",
            "fixed_code": code,
            "execution": execution,
        })

    fix_result = run_ai_fixer_for_all_errors(code, execution, max_attempts=5)
    fixed_code = fix_result["fixed_code"]
    fix_applied = fixed_code.strip() != code.strip()

    response = {
        "fix_applied": fix_applied,
        "fixed_code": fixed_code,
        "original_execution": execution,
        "fixed_execution": fix_result["execution"],
        "ai_fix_attempts": fix_result["attempts"],
        "ai_fix_sources": fix_result["sources"],
        "ai_fixer_warning": "Ollama unavailable. Used rule-based fallback." if fix_result["llm_errors"] else None,
    }
    return jsonify(response)


# start server
if __name__ == "__main__":
    app.run(debug=True, port=8000)
