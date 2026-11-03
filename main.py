"""
Main FastAPI application entrypoint.
Configures CORS, lifespan startup/shutdown, database initialization,
and root health endpoints.
"""
import os
import sys
import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure forecasting-project is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.api.routes import router as api_router, get_artifacts_dir, trigger_forecast_run, get_forecast
from src.api.schemas import HealthResponse, ForecastRunResponse, ForecastResponse
from src.api.security import verify_api_key, rate_limit_pipeline
from src.database.session import init_db, get_db
from src.database.service import seed_approved_stage3_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler: initialize DB and seed approved baseline data on startup."""
    init_db()
    db = next(get_db())
    try:
        seed_approved_stage3_data(db, artifacts_dir=str(get_artifacts_dir()))
    finally:
        db.close()
    yield


app = FastAPI(
    title="Monthly Price Forecasting & Decision Support API",
    description=(
        "Production-oriented forecasting API for commodity price movements. "
        "Provides 12-month operational forecasts, prediction intervals, holdout metrics, "
        "model provenance, and automated data quality diagnostics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configurable CORS origins through environment variables
cors_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:5173")
if cors_env.strip() == "*":
    cors_allowed_origins = ["*"]
else:
    cors_allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router)

# Aliases for root-level paths (/forecast/run and /forecast)
from fastapi import APIRouter
root_alias = APIRouter()
root_alias.add_api_route(
    "/forecast/run",
    trigger_forecast_run,
    methods=["POST"],
    response_model=ForecastRunResponse,
    dependencies=[Depends(verify_api_key), Depends(rate_limit_pipeline)],
)
root_alias.add_api_route(
    "/forecast",
    get_forecast,
    methods=["GET"],
    response_model=ForecastResponse,
)
app.include_router(root_alias)


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, summary="Service Health & Artifact Availability Check")
def get_health(db: Session = Depends(get_db)):
    """
    Check overall service health, database connectivity, and forecast artifact availability.
    """
    artifacts_dir = get_artifacts_dir()
    required_artifacts = [
        artifacts_dir / "final_forecast.csv",
        artifacts_dir / "forecast_metrics.csv",
        artifacts_dir / "holdout_predictions.csv",
    ]
    artifacts_ok = all(p.exists() for p in required_artifacts)

    # Check DB connectivity
    db_ok = True
    try:
        db.execute(text("SELECT 1")).scalar()
    except Exception:
        db_ok = False

    return HealthResponse(
        status="HEALTHY" if artifacts_ok else "DEGRADED",
        version="1.0.0",
        database_connected=db_ok,
        artifacts_available=artifacts_ok,
        model_loaded=True,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
