#!/usr/bin/env python3
"""
sync_dashboard_data.py
Merges data/packages.json, data/stats.json, data/matrix_results.json,
and data/history.db into:
- data/latest_results.json
- data/runs_history.json
- dashboard/public/results.json
- dashboard/public/history.json

Produces a unified schema with historical reliability metrics
for the Vite dashboard and for agent consumption.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import sys

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from runner.history_db import (
    DEFAULT_DB_PATH,
    DEFAULT_HISTORY_JSON,
    init_db,
    record_matrix_run,
    get_all_runs,
    get_package_history_data,
    generate_full_history_export,
    backfill_known_git_runs
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

PACKAGES_FILE = BASE_DIR / "data" / "packages.json"
STATS_FILE = BASE_DIR / "data" / "stats.json"
MATRIX_FILE = BASE_DIR / "data" / "matrix_results.json"

LATEST_RESULTS_DATA = BASE_DIR / "data" / "latest_results.json"
DASHBOARD_PUBLIC_RESULTS = BASE_DIR / "dashboard" / "public" / "results.json"
DASHBOARD_PUBLIC_HISTORY = BASE_DIR / "dashboard" / "public" / "history.json"


def sync():
    if not PACKAGES_FILE.exists():
        logging.error("packages.json not found")
        return

    with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
        packages = json.load(f)

    stats = {}
    if STATS_FILE.exists():
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)

    matrix = {"summary": {}, "results": {}}
    if MATRIX_FILE.exists():
        with open(MATRIX_FILE, "r", encoding="utf-8") as f:
            matrix = json.load(f)

    # 1. Initialize and maintain historical database
    init_db()
    existing_runs = get_all_runs()
    if len(existing_runs) < 2:
        logging.info("Backfilling historical runs from git history...")
        backfill_known_git_runs()

    # Record current matrix run if results present
    if matrix.get("results"):
        record_matrix_run(matrix, source="matrix_results_sync")

    # Generate full history export
    history_export = generate_full_history_export()

    # Also write history to dashboard/public/history.json
    DASHBOARD_PUBLIC_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_PUBLIC_HISTORY, "w", encoding="utf-8") as f:
        json.dump(history_export, f, indent=2)

    now_iso = datetime.now(timezone.utc).isoformat()
    package_reports = []

    passed_count = 0
    failed_count = 0
    total_lifetime_dl = 0
    total_2026_dl = 0
    total_last_month_dl = 0

    stable_count = 0
    regressed_count = 0
    recovered_count = 0

    all_runs = get_all_runs()

    for pkg in packages:
        name = pkg["pypi_name"]
        pkg_stat = stats.get(name, {})
        test_res = matrix.get("results", {}).get(name, {})

        is_passed = test_res.get("overall_status") == "passed"
        if is_passed:
            passed_count += 1
        else:
            failed_count += 1

        lifetime_dl = pkg_stat.get("downloads_lifetime", 0) or 0
        d_2026 = pkg_stat.get("downloads_2026", 0) or 0
        d_month = pkg_stat.get("downloads_last_month", 0) or 0

        total_lifetime_dl += lifetime_dl
        total_2026_dl += d_2026
        total_last_month_dl += d_month

        # Retrieve package historical tracking
        pkg_hist_data = get_package_history_data(name)
        trend = pkg_hist_data.get("trend", "stable")
        if trend == "stable":
            stable_count += 1
        elif trend == "regressed":
            regressed_count += 1
        elif trend == "recovered":
            recovered_count += 1

        item = {
            "id": pkg["id"],
            "name": name,
            "description": pkg.get("description", ""),
            "pypi_url": pkg.get("pypi_url", f"https://pypi.org/project/{name}/"),
            "pepy_url": pkg.get("pepy_url", f"https://pepy.tech/projects/{name}"),
            "pypistats_url": pkg.get("pypistats_url", f"https://pypistats.org/packages/{name}"),
            "default_module": pkg.get("default_module", "googletrans"),
            "latest_release": pkg_stat.get("latest_version") or test_res.get("installed_version", "unknown"),
            "latest_release_date": pkg_stat.get("latest_release_date"),
            "downloads": {
                "lifetime": lifetime_dl,
                "year_2026": d_2026,
                "year_2026_with_mirrors": pkg_stat.get("downloads_2026_with_mirrors", 0) or 0,
                "last_month": d_month,
                "last_week": pkg_stat.get("downloads_last_week", 0) or 0,
                "last_day": pkg_stat.get("downloads_last_day", 0) or 0
            },
            "test_result": {
                "status": test_res.get("overall_status", "untested"),
                "api_type": test_res.get("api_type", "unknown"),
                "module_name": test_res.get("module_name"),
                "elapsed_sec": test_res.get("elapsed_sec"),
                "error_summary": test_res.get("error_summary"),
                "tests": test_res.get("tests", {})
            },
            "reliability": {
                "percentage": pkg_hist_data.get("reliability_percentage", 0.0),
                "total_runs": pkg_hist_data.get("total_runs", 0),
                "passed_runs": pkg_hist_data.get("passed_runs", 0),
                "failed_runs": pkg_hist_data.get("failed_runs", 0),
                "trend": trend,
                "avg_latency_ms": pkg_hist_data.get("avg_latency_ms")
            },
            "history": pkg_hist_data.get("history", [])
        }
        package_reports.append(item)

    # Sort: passed first, then by lifetime downloads descending
    package_reports.sort(
        key=lambda x: (
            1 if x["test_result"]["status"] == "passed" else 0,
            x["downloads"]["lifetime"]
        ),
        reverse=True
    )

    combined_payload = {
        "generated_at": now_iso,
        "metadata": {
            "title": "Googletrans Implementations & Forks Live Matrix",
            "version": "v0.1.0",
            "release_url": "https://github.com/flynn0/googletrans-tester/releases/tag/v0.1.0",
            "repository": "https://github.com/flynn0/googletrans-tester",
            "inspiration_repos": [
                "https://github.com/aikenf/googletrans-all",
                "https://github.com/aikenf/googletrans-test",
                "https://github.com/flynn0/googletrans-curl-tester"
            ]
        },
        "summary": {
            "total_packages": len(packages),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round((passed_count / len(packages) * 100), 1) if packages else 0,
            "total_downloads_lifetime": total_lifetime_dl,
            "total_downloads_2026": total_2026_dl,
            "total_downloads_last_month": total_last_month_dl,
            "total_historical_runs": len(all_runs),
            "trend_summary": {
                "stable": stable_count,
                "regressed": regressed_count,
                "recovered": recovered_count
            }
        },
        "runs_history": all_runs,
        "packages": package_reports
    }

    # Write data/latest_results.json
    LATEST_RESULTS_DATA.parent.mkdir(parents=True, exist_ok=True)
    with open(LATEST_RESULTS_DATA, "w", encoding="utf-8") as f:
        json.dump(combined_payload, f, indent=2)

    # Write dashboard/public/results.json
    DASHBOARD_PUBLIC_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_PUBLIC_RESULTS, "w", encoding="utf-8") as f:
        json.dump(combined_payload, f, indent=2)

    logging.info(
        "Synchronized results to %s, %s, and history files (%d packages, %d passed, %d failed, %d historical runs)",
        LATEST_RESULTS_DATA,
        DASHBOARD_PUBLIC_RESULTS,
        len(packages),
        passed_count,
        failed_count,
        len(all_runs)
    )


if __name__ == "__main__":
    sync()
