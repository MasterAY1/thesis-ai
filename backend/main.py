import os
import uuid
import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s"
)
logger = logging.getLogger("thesis_ai")

app = FastAPI(title="ThesisAI API", description="Production Backend for Thesis Evaluation")

# Request ID Middleware for tracing
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    # Add correlation_id to logger context
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.correlation_id = request_id
        return record
        
    logging.setLogRecordFactory(record_factory)
    
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)
    
    logger.info(f"Completed request: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}s")
    
    # Restore log factory
    logging.setLogRecordFactory(old_factory)
    return response

# Allow requests from Next.js frontend (local and production)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [frontend_url]
if frontend_url != "http://localhost:3000":
    allowed_origins.append("http://localhost:3000") # Always allow local dev

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/health")
def health_check():
    """Railway health check endpoint"""
    return {"status": "ok", "service": "thesis_ai_backend"}

@app.get("/")
def read_root():
    return {"message": "ThesisAI Backend is running."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
