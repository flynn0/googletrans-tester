#!/usr/bin/env python3
"""
fetch_stats.py
Collects release metadata and download statistics for all 11 packages from:
- PyPI JSON API: latest version, upload date, author, description
- pepy.tech: total lifetime downloads
- pypistats.org: recent downloads (last month, last week, last day) & 2026 downloads
"""

import json
import logging
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGES_FILE = BASE_DIR / "data" / "packages.json"
OUTPUT_FILE = BASE_DIR / "data" / "stats.json"

HEADERS = {
    "User-Agent": "googletrans-tester-stats/1.0 (+https://github.com/flynn0/googletrans-tester)"
}


def fetch_url(url, timeout=12):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_pypi_meta(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        raw = fetch_url(url)
        data = json.loads(raw)
        info = data.get("info", {})
        version = info.get("version", "unknown")
        releases = data.get("releases", {})
        upload_time = None
        if version in releases and releases[version]:
            upload_time = releases[version][0].get("upload_time_iso_8601") or releases[version][0].get("upload_time")

        return {
            "latest_version": version,
            "latest_release_date": upload_time,
            "summary": info.get("summary", ""),
            "author": info.get("author", ""),
            "license": info.get("license", ""),
            "requires_python": info.get("requires_python", ""),
            "project_url": info.get("project_url", f"https://pypi.org/project/{package_name}/")
        }
    except Exception as e:
        logging.warning("PyPI fetch error for %s: %s", package_name, e)
        return {
            "latest_version": "unknown",
            "latest_release_date": None,
            "error": str(e)
        }


def fetch_pepy_lifetime(package_name):
    """
    Fetches lifetime downloads from pepy.tech by inspecting project data or badge fallback.
    """
    url = f"https://pepy.tech/projects/{package_name}"
    try:
        raw = fetch_url(url).decode("utf-8", errors="replace")
        # Match Next.js serialized state: totalDownloads\":12345
        m = re.search(r'totalDownloads\\\\\"?:(\d+)', raw)
        if m:
            return int(m.group(1))
    except Exception as e:
        logging.warning("pepy.tech page fetch error for %s: %s", package_name, e)

    # Fallback to badge
    try:
        badge_url = f"https://static.pepy.tech/badge/{package_name}"
        raw = fetch_url(badge_url).decode("utf-8", errors="replace")
        matches = re.findall(r'<text[^>]*>([0-9\.]+[kMGTBP]?)</text>', raw)
        if matches:
            val_str = matches[-1]
            return parse_metric_suffix(val_str)
    except Exception as e:
        logging.warning("pepy.tech badge fetch error for %s: %s", package_name, e)

    return 0


def parse_metric_suffix(s):
    multipliers = {"k": 1_000, "M": 1_000_000, "G": 1_000_000_000, "T": 1_000_000_000_000}
    s = s.strip()
    if not s:
        return 0
    mult = 1
    if s[-1] in multipliers:
        mult = multipliers[s[-1]]
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def fetch_pypistats(package_name):
    res = {
        "last_day": 0,
        "last_week": 0,
        "last_month": 0,
        "downloads_2026": 0,
        "downloads_2026_with_mirrors": 0
    }

    # 1. Recent downloads
    try:
        url = f"https://pypistats.org/api/packages/{package_name}/recent"
        raw = fetch_url(url)
        data = json.loads(raw)
        recent_data = data.get("data", {})
        res["last_day"] = recent_data.get("last_day", 0)
        res["last_week"] = recent_data.get("last_week", 0)
        res["last_month"] = recent_data.get("last_month", 0)
    except Exception as e:
        logging.warning("pypistats recent error for %s: %s", package_name, e)

    # 2. Overall downloads for 2026
    try:
        url = f"https://pypistats.org/api/packages/{package_name}/overall"
        raw = fetch_url(url)
        data = json.loads(raw)
        entries = data.get("data", [])
        d2026_nomirror = sum(x["downloads"] for x in entries if x.get("category") == "without_mirrors" and x.get("date", "").startswith("2026"))
        d2026_withmirror = sum(x["downloads"] for x in entries if x.get("category") == "with_mirrors" and x.get("date", "").startswith("2026"))
        res["downloads_2026"] = d2026_nomirror
        res["downloads_2026_with_mirrors"] = d2026_withmirror
    except Exception as e:
        logging.warning("pypistats overall error for %s: %s", package_name, e)

    return res


def collect_all_stats():
    if not PACKAGES_FILE.exists():
        logging.error("packages.json not found at %s", PACKAGES_FILE)
        sys.exit(1)

    with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
        packages = json.load(f)

    stats = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    for pkg_meta in packages:
        pypi_name = pkg_meta["pypi_name"]
        logging.info("Fetching stats for %s...", pypi_name)

        pypi_info = fetch_pypi_meta(pypi_name)
        time.sleep(0.2)  # courteous rate-limiting

        pepy_lifetime = fetch_pepy_lifetime(pypi_name)
        time.sleep(0.2)

        pypistats_data = fetch_pypistats(pypi_name)
        time.sleep(0.2)

        stats[pypi_name] = {
            "package_id": pkg_meta["id"],
            "pypi_name": pypi_name,
            "pypi_url": pkg_meta.get("pypi_url", f"https://pypi.org/project/{pypi_name}/"),
            "pepy_url": pkg_meta.get("pepy_url", f"https://pepy.tech/projects/{pypi_name}"),
            "pypistats_url": pkg_meta.get("pypistats_url", f"https://pypistats.org/packages/{pypi_name}"),
            "latest_version": pypi_info.get("latest_version"),
            "latest_release_date": pypi_info.get("latest_release_date"),
            "summary": pypi_info.get("summary"),
            "author": pypi_info.get("author"),
            "downloads_lifetime": pepy_lifetime,
            "downloads_2026": pypistats_data["downloads_2026"],
            "downloads_2026_with_mirrors": pypistats_data["downloads_2026_with_mirrors"],
            "downloads_last_month": pypistats_data["last_month"],
            "downloads_last_week": pypistats_data["last_week"],
            "downloads_last_day": pypistats_data["last_day"],
            "fetched_at": now_iso
        }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    logging.info("Successfully saved stats for %d packages to %s", len(stats), OUTPUT_FILE)
    return stats


if __name__ == "__main__":
    collect_all_stats()
