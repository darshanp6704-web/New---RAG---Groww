import os
import json
import time
import datetime
import logging
import re
import requests

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
SOURCES_FILE = os.path.join(os.path.dirname(__file__), "sources.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "manifest.json")

# Browser headers to bypass basic blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

def slugify(text):
    """
    Generate clean filenames from scheme names.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text

def download_url(url, max_retries=3, delay=3):
    """
    Download a URL with retry and timeout.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching {url} (Attempt {attempt}/{max_retries})...")
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching {url} on attempt {attempt}: {e}")
            if attempt < max_retries:
                sleep_time = delay * attempt
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logger.error(f"Failed to fetch {url} after {max_retries} attempts.")
                raise e

def main():
    if not os.path.exists(SOURCES_FILE):
        logger.error(f"Sources file not found at: {SOURCES_FILE}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(SOURCES_FILE, "r") as f:
        sources = json.load(f)

    logger.info(f"Found {len(sources)} sources to fetch.")
    manifest = {}
    
    # Load existing manifest if it exists
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, "r") as fm:
                manifest = json.load(fm)
        except Exception as e:
            logger.warning(f"Failed to load existing manifest: {e}")

    for idx, source in enumerate(sources):
        url = source.get("url")
        scheme_name = source.get("scheme_name")
        
        if not url or not scheme_name:
            logger.warning(f"Invalid entry at index {idx}, skipping.")
            continue
            
        slug = slugify(scheme_name)
        filename = f"{slug}.html"
        file_path = os.path.join(OUTPUT_DIR, filename)
        
        try:
            # Download the page
            html_content = download_url(url)
            
            # Record current timestamp
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Prepend timestamp comment to raw HTML file
            timestamp_comment = f"<!-- Fetched at: {timestamp} -->\n"
            full_content = timestamp_comment + html_content
            
            with open(file_path, "w", encoding="utf-8") as f_out:
                f_out.write(full_content)
                
            # Update manifest
            manifest[slug] = {
                "url": url,
                "scheme_name": scheme_name,
                "amc_name": source.get("amc_name"),
                "filename": filename,
                "fetch_timestamp": timestamp
            }
            logger.info(f"Saved {scheme_name} raw HTML to {file_path}")
            
            # Politeness delay to avoid blocking
            if idx < len(sources) - 1:
                logger.info("Applying politeness delay (2 seconds)...")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Failed to process {scheme_name}: {e}")
            
    # Write manifest back
    with open(MANIFEST_FILE, "w", encoding="utf-8") as fm_out:
        json.dump(manifest, fm_out, indent=2)
    logger.info(f"Manifest written successfully to {MANIFEST_FILE}")

if __name__ == "__main__":
    main()
