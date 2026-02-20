import subprocess
import tempfile
import os

def execute_code(code: str):
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as temp:
            temp.write(code)
            temp_filename = temp.name

        # Execute code
        result = subprocess.run(
            ["python3", temp_filename],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Remove temp file
        os.remove(temp_filename)

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout,
                "error": None
            }
        else:
            return {
                "success": False,
                "output": None,
                "error": result.stderr
            }

    except Exception as e:
        return {
            "success": False,
            "output": None,
            "error": str(e)
        }
