"""Configuration for the Primo search results scraper."""

# Rate limiting
MIN_DELAY = 3  # seconds
MAX_DELAY = 5  # seconds

# API settings
BATCH_SIZE = 50  # results per API request (max supported by Primo)
DEFAULT_MAX_RECORDS = None  # None = no limit, scrape all results

# Output
OUTPUT_DIR = "output"

# HTTP settings
USER_AGENT = "SearchAI-Scraper/1.0 (academic research; Stony Brook University library)"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential backoff base in seconds

# Primo API path (appended to the base URL extracted from the search URL)
PRIMO_API_PATH = "/primaws/rest/pub/pnxs"
