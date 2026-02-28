from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.core.config import settings
from app.api import auth, sources, rag, draft

load_dotenv()

app = FastAPI(
    title="ResearchFlow API",
    description="AI-powered research assistant",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(sources.router)
app.include_router(rag.router)
app.include_router(draft.router)

@app.get("/")
async def root():
    return {
        "message": "ResearchFlow API is running!",
        "version": "1.0.0",
        "status": "healthy",
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}