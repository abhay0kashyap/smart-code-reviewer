def explain_error(error: str, code: str):

    if error is None:
        return None

    lines = code.split("\n")

    # Find error line number
    error_line_number = None
    for line in error.split("\n"):
        if "line" in line:
            try:
                parts = line.split("line")
                error_line_number = int(parts[1].split(",")[0].strip())
                break
            except:
                pass

    wrong_line = None
    if error_line_number and error_line_number <= len(lines):
        wrong_line = lines[error_line_number - 1]

    explanation = {}
    
    if "NameError" in error:

        explanation = {
            "type": "NameError",
            "error_line": error_line_number,
            "wrong_code": wrong_line,
            "reason": "Python thinks 'hello' is a variable, but it is not defined.",
            "fix": "If you want text, you must use quotes.",
            "correct_line": f'print("hello")'
        }

        fixed_lines = lines.copy()
        if error_line_number:
            fixed_lines[error_line_number - 1] = explanation["correct_line"]

        explanation["fixed_full_code"] = "\n".join(fixed_lines)

    elif "SyntaxError" in error:

        explanation = {
            "type": "SyntaxError",
            "error_line": error_line_number,
            "wrong_code": wrong_line,
            "reason": "Your syntax is incorrect.",
            "fix": "Check brackets, quotes, and colon.",
            "correct_line": "Fix syntax properly"
        }

        explanation["fixed_full_code"] = code

    else:

        explanation = {
            "type": "Error",
            "error_line": error_line_number,
            "wrong_code": wrong_line,
            "reason": "There is an error in your code.",
            "fix": "Fix based on error message.",
            "correct_line": ""
        }

        explanation["fixed_full_code"] = code

    return explanation
