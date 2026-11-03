"""
SQLAlchemy database models for forecasting entities.
Entities: ModelVersion, ForecastRun, ForecastPoint, EvaluationMetric, DataQualityEvent.
"""
import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    order = Column(String(50), nullable=False)
    seasonal_order = Column(String(50), nullable=False)
    window_type = Column(String(50), nullable=False)
    window_size = Column(Integer, nullable=False)
    transform = Column(String(50), nullable=False)
    is_approved = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    runs = relationship("ForecastRun", back_populates="model_version")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id = Column(String(100), primary_key=True)  # e.g., run_20261102_120000_abc123
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    trigger_type = Column(String(50), default="api_request")
    status = Column(String(50), nullable=False)  # SUCCESS, FAILED
    execution_time_ms = Column(Integer, nullable=False)
    training_cutoff = Column(String(50), nullable=False)
    forecast_origin = Column(String(50), nullable=False)
    forecast_horizon = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    model_version = relationship("ModelVersion", back_populates="runs")
    points = relationship("ForecastPoint", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("EvaluationMetric", back_populates="run", cascade="all, delete-orphan")


class ForecastPoint(Base):
    __tablename__ = "forecast_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), ForeignKey("forecast_runs.id"), nullable=False)
    month = Column(String(20), nullable=False)
    point_forecast = Column(Float, nullable=False)
    lower_80 = Column(Float, nullable=False)
    upper_80 = Column(Float, nullable=False)
    lower_95 = Column(Float, nullable=False)
    upper_95 = Column(Float, nullable=False)

    run = relationship("ForecastRun", back_populates="points")


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), ForeignKey("forecast_runs.id"), nullable=True)
    evaluation_set = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=False)
    mae = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    smape = Column(Float, nullable=False)
    mase = Column(Float, nullable=False)
    bias = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    run = relationship("ForecastRun", back_populates="metrics")


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    event_type = Column(String(100), nullable=False)  # e.g., GAP_ANOMALY, OUTLIER, STRUCTURAL_SHIFT
    severity = Column(String(50), nullable=False)    # INFO, WARNING, CRITICAL
    description = Column(Text, nullable=False)
    affected_range = Column(String(100), nullable=True)
