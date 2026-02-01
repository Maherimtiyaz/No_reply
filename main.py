from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from exceptions import setup_exception_handlers
from src.auth.router import router as auth_router
from src.email.router import router as email_router
from src.parsing.router import router as parsing_router

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

# Include routers
app.include_router(auth_router)
app.include_router(email_router)
app.include_router(parsing_router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "noreply-api",
        "version": "0.1.0"
    }
