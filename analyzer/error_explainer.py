def explain_error(error: str):

    if error is None:
        return None

    if "SyntaxError" in error:
        return {
            "type": "SyntaxError",
            "explanation": "Python cannot understand your code syntax.",
            "fix_steps": [
                "Check if you forgot colon ':'",
                "Check brackets (), {}, []",
                "Check quotes ' or \"",
                "Check spelling of keywords"
            ]
        }

    elif "NameError" in error:
        return {
            "type": "NameError",
            "explanation": "You are using a variable that is not defined.",
            "fix_steps": [
                "Check spelling of variable name",
                "Make sure variable is created first",
                "Example: x = 10"
            ]
        }

    elif "TypeError" in error:
        return {
            "type": "TypeError",
            "explanation": "You used wrong data type.",
            "fix_steps": [
                "Check if mixing string and number",
                "Convert types properly",
                "Example: str(number)"
            ]
        }

    elif "IndentationError" in error:
        return {
            "type": "IndentationError",
            "explanation": "Indentation is incorrect.",
            "fix_steps": [
                "Use proper spacing",
                "Use same indentation level",
                "Example: 4 spaces per block"
            ]
        }

    else:
        return {
            "type": "Error",
            "explanation": "Python encountered an error.",
            "fix_steps": [
                "Read error message carefully",
                "Check code line mentioned",
                "Fix syntax or logic"
            ]
        }
