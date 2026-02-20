# analyzer/error_explainer.py
import re

def explain_error(error_type: str, error_message: str, code: str):
    """
    Returns a dict:
      {
        "explanation": str,
        "fix_available": bool,
        "correct_line": str or None,
        "fixed_full_code": str or None,
        "concept": str
      }
    """
    lines = code.splitlines()
    explanation = "Python encountered an error."
    fix_available = False
    correct_line = None
    fixed_full_code = code
    concept = ""

    # Helper to replace a single line (1-indexed)
    def replace_line(n, new_line):
        nonlocal fixed_full_code
        if not n or n < 1 or n > len(lines):
            return
        new_lines = lines.copy()
        new_lines[n-1] = new_line
        fixed_full_code = "\n".join(new_lines)

    # --- NameError: often missing quotes around a literal string
    if error_type == "NameError":
        explanation = "You used a name (identifier) that Python doesn't know about."
        concept = "In Python, plain words without quotes are treated as variables. If you meant text, use quotes (single or double)."
        # try to find an unquoted literal in the message: "name 'hello' is not defined"
        m = re.search(r"name '(.+?)' is not defined", error_message)
        if m:
            name = m.group(1)
            # find a line containing that name (simple heuristic)
            for i, L in enumerate(lines, start=1):
                if re.search(rf"\b{name}\b", L):
                    # propose quoting it
                    new_line = re.sub(rf"\b{name}\b", f'"{name}"', L, count=1)
                    correct_line = new_line
                    replace_line(i, new_line)
                    fix_available = True
                    break

    # --- SyntaxError: many possible causes — we implement a few safe heuristics
    elif error_type == "SyntaxError":
        explanation = "Your code syntax is incorrect — Python couldn't parse that line."
        concept = "Common causes: missing colon after def/if/for/while, stray backslash, mismatched quotes or parentheses."
        # Unexpected character after line continuation (common when user typed backslash)
        if "unexpected character after line continuation character" in error_message:
            # find a line with a backslash "\" and remove a stray backslash
            for i, L in enumerate(lines, start=1):
                if "\\" in L:
                    new_line = L.replace("\\", "")
                    correct_line = new_line
                    replace_line(i, new_line)
                    fix_available = True
                    break
        # Missing colon: look for def/if/for/while/else/elif lines missing colon at end
        if not fix_available:
            for i, L in enumerate(lines, start=1):
                stripped = L.strip()
                if re.match(r'^(def|if|for|while|elif|else|try|except|with)\b', stripped):
                    # if line does not end with a colon, propose adding it
                    if not stripped.endswith(":"):
                        new_line = L.rstrip() + ":"
                        correct_line = new_line
                        replace_line(i, new_line)
                        fix_available = True
                        concept = "Control structures and function definitions must end with a colon ':' in Python."
                        break
        # unmatched quotes or parentheses — as a safe attempt, do not auto-fix (just explain)
        if not fix_available:
            # check for unbalanced parentheses/quotes — explain only
            # we avoid auto-fixing these as they can be ambiguous
            if error_message:
                pass

    # --- TypeError, IndexError, etc. — provide explanation and sample fix hint
    elif error_type == "TypeError":
        explanation = "You used a value in a way that doesn't fit its type (e.g., adding string + int)."
        concept = "Check the types of the variables. Convert types when necessary (e.g., str(123) or int('12'))."
        fix_available = False

    elif error_type == "IndentationError":
        explanation = "Your code indentation is incorrect."
        concept = "Python uses indentation to define blocks. Make sure the indentation level is consistent (use spaces, typically 4)."
        fix_available = False

    elif error_type == "ZeroDivisionError":
        explanation = "You attempted to divide by zero."
        concept = "Ensure denominator is not zero before dividing. Example: if denom != 0: result = num/denom"
        fix_available = False

    else:
        # generic fallback
        explanation = f"Python raised {error_type}. {error_message}"
        concept = "Read the error type and the message — it tells you what went wrong."

    return {
        "explanation": explanation,
        "fix_available": fix_available,
        "correct_line": correct_line,
        "fixed_full_code": fixed_full_code,
        "concept": concept
    }