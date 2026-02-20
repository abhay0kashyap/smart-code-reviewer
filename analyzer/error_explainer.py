def explain_error(error: str):
    if error is None:
        return None

    if "SyntaxError" in error:
        return {
            "type": "SyntaxError",
            "explanation": "Python cannot understand your code. You may have forgotten colon (:), bracket, or quotes.",
            "fix": "Check your syntax carefully."
        }

    elif "NameError" in error:
        return {
            "type": "NameError",
            "explanation": "You are using a variable that was not defined.",
            "fix": "Define the variable before using it."
        }

    elif "TypeError" in error:
        return {
            "type": "TypeError",
            "explanation": "You used incompatible data types.",
            "fix": "Check variable types."
        }

    elif "IndentationError" in error:
        return {
            "type": "IndentationError",
            "explanation": "Indentation is incorrect.",
            "fix": "Fix spacing and indentation."
        }

    elif "ZeroDivisionError" in error:
        return {
            "type": "ZeroDivisionError",
            "explanation": "Division by zero is not allowed.",
            "fix": "Make sure denominator is not zero."
        }

    else:
        return {
            "type": "UnknownError",
            "explanation": "Unknown error occurred.",
            "fix": "Check your code carefully."
        }

