#!/usr/bin/env python3
"""CLI entry point for the Primo search results scraper."""

import argparse
import csv
import json
import logging
import random
import sys
import time
from pathlib import Path

from tqdm import tqdm

import config
import scraper


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def load_urls(source):
    """Load URLs from a CSV (with 'url' column), a text file, or a single URL string."""
    path = Path(source)
    if path.is_file():
        if path.suffix.lower() == ".csv":
            entries = []
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("url", "").strip()
                    if url:
                        entries.append({
                            "url": url,
                            "id": row.get("id", ""),
                            "sys": row.get("sys", ""),
                            "string": row.get("string", ""),
                        })
            return entries
        else:
            urls = []
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append({"url": line})
            return urls
    return [{"url": source}]


def load_completed_ids(output_path):
    """Load IDs already scraped from the output file (for resume support)."""
    completed = set()
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    entry_id = row.get("id", "")
                    if entry_id:
                        completed.add(entry_id)
                except json.JSONDecodeError:
                    continue
    return completed


def main():
    parser = argparse.ArgumentParser(
        description="Scrape search results from Stony Brook Library Primo API"
    )
    parser.add_argument(
        "url",
        help="A Primo search URL, path to a CSV, or path to a text file with one URL per line",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=config.DEFAULT_MAX_RECORDS,
        help=f"Maximum number of records to fetch per query (default: {config.DEFAULT_MAX_RECORDS})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL file path (default: output/results.jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch only a sample page and show metadata without full scrape",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh instead of resuming from existing output",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    entries = load_urls(args.url)
    logger.info(f"Loaded {len(entries)} URL(s) to process")

    # Set up output path
    output_path = Path(args.output) if args.output else Path(config.OUTPUT_DIR) / "results.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume support — skip already-completed entries
    if not args.no_resume:
        completed = load_completed_ids(output_path)
        if completed:
            before = len(entries)
            entries = [e for e in entries if e.get("id", "") not in completed]
            logger.info(f"Resuming: {before - len(entries)} already done, {len(entries)} remaining")

    total_records = 0
    total_errors = 0
    start_time = time.time()

    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, entry in enumerate(tqdm(entries, desc="Scraping URLs", unit="url"), 1):
            url = entry["url"]
            entry_id = entry.get("id", "")

            try:
                result = scraper.scrape_query(
                    url,
                    max_records=args.max_records,
                    dry_run=args.dry_run,
                )

                # Build a single output row with metadata + records
                output_row = {
                    "id": entry.get("id", ""),
                    "sys": entry.get("sys", ""),
                    "string": entry.get("string", ""),
                    "url": url,
                    "query": result["query"],
                    "total_available": result["total_available"],
                    "total_fetched": result["total_fetched"],
                    "records": result["records"],
                    "errors": result["errors"],
                }

                out_f.write(json.dumps(output_row, ensure_ascii=False) + "\n")
                out_f.flush()

                total_records += result["total_fetched"]

                if result["errors"]:
                    total_errors += len(result["errors"])
                    logger.warning(f"URL {i} (id: {entry_id}): {result['errors']}")

            except Exception as e:
                logger.error(f"Failed URL {i} (id: {entry_id}): {e}")
                # Write error row so we can track failures
                error_row = {
                    "id": entry.get("id", ""),
                    "sys": entry.get("sys", ""),
                    "string": entry.get("string", ""),
                    "url": url,
                    "query": None,
                    "total_available": 0,
                    "total_fetched": 0,
                    "records": [],
                    "errors": [str(e)],
                }
                out_f.write(json.dumps(error_row, ensure_ascii=False) + "\n")
                out_f.flush()
                total_errors += 1
                continue

            # Rate limit between URLs
            if i < len(entries):
                delay = config.URL_DELAY + random.uniform(0, config.MAX_DELAY - config.MIN_DELAY)
                time.sleep(delay)

            # Periodic checkpoint log
            if i % config.CHECKPOINT_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed * 3600
                logger.info(
                    f"Checkpoint: {i}/{len(entries)} URLs done, "
                    f"{total_records} records, {total_errors} errors, "
                    f"~{rate:.0f} URLs/hr"
                )

    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"SUMMARY")
    logger.info(f"  URLs processed: {len(entries)}")
    logger.info(f"  Total records: {total_records}")
    logger.info(f"  Total errors: {total_errors}")
    logger.info(f"  Time elapsed: {elapsed:.1f}s")
    logger.info(f"  Output file: {output_path}")


if __name__ == "__main__":
    main()
