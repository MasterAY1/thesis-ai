"""
ThesisAI API Routes — Optimized v3

Optimizations applied:
  - POST /api/evaluate now accepts evaluation_mode ("fast"|"deep").
  - Document hash caching: same file + mode → instant cached result.
  - Richer job store: per-section section_progress dict.
  - GET /api/progress/{job_id}: lightweight 2s polling endpoint (no results payload).
  - Deferred PDF generation: report is generated on demand, not blocking evaluation.
  - Performance timings returned when ?debug=true.

Existing endpoints preserved (backward compatible):
  GET  /api/ping
  POST /api/evaluate   — returns job_id immediately
  GET  /api/status/{job_id}
  POST /api/rewrite
  POST /api/report
  GET  /api/rubrics
  GET  /api/styles
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import os
import uuid
import shutil
import traceback
import threading
import logging
import io
from typing import Optional

from services.extraction import extract_text
from services.evaluation import evaluate_thesis
from services.rewrite_engine import rewrite_issue
from services.report_generator import generate_pdf_report
from services.feedback_styles import list_styles
from services.rubric_loader import list_available_rubrics
from services.cache import get_cache

logger = logging.getLogger("thesis_ai.routes")

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory job store (keyed by job_id)
jobs = {}


# ── Schemas ────────────────────────────────────────────────────────────────────

class RewriteRequest(BaseModel):
    issue_title: str
    issue_description: str
    section_name: str
    context: str = ""
    feedback_style: str = "friendly_lecturer"


# ── Health / ping ──────────────────────────────────────────────────────────────

@router.get("/ping")
def ping_server():
    return {"message": "pong"}


# ── Meta endpoints ─────────────────────────────────────────────────────────────

@router.get("/styles")
def get_feedback_styles():
    """Returns all available feedback style options for the frontend dropdown."""
    return {"styles": list_styles()}


@router.get("/rubrics")
def get_available_rubrics():
    """Returns all available institution rubric codes."""
    return {"institutions": list_available_rubrics()}


@router.get("/cache/stats")
def cache_stats():
    """Return evaluation cache statistics (for monitoring)."""
    return get_cache().stats()


# ── Async Evaluation ───────────────────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate_document(
    file: UploadFile = File(...),
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
    evaluation_mode: str = "fast",   # NEW: "fast" | "deep"
    debug: bool = False,
):
    """
    Accept a thesis file and start evaluation in the background.
    Returns a job_id immediately. Poll /api/progress/{job_id} or
    /api/status/{job_id} for results.

    evaluation_mode:
        "fast"  — Gemini Flash only, parallel sections, no cross-validation.
                  Target: 30–90 seconds.
        "deep"  — Full pipeline with cross-section validation.
                  Target: 2–4 minutes.
    """
    if evaluation_mode not in ("fast", "deep"):
        raise HTTPException(
            status_code=400,
            detail="evaluation_mode must be 'fast' or 'deep'."
        )

    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    MAX_FILE_SIZE = 15 * 1024 * 1024
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 15MB.")

    job_id    = str(uuid.uuid4())[:8]
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    try:
        # Read file bytes for hash check
        file_bytes = await file.read()

        # ── Document hash cache check ──────────────────────────────────────────
        cache = get_cache()
        cache_key = cache.make_key(file_bytes, evaluation_mode, institution)
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            logger.info(f"Cache HIT for job {job_id}: returning cached result instantly")
            return {
                "status":    "completed",
                "job_id":    job_id,
                "cached":    True,
                "message":   "Returned from cache. Same document already evaluated.",
                "results": {
                    "status":           "success",
                    "filename":         file.filename,
                    "extracted_length": cached_result.get("_extracted_length", 0),
                    "results":          cached_result,
                    "cached":           True,
                },
            }

        # ── Save file and extract text ─────────────────────────────────────────
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)

        extracted_text = extract_text(file_path)

        if not extracted_text:
            raise HTTPException(status_code=500, detail="Failed to extract text from file.")

        logger.info(f"Job {job_id}: Extracted {len(extracted_text)} chars from {file.filename}")

        jobs[job_id] = {
            "status":           "processing",
            "filename":         file.filename,
            "extracted_length": len(extracted_text),
            "progress":         "Starting evaluation…",
            "section_progress": {},
            "detected_sections": [],
            "evaluation_mode":  evaluation_mode,
            "results":          None,
            "error":            None,
            "_cache_key":       cache_key,
            "_extracted_length": len(extracted_text),
        }

        thread = threading.Thread(
            target=_run_evaluation,
            args=(job_id, extracted_text, file_path, institution, feedback_style, evaluation_mode, debug),
            daemon=True,
        )
        thread.start()

        return {
            "status":  "accepted",
            "job_id":  job_id,
            "message": f"Evaluation started ({evaluation_mode} mode). Poll /api/progress/{{job_id}} for live updates.",
            "evaluation_mode": evaluation_mode,
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
    evaluation_mode: str = "fast",
    debug: bool = False,
):
    """
    Background worker — runs the full async evaluation pipeline in a thread.
    Uses asyncio.run() to create a fresh event loop for the async pipeline.
    """
    try:
        import asyncio
        logger.info(
            f"Job {job_id}: Starting {evaluation_mode} evaluation "
            f"(style={feedback_style}, institution={institution})"
        )

        # Pass the job dict as progress_store so the pipeline can update it live
        progress_store = jobs[job_id]

        result = evaluate_thesis(
            text=text,
            institution=institution,
            feedback_style=feedback_style,
            evaluation_mode=evaluation_mode,
            progress_store=progress_store,
            debug=debug,
        )

        # Tag with extracted length for cache
        result["_extracted_length"] = jobs[job_id]["_extracted_length"]

        # Store in cache so next identical upload is instant
        cache_key = jobs[job_id].get("_cache_key")
        if cache_key:
            get_cache().set(cache_key, result)

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


# ── Progress polling (lightweight, 2s interval) ────────────────────────────────

@router.get("/progress/{job_id}")
def get_job_progress(job_id: str):
    """
    Lightweight progress endpoint — poll every 2 seconds for live section updates.
    Returns section_progress dict WITHOUT the full results payload.
    Frontend uses this during evaluation to show section-by-section progress.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]

    return {
        "job_id":           job_id,
        "status":           job["status"],
        "progress":         job["progress"],
        "evaluation_mode":  job.get("evaluation_mode", "fast"),
        "section_progress": job.get("section_progress", {}),
        "detected_sections": job.get("detected_sections", []),
    }


# ── Status polling (full results on completion) ────────────────────────────────

@router.get("/status/{job_id}")
def get_job_status(job_id: str):
    """
    Poll this endpoint to check evaluation progress and receive final results.
    For live section progress during evaluation, use /api/progress/{job_id} instead.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]
    response = {
        "job_id":           job_id,
        "status":           job["status"],
        "progress":         job["progress"],
        "filename":         job["filename"],
        "evaluation_mode":  job.get("evaluation_mode", "fast"),
        "section_progress": job.get("section_progress", {}),
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


# ── Rewrite Engine ─────────────────────────────────────────────────────────────

@router.post("/rewrite")
async def rewrite_section(payload: RewriteRequest):
    """
    AI 'Fix This For Me' — generates an academic rewrite for a specific deduction.
    Body: issue_title, issue_description, section_name, context, feedback_style
    Response: { "rewrite": "...", "tips": ["..."] }
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


# ── PDF Report (deferred, on-demand) ──────────────────────────────────────────

@router.post("/report")
async def download_report(evaluation_data: dict):
    """
    Generate and stream a PDF evaluation report on demand.
    PDF generation is NOT done during evaluation — only when this endpoint is called.

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
