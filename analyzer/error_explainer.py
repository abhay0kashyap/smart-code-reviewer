from __future__ import annotations

import re
from typing import Dict, Optional


def _infer_error_type(error_message: str) -> str:
    if not error_message:
        return "ExecutionError"

    lines = error_message.strip().splitlines()
    if not lines:
        return "ExecutionError"

    last_line = lines[-1]
    if ":" in last_line:
        return last_line.split(":", 1)[0].strip() or "ExecutionError"
    return "ExecutionError"


def _friendly_explanation(error_type: str) -> str:
    mapping = {
        "SyntaxError": "Python could not understand the structure of one line.",
        "IndentationError": "The indentation is inconsistent for a Python block.",
        "TabError": "Tabs and spaces are mixed in indentation.",
        "NameError": "A name was used before being defined.",
        "TypeError": "Two values are being used in an incompatible way.",
        "ImportError": "Python could not import something requested.",
        "ModuleNotFoundError": "A required module is missing.",
        "IndexError": "A list index was used outside the valid range.",
        "AttributeError": "An object was used with a missing method or attribute.",
        "ValueError": "A value has the correct type but invalid content.",
        "KeyError": "A dictionary key was accessed but does not exist.",
        "ZeroDivisionError": "Division by zero was attempted.",
    }
    return mapping.get(error_type, "Python raised an error while running your code.")


def _concept(error_type: str, error_line: Optional[int]) -> str:
    line_hint = f" around line {error_line}" if error_line else ""
    mapping = {
        "SyntaxError": f"Fix punctuation or structure{line_hint}.",
        "IndentationError": "Use consistent indentation (4 spaces).",
        "TabError": "Use only spaces for indentation.",
        "NameError": "Define variables before using them.",
        "TypeError": "Convert values to compatible types before combining them.",
        "ImportError": "Check package/module names and installation.",
        "ModuleNotFoundError": "Install the missing module in your environment.",
    }
    return mapping.get(error_type, "Start by fixing the first traceback error and rerun.")


def explain_error(code: str, error_message: str, error_line: Optional[int]) -> Dict[str, object]:
    _ = code  # reserved for future richer explanations
    resolved_error_message = str(error_message or "Unknown error")
    error_type = _infer_error_type(resolved_error_message)

    fix_available = error_type in {
        "SyntaxError",
        "IndentationError",
        "TabError",
        "NameError",
        "TypeError",
        "ImportError",
        "ModuleNotFoundError",
        "IndexError",
        "AttributeError",
        "ValueError",
        "KeyError",
        "ZeroDivisionError",
    }

    return {
        "explanation": _friendly_explanation(error_type),
        "concept": _concept(error_type, error_line),
        "fix_available": fix_available,
    }
