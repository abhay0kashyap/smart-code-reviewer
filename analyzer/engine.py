import ast
from .rules import check_mutable_default_args

def analyze_code(code: str):
    try:
        tree = ast.parse(code)

        issues = []
        issues.extend(check_mutable_default_args(tree))

        return {
            "status": "success",
            "message": "Analysis complete",
            "issues": issues
        }

    except SyntaxError as e:
        return {
            "status": "error",
            "message": f"Syntax Error at line {e.lineno}",
            "issues": []
        }
