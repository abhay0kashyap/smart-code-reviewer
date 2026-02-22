import subprocess
import tempfile
import re
import sys


def execute_code(code):

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False
        ) as f:

            f.write(code)
            filename = f.name

        result = subprocess.run(
            [sys.executable, filename],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:

            return {
                "success": True,
                "output": result.stdout,
                "error_line": None,
                "error_message": None,
                "error_type": None
            }

        else:

            error_text = result.stderr

            line_number = None
            traceback_matches = re.findall(r'line\s+(\d+)', error_text)
            if traceback_matches:
                line_number = int(traceback_matches[-1])

            last_line = error_text.strip().splitlines()[-1] if error_text.strip() else ""
            if ":" in last_line:
                error_type = last_line.split(":", 1)[0].strip()
            else:
                error_type = "ExecutionError"

            return {
                "success": False,
                "output": None,
                "error_line": line_number,
                "error_message": error_text,
                "error_type": error_type
            }

    except Exception as e:

        return {
            "success": False,
            "output": None,
            "error_line": None,
            "error_message": str(e),
            "error_type": "ExecutionError"
        }
