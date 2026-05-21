"""
ThesisAI API Routes — Phase 2

New endpoints (Phase 2):
  POST /api/rewrite          — AI "Fix This For Me" rewrite for a single deduction
  GET  /api/report/{job_id}  — Download PDF evaluation report
  GET  /api/rubrics          — List all available institutions/rubrics
  GET  /api/styles           — List all available feedback styles

Existing endpoints (preserved):
  GET  /api/ping
  POST /api/evaluate         — Async job queue (returns job_id)
  GET  /api/status/{job_id}  — Poll for job result
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import os
import uuid
import shutil
import traceback
import threading
import logging
import io
from services.extraction import extract_text
from services.evaluation import evaluate_thesis
from services.rewrite_engine import rewrite_issue
from services.report_generator import generate_pdf_report
from services.feedback_styles import list_styles
from services.rubric_loader import list_available_rubrics

logger = logging.getLogger("thesis_ai.routes")

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory job store (keyed by job_id)
jobs = {}


# ── Schemas ───────────────────────────────────────────────────────────────────

class RewriteRequest(BaseModel):
    issue_title: str
    issue_description: str
    section_name: str
    context: str = ""
    feedback_style: str = "friendly_lecturer"


# ── Health / ping ─────────────────────────────────────────────────────────────

@router.get("/ping")
def ping_server():
    return {"message": "pong"}


# ── Meta endpoints ────────────────────────────────────────────────────────────

@router.get("/styles")
def get_feedback_styles():
    """Returns all available feedback style options for the frontend dropdown."""
    return {"styles": list_styles()}


@router.get("/rubrics")
def get_available_rubrics():
    """Returns all available institution rubric codes."""
    return {"institutions": list_available_rubrics()}


# ── Async Evaluation ──────────────────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate_document(
    file: UploadFile = File(...),
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
):
    """
    Accept a thesis file and start evaluation in the background.
    Returns a job_id immediately. Poll /api/status/{job_id} for results.
    """
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    MAX_FILE_SIZE = 15 * 1024 * 1024
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 15MB.")

    job_id    = str(uuid.uuid4())[:8]
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_text = extract_text(file_path)

        if not extracted_text:
            raise HTTPException(status_code=500, detail="Failed to extract text from file.")

        logger.info(f"Job {job_id}: Extracted {len(extracted_text)} chars from {file.filename}")

        jobs[job_id] = {
            "status":           "processing",
            "filename":         file.filename,
            "extracted_length": len(extracted_text),
            "progress":         "Starting AI evaluation...",
            "results":          None,
            "error":            None,
        }

        thread = threading.Thread(
            target=_run_evaluation,
            args=(job_id, extracted_text, file_path, institution, feedback_style),
            daemon=True,
        )
        thread.start()

        return {
            "status":  "accepted",
            "job_id":  job_id,
            "message": "Evaluation started. Poll /api/status/{job_id} for results.",
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


def _run_evaluation(
    job_id: str,
    text: str,
    file_path: str,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
):
    """Background worker — runs the full evaluation pipeline."""
    try:
        logger.info(f"Job {job_id}: Starting evaluation (style={feedback_style}, institution={institution})")
        jobs[job_id]["progress"] = "Detecting document type..."

        result = evaluate_thesis(text, institution=institution, feedback_style=feedback_style)

        jobs[job_id]["status"]   = "completed"
        jobs[job_id]["progress"] = "Evaluation complete."
        jobs[job_id]["results"]  = result
        logger.info(f"Job {job_id}: Completed successfully.")

    except Exception as e:
        logger.error(f"Job {job_id}: Failed — {e}")
        traceback.print_exc()
        jobs[job_id]["status"]   = "failed"
        jobs[job_id]["progress"] = "Evaluation failed."
        jobs[job_id]["error"]    = str(e)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.get("/status/{job_id}")
def get_job_status(job_id: str):
    """Poll this endpoint every 5s to check evaluation progress."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]
    response = {
        "job_id":   job_id,
        "status":   job["status"],
        "progress": job["progress"],
        "filename": job["filename"],
    }

    if job["status"] == "completed":
        response["results"] = {
            "status":           "success",
            "filename":         job["filename"],
            "extracted_length": job["extracted_length"],
            "results":          job["results"],
        }
        del jobs[job_id]

    elif job["status"] == "failed":
        response["error"] = job["error"]
        del jobs[job_id]

    return response


# ── Rewrite Engine ────────────────────────────────────────────────────────────

@router.post("/rewrite")
async def rewrite_section(payload: RewriteRequest):
    """
    AI 'Fix This For Me' — generates an academic rewrite for a specific deduction.

    Body:
        issue_title, issue_description, section_name, context, feedback_style

    Response:
        { "rewrite": "...", "tips": ["..."] }
    """
    if not payload.issue_title or not payload.section_name:
        raise HTTPException(status_code=400, detail="issue_title and section_name are required.")

    try:
        result = rewrite_issue(
            issue_title=payload.issue_title,
            issue_description=payload.issue_description,
            section_name=payload.section_name,
            context=payload.context,
            feedback_style=payload.feedback_style,
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── PDF Report ────────────────────────────────────────────────────────────────

@router.post("/report")
async def download_report(evaluation_data: dict):
    """
    Generate and stream a PDF evaluation report.

    Body: The full evaluation result JSON (same structure stored in localStorage).
    Response: PDF file download.
    """
    try:
        filename = evaluation_data.get("filename", "thesis")
        results  = evaluation_data.get("results", evaluation_data)

        pdf_bytes = generate_pdf_report(results, filename=filename)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="ThesisAI_Report_{filename}.pdf"',
            },
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
