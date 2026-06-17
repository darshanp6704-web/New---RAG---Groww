import os
import sys
import time
import datetime
import logging
import argparse

# Append parent directory to sys.path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.ingestion.fetch import main as fetch_main
from src.ingestion.parse import main as parse_main
from src.ingestion.vector_store import main as vector_store_main

# Configure Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "scheduler.log")

# Setup Logging to both Console and File
logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

# Avoid adding duplicate handlers if the script is imported or re-run
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def run_pipeline():
    """
    Sequentially runs the fetch, parse, and vector_store steps.
    """
    logger.info("==================================================")
    logger.info("Starting scheduled ingestion pipeline run.")
    logger.info("==================================================")
    
    try:
        logger.info("STEP 1: Fetching latest Groww HTML files...")
        fetch_main()
        logger.info("STEP 1: Fetch completed successfully.")
        
        logger.info("STEP 2: Parsing HTML files into structured JSON...")
        parse_main()
        logger.info("STEP 2: Parse completed successfully.")
        
        logger.info("STEP 3: Indexing parsed data into ChromaDB...")
        vector_store_main()
        logger.info("STEP 3: Indexing completed successfully.")
        
        logger.info("==================================================")
        logger.info("Ingestion pipeline completed successfully.")
        logger.info("==================================================")
    except Exception as e:
        logger.error(f"Ingestion pipeline execution failed: {e}", exc_info=True)
        logger.info("==================================================")

def get_next_run_delay():
    """
    Calculates the target datetime for the next 10:00 AM IST execution 
    and returns the timezone-aware target datetime and the delay in seconds.
    """
    # Indian Standard Time timezone offset: UTC +5:30
    tz_ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(tz_ist)
    
    # Target execution time: 10:00 AM IST today
    target = now.replace(hour=10, minute=0, second=0, microsecond=0)
    
    # If the target time for today has already passed, set it to tomorrow at 10:00 AM IST
    if now >= target:
        target += datetime.timedelta(days=1)
        
    delay = (target - now).total_seconds()
    return target, delay

def main():
    parser = argparse.ArgumentParser(description="Ingestion Pipeline Scheduler for Mutual Fund FAQ Assistant")
    parser.add_argument("--now", action="store_true", help="Execute the ingestion pipeline immediately and exit.")
    args = parser.parse_args()
    
    if args.now:
        logger.info("Dry-run flag (--now) detected. Executing pipeline immediately...")
        run_pipeline()
        logger.info("Dry-run execution completed. Exiting.")
        return
        
    logger.info("Starting persistent scheduler service. Target run time is 10:00 AM IST daily.")
    
    while True:
        target_time, delay = get_next_run_delay()
        logger.info(f"Next scheduled run: {target_time.strftime('%Y-%m-%d %H:%M:%S %Z')} (in {delay/3600:.2f} hours)")
        
        try:
            # Sleep until the target run time
            time.sleep(delay)
            run_pipeline()
        except KeyboardInterrupt:
            logger.info("Scheduler service stopped by user (KeyboardInterrupt). Exiting.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
            logger.info("Retrying scheduler loop in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    main()
