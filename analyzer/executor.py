import subprocess
import tempfile
import os
import re

def execute_code(code: str):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as temp:
        temp.write(code)
        filename = temp.name

    result = subprocess.run(
        ["python3", filename],
        capture_output=True,
        text=True
    )

    os.remove(filename)

    if result.returncode == 0:
        return {
            "success": True,
            "output": result.stdout,
            "error": None
        }

    error_text = result.stderr

    # Extract line number
    line_match = re.search(r'line (\d+)', error_text)
    error_line = int(line_match.group(1)) if line_match else None

    # Extract error type
    error_type_match = re.search(r'(\w+Error):', error_text)
    error_type = error_type_match.group(1) if error_type_match else "Error"

    # Extract error message
    error_message = error_text.split("\n")[-2]

    return {
        "success": False,
        "output": None,
        "error": error_text,
        "error_line": error_line,
        "error_type": error_type,
        "error_message": error_message
    }
