from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.models.database import init_db
from app.routers import scan, fines

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    print(f"🚗 {settings.app_name} started!")
    print(f"📡 External API: {settings.external_api_url}")
    print(f"⏱️  Cache cooldown: {settings.cache_cooldown_min} minutes")
    yield
    # Shutdown
    print("👋 Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="Real-time car plate scanning system for road tax and insurance verification",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Include routers
app.include_router(scan.router, prefix="/api", tags=["Scanning"])
app.include_router(fines.router, prefix="/api", tags=["Fines"])


@app.get("/")
async def root(request: Request):
    """Serve the main dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "scan_interval": settings.scan_interval_ms,
            "cache_cooldown": settings.cache_cooldown_min
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}

