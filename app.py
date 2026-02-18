from flask import Flask, request, jsonify
from analyzer.engine import analyze_code

app = Flask(__name__)

@app.route("/")
def home():
    return "Smart Code Reviewer Running 🚀"

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    code = data.get("code", "")
    result = analyze_code(code)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
