"""
WHOOP Health Dashboard — FastAPI application entry point.

All endpoints require Bearer token authentication (API_SECRET env var).
"""

import os

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from routers import sleep, recovery, workouts, cycles, journal, summary

app = FastAPI(
    title="WHOOP Health Dashboard API",
    description="Personal health metrics from WHOOP, stored in Supabase.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Bearer token auth
# ---------------------------------------------------------------------------

_bearer = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> str:
    api_secret = os.environ.get("API_SECRET", "")
    if not api_secret or credentials.credentials != api_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(sleep.router, prefix="/sleep", tags=["sleep"], dependencies=[Security(verify_token)])
app.include_router(recovery.router, prefix="/recovery", tags=["recovery"], dependencies=[Security(verify_token)])
app.include_router(workouts.router, prefix="/workouts", tags=["workouts"], dependencies=[Security(verify_token)])
app.include_router(cycles.router, prefix="/cycles", tags=["cycles"], dependencies=[Security(verify_token)])
app.include_router(journal.router, prefix="/journal", tags=["journal"], dependencies=[Security(verify_token)])
app.include_router(summary.router, prefix="/summary", tags=["summary"], dependencies=[Security(verify_token)])


@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}
