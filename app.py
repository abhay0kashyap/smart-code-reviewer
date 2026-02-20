from flask import Flask, request, jsonify, render_template
from analyzer.engine import analyze_code
from analyzer.executor import execute_code
from analyzer.error_explainer import explain_error

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_code():
    data = request.get_json()
    code = data.get("code", "")

    execution_result = execute_code(code)

    explanation = None
    if execution_result["error"]:
        explanation = explain_error(execution_result["error"], code)


    analysis_result = analyze_code(code)

    return jsonify({
        "execution": execution_result,
        "explanation": explanation,
        "analysis": analysis_result
    })

if __name__ == "__main__":
    app.run(debug=True)
