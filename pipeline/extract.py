"""Extract step: CSV exports plus a paginated REST API client with retries."""
import csv
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fetch_tickets(base_url: str, token: str, page_size: int = 200,
                  max_retries: int = 4, backoff: float = 0.2) -> list[dict]:
    """Pull every page from the ticketing API, retrying 5xx and network errors."""
    rows, page = [], 1
    while page:
        url = f"{base_url}/api/v1/tickets?page={page}&page_size={page_size}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == max_retries:
                    raise
                log.warning("page %s: HTTP %s, retry %s/%s", page, e.code, attempt, max_retries)
            except urllib.error.URLError:
                if attempt == max_retries:
                    raise
                log.warning("page %s: network error, retry %s/%s", page, attempt, max_retries)
            time.sleep(backoff * 2 ** (attempt - 1))
        rows.extend(body["data"])
        page = body["next_page"]
    log.info("fetched %s tickets from API", len(rows))
    return rows
