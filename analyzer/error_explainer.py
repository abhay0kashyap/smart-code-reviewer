from __future__ import annotations

import re
from typing import Dict, Optional


def _get_default_explanation(error_type: str) -> str:
    explanations = {
        "SyntaxError": "Python could not understand the way this line is written.",
        "IndentationError": "The spacing at the start of a line is inconsistent.",
        "TabError": "The code mixes tabs and spaces in indentation.",
        "NameError": "A variable or function name was used before being defined.",
        "TypeError": "Two values were used together in an incompatible way.",
        "ValueError": "A value has the right type but an invalid content.",
        "IndexError": "You tried to access a list position that does not exist.",
        "KeyError": "You asked a dictionary for a key that is not present.",
        "AttributeError": "You tried to use a method or property that does not exist on this object.",
        "ZeroDivisionError": "Division by zero is not allowed.",
        "ImportError": "Python could not import the requested module or name.",
        "ModuleNotFoundError": "A module is missing in the current environment.",
        "TimeoutError": "The program took too long to finish.",
    }
    return explanations.get(error_type, "Python raised an error while executing the program.")


def _get_default_suggestion(error_type: str, error_message: str, error_line: Optional[int]) -> str:
    line_note = f" on line {error_line}" if error_line else ""

    if error_type == "SyntaxError":
        if "expected ':'" in error_message:
            return f"Add a ':' at the end of the statement{line_note}."
        if "never closed" in error_message:
            return f"Close the missing quote, bracket, or parenthesis{line_note}."
        return f"Check punctuation and structure carefully{line_note}."

    if error_type in {"IndentationError", "TabError"}:
        return "Use only spaces for indentation (usually 4 spaces per block)."

    if error_type == "NameError":
        undefined = re.search(r"name '(.+?)' is not defined", error_message)
        if undefined:
            return f"Define '{undefined.group(1)}' first, or wrap it in quotes if it is text."
        return "Define the variable before using it."

    if error_type == "TypeError":
        return "Convert values to compatible types (for example, int/float/str) before combining them."

    if error_type == "ValueError":
        return "Validate and convert input values before using them."

    if error_type == "IndexError":
        return "Check list length before indexing, or use a valid index."

    if error_type == "KeyError":
        return "Use dict.get(key) or verify that the key exists before reading it."

    if error_type == "AttributeError":
        return "Check the object type and available attributes with dir(object)."

    if error_type == "ZeroDivisionError":
        return "Ensure the denominator is not zero before division."

    if error_type in {"ImportError", "ModuleNotFoundError"}:
        return "Install the missing package and verify the module name."

    if error_type == "TimeoutError":
        return "Reduce loops/workload or optimize the logic to finish faster."

    return "Read the traceback and fix the first failing line first."


def explain_error(
    error_type: Optional[str],
    error_message: Optional[str],
    error_line: Optional[int] = None,
    traceback_text: Optional[str] = None,
) -> Dict[str, object]:
    resolved_error_type = (error_type or "ExecutionError").strip() or "ExecutionError"
    resolved_error_message = (error_message or "Unknown error").strip() or "Unknown error"

    if error_line is None and traceback_text:
        line_matches = re.findall(r"line\s+(\d+)", traceback_text)
        if line_matches:
            error_line = int(line_matches[-1])

    explanation = _get_default_explanation(resolved_error_type)
    suggestion = _get_default_suggestion(resolved_error_type, resolved_error_message, error_line)

    fix_available = resolved_error_type in {
        "SyntaxError",
        "IndentationError",
        "TabError",
        "NameError",
        "TypeError",
        "ValueError",
        "IndexError",
        "KeyError",
        "AttributeError",
        "ZeroDivisionError",
        "ImportError",
        "ModuleNotFoundError",
    }

    return {
        "error_line": error_line,
        "error_type": resolved_error_type,
        "error_message": resolved_error_message,
        "explanation": explanation,
        "suggestion": suggestion,
        "fix_available": fix_available,
    }
