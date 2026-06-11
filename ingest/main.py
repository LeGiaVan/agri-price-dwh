import sys
import os

# Ensure package root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from ingest.worldbank_ingest import ingest_worldbank
    from ingest.yf_ingest import ingest as ingest_yf
    from ingest.utils import get_logger
except ImportError:
    from worldbank_ingest import ingest_worldbank
    from yf_ingest import ingest as ingest_yf
    from utils import get_logger

LOG = get_logger("ingest.main")


def _run_step(step_name: str, ingest_func) -> None:
    try:
        LOG.info("--- Running %s ---", step_name)
        ingest_func()
        LOG.info("%s complete", step_name)
    except Exception as e:
        LOG.exception("%s failed: %s", step_name, e)
        sys.exit(1)


def run_all() -> None:
    LOG.info("=== Starting Master Ingestion Pipeline ===")

    _run_step("World Bank Ingestion", ingest_worldbank)
    _run_step("Yahoo Finance Ingestion", ingest_yf)

    LOG.info("=== Master Ingestion Pipeline Completed Successfully ===")

if __name__ == "__main__":
    run_all()
