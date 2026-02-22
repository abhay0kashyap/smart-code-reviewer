# analyzer/error_explainer.py

import ast
import re


def explain_error(error_type, error_message, code):

    explanation = ""
    concept = ""
    fix_available = False
    correct_line = None
    fixed_full_code = code
    error_line = None

    lines = code.splitlines()

    try:

        # Use Python AST to get exact error location
        ast.parse(code)

    except SyntaxError as e:

        error_line = e.lineno
        if not error_line or error_line < 1 or error_line > len(lines):
            original_line = ""
        else:
            original_line = lines[error_line - 1]

        explanation = e.msg

        concept = "Python syntax error means structure of code is wrong."

        new_line = original_line


        # Fix 1: ; instead of :
        if original_line.strip().endswith(";"):

            new_line = original_line.rstrip(";") + ":"

            explanation = "You used ';' but Python requires ':'"

            concept = "Use ':' after if, for, while, def, else"

            fix_available = True


        # Fix 2: missing colon
        elif original_line.strip().startswith(("if", "for", "while", "def", "else", "elif")):

            if not original_line.strip().endswith(":"):

                new_line = original_line + ":"

                explanation = "Missing ':' at end of statement"

                concept = "Python blocks must end with ':'"

                fix_available = True


        # Apply fix
        if fix_available:

            correct_line = new_line

            new_lines = lines.copy()

            new_lines[error_line - 1] = new_line

            fixed_full_code = "\n".join(new_lines)


    except Exception:

        pass


    # Handle NameError separately
    if error_type == "NameError":

        match = re.search(r"name '(.+)' is not defined", error_message)

        if match:

            name = match.group(1)

            for i, line in enumerate(lines):

                if name in line:

                    error_line = i + 1

                    new_line = line.replace(name, f'"{name}"')

                    correct_line = new_line

                    new_lines = lines.copy()

                    new_lines[i] = new_line

                    fixed_full_code = "\n".join(new_lines)

                    explanation = f"{name} is treated as variable. Use quotes for string."

                    concept = "Strings must be inside quotes"

                    fix_available = True

                    break

    if not explanation and error_message:
        explanation = error_message.splitlines()[-1]

    if not concept:
        concept = "Review the traceback and fix the first failing line."


    return {

        "error_line": error_line,

        "explanation": explanation,

        "concept": concept,

        "fix_available": fix_available,

        "correct_line": correct_line,

        "fixed_full_code": fixed_full_code

    }
