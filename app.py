"""
Smart Code Reviewer - FastAPI Backend
Run this file to start the server: python app.py
"""

import os
import sys

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app_factory import app

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    
    print(f"Starting Smart Code Reviewer on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, debug=debug)

