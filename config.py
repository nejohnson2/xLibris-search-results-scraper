"""Configuration for the Primo search results scraper."""

# Rate limiting — delays between API calls
MIN_DELAY = 3  # seconds (between pagination calls within a query)
MAX_DELAY = 5  # seconds
URL_DELAY = 2  # seconds between different URLs (added to MIN/MAX_DELAY jitter)

# Checkpoint — write intermediate results every N URLs
CHECKPOINT_INTERVAL = 100

# API settings
BATCH_SIZE = 50  # results per API request (max supported by Primo)
DEFAULT_MAX_RECORDS = 20  # max records to fetch per query

# Output
OUTPUT_DIR = "output"

# HTTP settings
USER_AGENT = "SearchAI-Scraper/1.0 (academic research; Stony Brook University library)"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential backoff base in seconds

# Primo API path (appended to the base URL extracted from the search URL)
PRIMO_API_PATH = "/primaws/rest/pub/pnxs"
