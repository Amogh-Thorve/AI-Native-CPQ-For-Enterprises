from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.app.core.config import settings
from backend.app.core.exceptions import register_exception_handlers

# Import domain modules routers
from backend.app.domains.auth import router as auth_router
from backend.app.domains.customer import router as customer_router
from backend.app.domains.catalog import router as catalog_router
from backend.app.domains.pricing import router as pricing_router
from backend.app.domains.configuration import router as configuration_router
from backend.app.domains.quotes import router as quotes_router
from backend.app.domains.approval import router as approval_router
from backend.app.domains.document import router as document_router
from backend.app.domains.email import router as email_router
from backend.app.domains.ai import router as ai_router
from backend.app.domains.integrations import router as integrations_router
from backend.app.domains.analytics import router as analytics_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise-grade modular monolith CPQ Platform with AI-assisted workflows and Salesforce CRM sync.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Set up CORS middleware for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server url
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register central error handling handlers
register_exception_handlers(app)

# Ensure directory for proposal PDFs exists and mount static files route
os.makedirs("static/documents", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register domain sub-routers under the central api/v1 route
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(customer_router, prefix=settings.API_V1_STR)
app.include_router(catalog_router, prefix=settings.API_V1_STR)
app.include_router(pricing_router, prefix=settings.API_V1_STR)
app.include_router(configuration_router, prefix=settings.API_V1_STR)
app.include_router(quotes_router, prefix=settings.API_V1_STR)
app.include_router(approval_router, prefix=settings.API_V1_STR)
app.include_router(document_router, prefix=settings.API_V1_STR)
app.include_router(email_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(integrations_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["system-monitoring"])
def health_check():
    """
    Core system monitoring health status check.
    """
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": "1.0.0"
    }
