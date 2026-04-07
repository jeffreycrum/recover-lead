"""Monthly health check for county scraper URLs.

Reads fl_county_surplus_research.csv and tests each scrapable URL.
Updates the CSV with current status and flags broken URLs.
Outputs a summary to stdout for CI/cron logging.

Usage:
    python scripts/check_county_urls.py
"""

import asyncio
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

CSV_PATH = Path(__file__).parent / "fl_county_surplus_research.csv"

# Browser-like headers to avoid bot blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def check_url(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    """Check a URL and return (status_code, error_or_empty)."""
    if not url or url == "N/A":
        return 0, "no_url"
    try:
        resp = await client.head(url, follow_redirects=True, timeout=15)
        return resp.status_code, ""
    except httpx.TimeoutException:
        return 0, "timeout"
    except httpx.RequestError as e:
        return 0, str(e)[:100]


async def main():
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run county research first.")
        sys.exit(1)

    rows = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Add status columns if not present
    if "Last Checked" not in fieldnames:
        fieldnames = list(fieldnames) + ["Last Checked", "HTTP Status", "Check Error"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scrapable_rows = [r for r in rows if r["Access Method"] == "Scrapable"]

    print(f"Checking {len(scrapable_rows)} scrapable county URLs...")
    print()

    broken = []
    working = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        for row in rows:
            if row["Access Method"] != "Scrapable":
                row.setdefault("Last Checked", "")
                row.setdefault("HTTP Status", "")
                row.setdefault("Check Error", "")
                continue

            url = row["URL"]
            status_code, error = await check_url(client, url)
            row["Last Checked"] = now
            row["HTTP Status"] = str(status_code)
            row["Check Error"] = error

            county = row["County"]
            if status_code == 200:
                working.append(county)
                print(f"  OK  {county}: {status_code}")
            else:
                broken.append((county, status_code, error))
                print(f"  FAIL {county}: {status_code} {error}")

    # Write updated CSV
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Results: {len(working)} working, {len(broken)} broken out of {len(scrapable_rows)} scrapable")

    if broken:
        print()
        print("BROKEN URLS — action required:")
        for county, status, error in broken:
            print(f"  - {county}: HTTP {status} {error}")

    return len(broken)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(1 if exit_code > 0 else 0)
