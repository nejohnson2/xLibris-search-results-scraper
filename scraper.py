"""Core scraping logic for Primo search results API."""

import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

import config

logger = logging.getLogger(__name__)


def parse_primo_url(url):
    """Parse a Primo search URL and extract query parameters.

    Returns a dict with keys: base_url, vid, query, scope, tab, mfacet, and
    any other relevant params found in the URL.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    base_url = f"{parsed.scheme}://{parsed.netloc}"

    result = {
        "base_url": base_url,
        "vid": params.get("vid", [None])[0],
        "query": params.get("query", [None])[0],
        "search_scope": params.get("search_scope", [None])[0],
        "tab": params.get("tab", ["Everything"])[0],
    }

    # Handle mfacet params (can be multiple)
    mfacets = params.get("mfacet", [])
    result["mfacets"] = mfacets

    return result


def build_api_params(parsed_url, offset=0):
    """Build query parameters for the Primo REST API call."""
    params = {
        "blendFacetsSeparately": "false",
        "disableCache": "false",
        "getMore": "0",
        "inst": parsed_url["vid"].split(":")[0] if parsed_url["vid"] else "",
        "lang": "en",
        "limit": str(config.BATCH_SIZE),
        "newspapersActive": "false",
        "newspapersSearch": "false",
        "offset": str(offset),
        "pcAvailability": "false",
        "q": parsed_url["query"],
        "qExclude": "",
        "qInclude": "",
        "refEntryActive": "false",
        "rtaLinks": "true",
        "scope": parsed_url["search_scope"],
        "searchInFulltextUserSelection": "false",
        "skipDelivery": "Y",
        "sort": "rank",
        "tab": parsed_url["tab"],
        "vid": parsed_url["vid"],
    }

    # Convert mfacet params to qInclude format
    for mfacet in parsed_url.get("mfacets", []):
        parts = mfacet.split(",")
        if len(parts) >= 3:
            facet_field = parts[0]
            facet_value = parts[2]
            if params["qInclude"]:
                params["qInclude"] += "|,|"
            params["qInclude"] += f"facet_{facet_field},exact,{facet_value}"

    return params


def _safe_get(doc, *keys):
    """Safely traverse nested dict keys, returning None if any key is missing."""
    current = doc
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_get_list(doc, *keys):
    """Like _safe_get but ensures the result is a list."""
    val = _safe_get(doc, *keys)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _first_or_none(doc, *keys):
    """Get the first element of a list field, or the value if scalar."""
    val = _safe_get(doc, *keys)
    if isinstance(val, list):
        return val[0] if val else None
    return val


def extract_record(doc):
    """Extract a flat record dict from a Primo API document object."""
    pnx = doc.get("pnx", {})

    record = {
        "record_id": _first_or_none(pnx, "control", "recordid"),
        "title": _first_or_none(pnx, "display", "title"),
        "type": _first_or_none(pnx, "display", "type"),
        "creators": _safe_get_list(pnx, "display", "creator"),
        "contributors": _safe_get_list(pnx, "display", "contributor"),
        "publisher": _first_or_none(pnx, "display", "publisher"),
        "publication_date": _first_or_none(pnx, "addata", "date"),
        "journal": _first_or_none(pnx, "addata", "jtitle"),
        "volume": _first_or_none(pnx, "addata", "volume"),
        "issue": _first_or_none(pnx, "addata", "issue"),
        "pages": _first_or_none(pnx, "addata", "pages"),
        "doi": _first_or_none(pnx, "addata", "doi"),
        "pmid": _first_or_none(pnx, "addata", "pmid"),
        "issn": _safe_get_list(pnx, "addata", "issn"),
        "abstract": _first_or_none(pnx, "addata", "abstract"),
        "subjects": _safe_get_list(pnx, "display", "subject"),
        "keywords": _safe_get_list(pnx, "display", "keyword"),
        "language": _safe_get_list(pnx, "display", "language"),
        "source": _first_or_none(pnx, "display", "source"),
        "open_access": _first_or_none(pnx, "display", "oa"),
    }

    # Extract best available fulltext link
    links = doc.get("pnx", {}).get("links", {})
    fulltext = (
        _first_or_none(links, "linktorsrc")
        or _first_or_none(links, "linktohtml")
        or _first_or_none(links, "openurl")
    )
    record["fulltext_link"] = fulltext

    return record


def check_robots_txt(base_url, session):
    """Check robots.txt for the target site. Logs a warning if disallowed."""
    robots_url = f"{base_url}/robots.txt"
    try:
        resp = session.get(robots_url, timeout=10)
        if resp.status_code == 200:
            text = resp.text.lower()
            if "disallow: /primaws" in text:
                logger.warning(
                    "robots.txt disallows /primaws — proceeding with caution"
                )
                return False
        logger.info("robots.txt check passed")
    except requests.RequestException:
        logger.info("Could not fetch robots.txt — proceeding with caution")
    return True


def fetch_page(session, api_url, params, offset):
    """Fetch one page of results from the Primo API with retry logic."""
    params = {**params, "offset": str(offset)}

    for attempt in range(config.MAX_RETRIES):
        try:
            resp = session.get(
                api_url, params=params, timeout=config.REQUEST_TIMEOUT
            )

            if resp.status_code == 429:
                wait = config.RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.warning(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                wait = config.RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.warning(
                    f"Server error ({resp.status_code}). Retrying in {wait}s..."
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            wait = config.RETRY_BACKOFF_BASE ** (attempt + 1)
            logger.warning(f"Request timed out. Retrying in {wait}s...")
            time.sleep(wait)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if attempt < config.MAX_RETRIES - 1:
                wait = config.RETRY_BACKOFF_BASE ** (attempt + 1)
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(f"Failed to fetch page at offset {offset} after {config.MAX_RETRIES} retries")


def scrape_query(url, max_records=None, dry_run=False):
    """Scrape all results for a given Primo search URL.

    Args:
        url: A Primo discovery search URL.
        max_records: Maximum number of records to retrieve. None = all.
        dry_run: If True, only fetch the first page to show metadata without
                 scraping everything.

    Returns:
        dict with keys: 'records' (list of dicts), 'total_available' (int),
        'total_fetched' (int), 'query' (str), 'errors' (list of str).
    """
    parsed = parse_primo_url(url)
    api_url = parsed["base_url"] + config.PRIMO_API_PATH
    params = build_api_params(parsed)

    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})

    check_robots_txt(parsed["base_url"], session)

    result = {
        "query": parsed["query"],
        "url": url,
        "records": [],
        "total_available": 0,
        "total_fetched": 0,
        "errors": [],
    }

    # Fetch first page to get total count
    logger.info(f"Fetching initial page to determine result count...")
    try:
        data = fetch_page(session, api_url, params, 0)
    except Exception as e:
        result["errors"].append(f"Failed to fetch first page: {e}")
        return result

    total = data.get("info", {}).get("total", 0)
    result["total_available"] = total
    logger.info(f"Total results available: {total}")

    if dry_run:
        docs = data.get("docs", [])
        for doc in docs[:5]:
            result["records"].append(extract_record(doc))
        result["total_fetched"] = len(result["records"])
        logger.info(f"Dry run: fetched {len(result['records'])} sample records")
        return result

    # Determine how many records to fetch
    target = total
    if max_records is not None:
        target = min(total, max_records)
    logger.info(f"Will fetch {target} of {total} records")

    # Process first page
    docs = data.get("docs", [])
    for doc in docs:
        if len(result["records"]) >= target:
            break
        result["records"].append(extract_record(doc))

    offset = len(docs)

    # Paginate through remaining results
    while offset < target and offset < total:
        delay = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
        logger.info(
            f"Progress: {len(result['records'])}/{target} records. "
            f"Waiting {delay:.1f}s..."
        )
        time.sleep(delay)

        try:
            data = fetch_page(session, api_url, params, offset)
        except Exception as e:
            msg = f"Failed at offset {offset}: {e}"
            logger.error(msg)
            result["errors"].append(msg)
            break

        docs = data.get("docs", [])
        if not docs:
            logger.info("No more documents returned. Stopping.")
            break

        for doc in docs:
            if len(result["records"]) >= target:
                break
            result["records"].append(extract_record(doc))

        offset += len(docs)

    result["total_fetched"] = len(result["records"])
    logger.info(f"Done. Fetched {result['total_fetched']} records.")
    return result


def save_results(result, output_path):
    """Save scrape results to a JSON file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {result['total_fetched']} records to {output_path}")
