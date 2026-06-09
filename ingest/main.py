import sys
import os

# Ensure package root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from ingest.fao_ingest import ingest_fao
    from ingest.worldbank_ingest import ingest_worldbank
    from ingest.utils import get_logger
except ImportError:
    from fao_ingest import ingest_fao
    from worldbank_ingest import ingest_worldbank
    from utils import get_logger

LOG = get_logger("ingest.main")

def run_all() -> None:
    LOG.info("=== Starting Master Ingestion Pipeline ===")
    
    # 1. Run FAO Ingestion
    try:
        LOG.info("--- Step 1: Running FAO Ingestion (HuggingFace) ---")
        fao_rows = ingest_fao()
        LOG.info("FAO Ingestion complete: %s rows inserted/replaced", fao_rows)
    except Exception as e:
        LOG.exception("FAO Ingestion failed: %s", e)
        sys.exit(1)
        
    # 2. Run World Bank Ingestion
    try:
        LOG.info("--- Step 2: Running World Bank Ingestion (API) ---")
        wb_rows = ingest_worldbank()
        LOG.info("World Bank Ingestion complete: %s rows inserted/replaced", wb_rows)
    except Exception as e:
        LOG.exception("World Bank Ingestion failed: %s", e)
        sys.exit(1)
        
    LOG.info("=== Master Ingestion Pipeline Completed Successfully ===")

if __name__ == "__main__":
    run_all()
