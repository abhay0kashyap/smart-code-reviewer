import ast

def check_mutable_default_args(tree):
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append({
                        "type": "error",
                        "message": "Mutable default argument detected. Use None instead.",
                        "line": node.lineno
                    })

    return issues
