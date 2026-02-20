def explain_error(error_type, error_message):

    explanations = {
        "NameError": "You are using a variable that has not been defined.",
        "SyntaxError": "Your code syntax is incorrect.",
        "TypeError": "You used incompatible data types.",
        "IndentationError": "Your indentation is incorrect.",
        "ZeroDivisionError": "You cannot divide by zero.",
        "IndexError": "You tried to access an index that doesn't exist.",
        "KeyError": "You tried to access a key that doesn't exist in dictionary.",
        "AttributeError": "Object does not have that attribute."
    }

    fixes = {
        "NameError": "Define the variable before using it.",
        "SyntaxError": "Check brackets, quotes, and colons.",
        "TypeError": "Check variable types.",
        "IndentationError": "Fix indentation spacing.",
        "ZeroDivisionError": "Ensure denominator is not zero.",
        "IndexError": "Check list index range.",
        "KeyError": "Check dictionary keys.",
        "AttributeError": "Check object properties."
    }

    return {
        "explanation": explanations.get(error_type, "Python encountered an error."),
        "fix": fixes.get(error_type, "Check your code and fix the error.")
    }
