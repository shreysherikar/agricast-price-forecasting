"""
Pytest configuration and environment fixtures.
Provides robust absolute paths regardless of current working directory.
"""
import os
import sys
from pathlib import Path
import pytest

# Add forecasting-project root to python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set MPLCONFIGDIR for matplotlib in tests
os.environ["MPLCONFIGDIR"] = str(project_root / ".mplconfig")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)


@pytest.fixture(scope="session")
def project_dir():
    return project_root


@pytest.fixture(scope="session")
def prices_csv_path(project_dir):
    return project_dir / "data" / "prices.csv"


@pytest.fixture(scope="session")
def outputs_dir(project_dir):
    return project_dir / "outputs"


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database(project_dir):
    """
    Ensure the database schema and baseline approved Stage 3 tables
    are initialized and seeded before test execution in clean environments.
    Guarantees that test suite executes cleanly on fresh extractions.
    """
    from src.database.session import init_db, get_db
    from src.database.service import seed_approved_stage3_data

    init_db()
    db = next(get_db())
    try:
        seed_approved_stage3_data(db, artifacts_dir=str(project_dir / "outputs"))
    finally:
        db.close()

