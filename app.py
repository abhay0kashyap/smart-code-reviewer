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

    code = request.json["code"]

    execution = execute_code(code)

    explanation = None

    if not execution["success"]:
        explanation = explain_error(
            execution["error_type"],
            execution["error_message"]
        )

    return jsonify({
        "execution": execution,
        "explanation": explanation
    })

@app.route("/analyze", methods=["POST"])
def analyze():
    code = request.json["code"]

    analysis = analyze_code(code)

    return jsonify(analysis)

if __name__ == "__main__":
    app.run(debug=True)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
