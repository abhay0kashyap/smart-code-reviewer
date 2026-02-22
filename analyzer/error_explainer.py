from __future__ import annotations

import re
from typing import Any, Dict


def _friendly_explanation(error_type: str) -> str:
    mapping = {
        "SyntaxError": "Python could not understand the structure of one line.",
        "IndentationError": "The spacing at the start of lines is inconsistent.",
        "TabError": "The code mixes tabs and spaces for indentation.",
        "NameError": "A variable or function name was used before being defined.",
        "TypeError": "Two values were used together in a way Python does not allow.",
        "ImportError": "Python could not import the requested module or symbol.",
        "ModuleNotFoundError": "A required Python module is not installed.",
        "IndexError": "A list index was used that does not exist.",
        "AttributeError": "The object does not have the attribute or method you called.",
        "KeyError": "A dictionary key was requested but does not exist.",
        "ValueError": "A value is present but not valid for the operation.",
        "ZeroDivisionError": "A division by zero was attempted.",
    }
    return mapping.get(error_type, "Python raised an error while running your code.")


def _suggestion(error_type: str, error_message: str) -> str:
    if error_type == "NameError":
        match = re.search(r"name '(.+?)' is not defined", error_message)
        if match:
            return f"Define '{match.group(1)}' first, or wrap it in quotes if it is text."
    if error_type == "SyntaxError" and "expected ':'" in error_message:
        return "Add ':' at the end of the related statement."
    if error_type in {"IndentationError", "TabError"}:
        return "Use 4 spaces per indentation level and avoid mixing tabs/spaces."
    if error_type == "IndexError":
        return "Check list length before reading by index."
    if error_type == "KeyError":
        return "Use dict.get(key) or check if the key exists before access."
    if error_type in {"ImportError", "ModuleNotFoundError"}:
        return "Install missing modules and verify import names."
    return "Fix the first traceback error line and run again."


def explain_error(code: str, execution: Dict[str, Any]) -> Dict[str, object]:
    error_type = str(execution.get("error_type") or "ExecutionError")
    error_message = str(execution.get("error_message") or "Unknown error")
    error_line = execution.get("error_line")
    traceback_text = str(execution.get("traceback") or "")

    if error_line is None and traceback_text:
        matches = re.findall(r"line\s+(\d+)", traceback_text)
        if matches:
            error_line = int(matches[-1])

    return {
        "error_line": error_line,
        "error_type": error_type,
        "error_message": error_message,
        "explanation": _friendly_explanation(error_type),
        "suggestion": _suggestion(error_type, error_message),
        "fix_available": True,
    }
