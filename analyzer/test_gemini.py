from __future__ import annotations

import os
import sys

try:
    from google import genai
except Exception as exc:
    print(f"google-genai import failed: {exc}")
    print("Install dependency with: pip install google-genai")
    sys.exit(1)


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Fix this Python code: print(name/)"
    )

    print(response.text)


if __name__ == "__main__":
    main()
