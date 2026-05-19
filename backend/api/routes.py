"""
ThesisAI API Routes — Async Job Queue Architecture

The evaluation process takes several minutes (12+ AI calls).
Render's free tier has a 30-second request timeout, so we can't
run the evaluation synchronously inside a single POST request.

Solution: Async job queue.
  1. POST /api/evaluate → saves file, starts background thread, returns job_id instantly
  2. GET /api/status/{job_id} → frontend polls this every 5s until done
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import os
import uuid
import shutil
import traceback
import threading
import logging
from services.extraction import extract_text
from services.evaluation import evaluate_thesis

logger = logging.getLogger("thesis_ai.routes")

router = APIRouter()

# Temporary storage for uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory job store (for free tier — no database needed)
# In production, replace with Redis or a database
jobs = {}


@router.get("/ping")
def ping_server():
    return {"message": "pong"}


@router.post("/evaluate")
async def evaluate_document(file: UploadFile = File(...)):
    """
    Accept a thesis file and start evaluation in the background.
    Returns a job_id immediately (within 2 seconds).
    """
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    # Set a 15MB upload limit
    MAX_FILE_SIZE = 15 * 1024 * 1024
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 15MB.")

    # Generate a unique job ID
    job_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    try:
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Extract text immediately (fast — takes 1-2 seconds)
        extracted_text = extract_text(file_path)

        if not extracted_text:
            raise HTTPException(status_code=500, detail="Failed to extract text from file.")

        logger.info(f"Job {job_id}: Extracted {len(extracted_text)} chars from {file.filename}")

        # Store job as pending
        jobs[job_id] = {
            "status": "processing",
            "filename": file.filename,
            "extracted_length": len(extracted_text),
            "progress": "Starting AI evaluation...",
            "results": None,
            "error": None,
        }

        # Start evaluation in a background thread
        thread = threading.Thread(
            target=_run_evaluation,
            args=(job_id, extracted_text, file_path),
            daemon=True,
        )
        thread.start()

        # Return immediately with the job ID
        return {
            "status": "accepted",
            "job_id": job_id,
            "message": "Evaluation started. Poll /api/status/{job_id} for results.",
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        # Cleanup on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


def _run_evaluation(job_id: str, text: str, file_path: str):
    """Background worker that runs the full evaluation pipeline."""
    try:
        logger.info(f"Job {job_id}: Starting evaluation...")
        jobs[job_id]["progress"] = "Splitting thesis into sections..."

        result = evaluate_thesis(text)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = "Evaluation complete."
        jobs[job_id]["results"] = result
        logger.info(f"Job {job_id}: Evaluation completed successfully.")

    except Exception as e:
        logger.error(f"Job {job_id}: Evaluation failed: {e}")
        traceback.print_exc()
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = "Evaluation failed."
        jobs[job_id]["error"] = str(e)

    finally:
        # Cleanup uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)


@router.get("/status/{job_id}")
def get_job_status(job_id: str):
    """
    Poll this endpoint to check evaluation progress.
    Frontend calls this every 5 seconds until status is 'completed' or 'failed'.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]

    response = {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "filename": job["filename"],
    }

    if job["status"] == "completed":
        response["results"] = {
            "status": "success",
            "filename": job["filename"],
            "extracted_length": job["extracted_length"],
            "results": job["results"],
        }
        # Clean up job from memory after delivering results
        del jobs[job_id]

    elif job["status"] == "failed":
        response["error"] = job["error"]
        del jobs[job_id]

    return response
