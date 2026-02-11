# XLibris Search Results Scraper

Extracts search results from a library discovery system via its REST API. Outputs structured JSON with metadata for each record (title, authors, DOI, PMID, abstract, journal, subjects, etc.).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Dry run — fetch 5 sample records and show total count
python main.py --dry-run "PRIMO_SEARCH_URL"

# Scrape with a record limit
python main.py --max-records 500 "PRIMO_SEARCH_URL"

# Scrape all results (no limit)
python main.py "PRIMO_SEARCH_URL"

# Process multiple URLs from a file (one URL per line)
python main.py --max-records 1000 urls.txt

# Verbose logging
python main.py -v --max-records 100 "PRIMO_SEARCH_URL"
```

### Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview sample records and total count without full scrape |
| `--max-records N` | Cap the number of records fetched per query |
| `--output-dir DIR` | Output directory (default: `output/`) |
| `-v, --verbose` | Enable debug logging |

## Output

Results are saved as JSON files in the output directory. Each file contains:

```json
{
  "query": "the search query string",
  "url": "the original search URL",
  "total_available": 71009,
  "total_fetched": 500,
  "errors": [],
  "records": [
    {
      "record_id": "...",
      "title": "...",
      "type": "article",
      "creators": ["..."],
      "contributors": ["..."],
      "publisher": "...",
      "publication_date": "2024-01-15",
      "journal": "...",
      "volume": "12",
      "issue": "3",
      "pages": "100-110",
      "doi": "10.1234/example",
      "pmid": "12345678",
      "issn": ["1234-5678"],
      "abstract": "...",
      "subjects": ["..."],
      "keywords": ["..."],
      "language": ["eng"],
      "source": "...",
      "open_access": "free_for_read",
      "fulltext_link": "..."
    }
  ]
}
```

## Rate Limiting

The scraper is configured to be respectful of the server:

- 3-5 second random delay between requests
- Batch size of 50 results per request
- Exponential backoff on 429/5xx errors (max 3 retries)
- Descriptive User-Agent header

These settings can be adjusted in `config.py`.
