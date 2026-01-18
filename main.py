from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from exceptions import setup_exception_handlers

app = FastAPI(
    title="NoReply API",
    description="Financial transaction ledger from email ingestion",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
setup_exception_handlers(app)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "noreply-api",
        "version": "0.1.0"
    }
