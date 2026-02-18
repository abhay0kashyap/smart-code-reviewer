import ast

def analyze_code(code: str):
    try:
        tree = ast.parse(code)
        return {
            "status": "success",
            "message": "Code parsed successfully!",
            "issues": []
        }
    except SyntaxError as e:
        return {
            "status": "error",
            "message": f"Syntax Error at line {e.lineno}",
            "issues": []
        }
