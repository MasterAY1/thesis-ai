from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import traceback
from services.extraction import extract_text
from services.evaluation import evaluate_thesis

router = APIRouter()

# Temporary storage for uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/evaluate")
async def evaluate_document(file: UploadFile = File(...)):
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")
        
    # Set a 15MB upload limit (Railway production safety)
    MAX_FILE_SIZE = 15 * 1024 * 1024
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 15MB.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    try:
        # 1. Save the file temporarily
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Extract Text
        extracted_text = extract_text(file_path)
        
        if not extracted_text:
            raise HTTPException(status_code=500, detail="Failed to extract text from file.")
            
        # Log extraction length for debugging
        print(f"DEBUG: Successfully extracted {len(extracted_text)} characters from {file.filename}")
            
        # 3. Evaluate Text
        evaluation_result = evaluate_thesis(extracted_text)
        
        return {
            "status": "success",
            "filename": file.filename,
            "extracted_length": len(extracted_text),
            "results": evaluation_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)

