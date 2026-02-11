#!/usr/bin/env python3
"""CLI entry point for the Primo search results scraper."""

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

import config
import scraper


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def sanitize_filename(url):
    """Create a short, unique filename from a URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"results_{url_hash}"


def load_urls(source):
    """Load URLs from a file (one per line) or return a single URL as a list."""
    path = Path(source)
    if path.is_file():
        urls = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        return urls
    return [source]


def main():
    parser = argparse.ArgumentParser(
        description="Scrape search results from Stony Brook Library Primo API"
    )
    parser.add_argument(
        "url",
        help="A Primo search URL, or path to a text file with one URL per line",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Maximum number of records to fetch per query (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        default=config.OUTPUT_DIR,
        help=f"Output directory (default: {config.OUTPUT_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch only a sample page and show metadata without full scrape",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    urls = load_urls(args.url)
    logger.info(f"Loaded {len(urls)} URL(s) to process")

    total_records = 0
    start_time = time.time()

    for i, url in enumerate(urls, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing URL {i}/{len(urls)}")
        logger.info(f"URL: {url[:100]}...")

        try:
            result = scraper.scrape_query(
                url,
                max_records=args.max_records,
                dry_run=args.dry_run,
            )

            filename = sanitize_filename(url)
            output_path = Path(args.output_dir) / f"{filename}.json"
            scraper.save_results(result, output_path)

            total_records += result["total_fetched"]

            logger.info(
                f"URL {i}: {result['total_fetched']} records fetched "
                f"(of {result['total_available']} available)"
            )
            if result["errors"]:
                logger.warning(f"  Errors: {result['errors']}")

        except Exception as e:
            logger.error(f"Failed to process URL {i}: {e}")
            continue

    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"SUMMARY")
    logger.info(f"  URLs processed: {len(urls)}")
    logger.info(f"  Total records: {total_records}")
    logger.info(f"  Time elapsed: {elapsed:.1f}s")
    logger.info(f"  Output dir: {args.output_dir}")


if __name__ == "__main__":
    main()
