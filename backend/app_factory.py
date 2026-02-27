"""
FastAPI Backend for Smart Code Reviewer
Handles /run and /ai-fix endpoints with proper OpenAI integration
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.execution_service import run_user_code
from utils.logging_config import configure_logging

# Import OpenAI
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# Configure logging
configure_logging(log_dir=os.getenv("LOG_DIR", "logs"))
LOGGER = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Smart Code Reviewer API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# ============ Request Models ============

class RunRequest(BaseModel):
    code: str


class AIFixRequest(BaseModel):
    code: str
    error: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None


class AIAssistRequest(BaseModel):
    code: str
    prompt: str
    error: Optional[str] = None


# ============ Helper Functions ============

def _extract_error_info(error_obj: Any) -> tuple:
    """Extract error_type, error_message, traceback from error object"""
    if error_obj is None:
        return "", "", ""
    
    if isinstance(error_obj, dict):
        error_type = str(error_obj.get("error_type", ""))
        error_message = str(error_obj.get("error_message", ""))
        traceback = str(error_obj.get("traceback", ""))
        return error_type, error_message, traceback
    
    if isinstance(error_obj, str):
        return "", error_obj, ""
    
    return "", str(error_obj), ""


def _clean_code(text: str) -> str:
    """Clean code from markdown blocks"""
    cleaned = (text or "").strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = max(fenced, key=len).strip()
    return cleaned.strip()


def _build_ai_fix_prompt(code: str, error_message: str, traceback: str) -> str:
    """Build the AI prompt exactly as specified"""
    return f"""You are a senior Python developer.
Fix the following Python code.
Return ONLY the full corrected Python code.
No explanations.

CODE:
{code}

ERROR:
{error_message}

TRACEBACK:
{traceback}"""


def _call_openai(prompt: str) -> tuple:
    """
    Call OpenAI API and return (success, response_text, error_message)
    """
    global OPENAI_API_KEY
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        LOGGER.error("OpenAI API key not configured")
        return False, "", "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
    
    if OpenAI is None:
        LOGGER.error("OpenAI package not installed")
        return False, "", "OpenAI package not installed"
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Try responses API first (newer)
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )
            raw_text = str(getattr(response, "output_text", "") or "")
            if raw_text.strip():
                LOGGER.info("OpenAI responses API succeeded")
                return True, raw_text, ""
        except Exception as e:
            LOGGER.warning(f"OpenAI responses API failed: {e}")
        
        # Fallback to chat completions
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a senior Python developer. Return ONLY valid Python code. No explanations, no markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        
        raw_text = (response.choices[0].message.content or "") if response.choices else ""
        if raw_text.strip():
            LOGGER.info("OpenAI chat API succeeded")
            return True, raw_text, ""
        
        return False, "", "Empty response from OpenAI"
        
    except Exception as e:
        error_msg = str(e)
        LOGGER.exception(f"OpenAI API error: {error_msg}")
        return False, "", f"OpenAI API failed: {error_msg}"


# ============ Routes ============

@app.get("/")
async def index():
    """Serve the main HTML page"""
    from fastapi.responses import FileResponse
    return FileResponse("templates/index.html")


@app.post("/run")
async def run_code(request: RunRequest):
    """
    Execute Python code and return execution result
    """
    LOGGER.info(f"/run request code_chars={len(request.code)}")
    
    if not request.code or not request.code.strip():
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "No code provided"}
        )
    
    try:
        result = run_user_code(request.code)
        return JSONResponse(content=result)
    except Exception as e:
        LOGGER.exception("Error running code")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@app.post("/ai-fix")
async def ai_fix(request: AIFixRequest):
    """
    Generate AI fix for code with error
    
    Expected payload:
    {
        "code": "current editor code",
        "error": { ... }  // optional error object
        // OR
        "error_type": "...",
        "error_message": "...",
        "traceback": "..."
    }
    
    Returns:
    {
        "success": true/false,
        "fixed_code": "corrected code" // if success
        "error": "error message" // if failed
    }
    """
    LOGGER.info(f"/ai-fix request code_chars={len(request.code)}")
    
    # Extract code
    code = str(request.code or "")
    if not code.strip():
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "No code provided", "fixed_code": ""}
        )
    
    # Extract error info from various possible formats
    error_type = ""
    error_message = ""
    traceback_text = ""
    
    # From error object (error field)
    if request.error and isinstance(request.error, dict):
        error_type = str(request.error.get("error_type", ""))
        error_message = str(request.error.get("error_message", ""))
        traceback_text = str(request.error.get("traceback", ""))
    
    # From direct fields (override if provided)
    if request.error_type:
        error_type = str(request.error_type)
    if request.error_message:
        error_message = str(request.error_message)
    if request.traceback:
        traceback_text = str(request.traceback)
    
    LOGGER.info(f"AI Fix: error_type={error_type}, error_message={error_message[:100] if error_message else ''}")
    
    #, return error If no error info
    if not error_message.strip() and not traceback_text.strip():
        return JSONResponse(
            content={
                "success": False, 
                "error": "No error provided. Run code first to detect errors.", 
                "fixed_code": ""
            }
        )
    
    # Build the AI prompt
    prompt = _build_ai_fix_prompt(code, error_message, traceback_text)
    
    # Call OpenAI
    success, raw_response, error_msg = _call_openai(prompt)
    
    if not success:
        LOGGER.error(f"OpenAI API failed: {error_msg}")
        return JSONResponse(
            content={
                "success": False,
                "error": error_msg,
                "fixed_code": ""
            }
        )
    
    # Clean the response
    fixed_code = _clean_code(raw_response)
    
    if not fixed_code.strip():
        LOGGER.warning("OpenAI returned empty fixed code")
        return JSONResponse(
            content={
                "success": False,
                "error": "No usable fix generated",
                "fixed_code": ""
            }
        )
    
    LOGGER.info(f"AI Fix succeeded, fixed_code_chars={len(fixed_code)}")
    return JSONResponse(
        content={
            "success": True,
            "fixed_code": fixed_code,
            "error": ""
        }
    )


@app.post("/ai-assist")
async def ai_assist(request: AIAssistRequest):
    """
    AI Tutor/Assistant endpoint
    """
    LOGGER.info(f"/ai-assist request code_chars={len(request.code)}, prompt_chars={len(request.prompt)}")
    
    # This would need similar implementation for full AI assist
    # For now, return a placeholder
    return JSONResponse(
        content={
            "assistant_message": "AI Tutor is being updated. Please try again.",
            "suggestions": [],
            "generated_code": ""
        }
    )


# ============ Entry Point ============

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

