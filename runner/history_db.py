#!/usr/bin/env python3
"""
history_db.py
Manages historical test run tracking using SQLite and JSON formats.
Stores each test matrix run, tracks package pass/fail transitions,
and calculates reliability statistics (percentages, uptime, latencies).
"""

import json
import logging
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "history.db"
DEFAULT_HISTORY_JSON = BASE_DIR / "data" / "runs_history.json"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables and indices if they do not exist."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                total_packages INTEGER NOT NULL,
                passed_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                source TEXT DEFAULT 'matrix_runner',
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS package_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
                package_name TEXT NOT NULL,
                package_id TEXT,
                status TEXT NOT NULL,
                api_type TEXT,
                version TEXT,
                latency_ms REAL,
                error_summary TEXT,
                tests_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(run_id, package_name)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pkg_name ON package_results(package_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON test_runs(timestamp);")
    conn.close()


def record_matrix_run(
    matrix_data: Dict[str, Any],
    db_path: Optional[Path] = None,
    source: str = "matrix_runner",
    run_timestamp: Optional[str] = None
) -> str:
    """Record a matrix test execution into the SQLite database. Returns run_id."""
    init_db(db_path)
    conn = get_db_connection(db_path)

    summary = matrix_data.get("summary", {})
    results = matrix_data.get("results", {})

    ts = run_timestamp or summary.get("timestamp") or datetime.now(timezone.utc).isoformat()
    # Normalize run_id to ISO timestamp without microsecond noise if possible
    run_id = f"run_{ts.replace(':', '-').replace('.', '_')}"
    now_iso = datetime.now(timezone.utc).isoformat()

    passed_count = summary.get("passed", sum(1 for r in results.values() if r.get("overall_status") == "passed"))
    failed_count = summary.get("failed", len(results) - passed_count)
    total_packages = summary.get("total", len(results))

    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO test_runs (
                run_id, timestamp, total_packages, passed_count, failed_count, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (run_id, ts, total_packages, passed_count, failed_count, source, now_iso))

        for pkg_name, pkg_res in results.items():
            status = pkg_res.get("overall_status", "unknown")
            api_type = pkg_res.get("api_type")
            version = pkg_res.get("installed_version")
            translate_test = pkg_res.get("tests", {}).get("translate_en_de", {})
            latency_ms = translate_test.get("latency_ms")
            error_summary = pkg_res.get("error_summary")
            tests_json = json.dumps(pkg_res.get("tests", {}))
            pkg_id = pkg_res.get("package_id", pkg_name)

            conn.execute("""
                INSERT OR REPLACE INTO package_results (
                    run_id, package_name, package_id, status, api_type, version,
                    latency_ms, error_summary, tests_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, pkg_name, pkg_id, status, api_type, version,
                latency_ms, error_summary, tests_json, now_iso
            ))

    conn.close()
    return run_id


def get_all_runs(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve all recorded runs in chronological order."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM test_runs ORDER BY timestamp ASC;")
    rows = cur.fetchall()
    runs = []
    for r in rows:
        runs.append({
            "run_id": r["run_id"],
            "timestamp": r["timestamp"],
            "total_packages": r["total_packages"],
            "passed_count": r["passed_count"],
            "failed_count": r["failed_count"],
            "pass_rate": round(r["passed_count"] / r["total_packages"] * 100, 1) if r["total_packages"] else 0,
            "source": r["source"],
        })
    conn.close()
    return runs


def get_package_history_data(package_name: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Retrieve full history and calculate reliability statistics for a package."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.timestamp, pr.*
        FROM package_results pr
        JOIN test_runs r ON pr.run_id = r.run_id
        WHERE pr.package_name = ?
        ORDER BY r.timestamp ASC;
    """, (package_name,))
    rows = cur.fetchall()
    conn.close()

    history_records = []
    passed_count = 0
    total_latency = 0.0
    latency_count = 0

    for r in rows:
        is_passed = r["status"] == "passed"
        if is_passed:
            passed_count += 1
        lat = r["latency_ms"]
        if lat is not None:
            total_latency += lat
            latency_count += 1

        history_records.append({
            "run_id": r["run_id"],
            "timestamp": r["timestamp"],
            "status": r["status"],
            "version": r["version"],
            "api_type": r["api_type"],
            "latency_ms": lat,
            "error_summary": r["error_summary"],
            "tests": json.loads(r["tests_json"]) if r["tests_json"] else {}
        })

    total_runs = len(history_records)
    reliability_pct = round((passed_count / total_runs * 100), 1) if total_runs > 0 else 0.0
    avg_latency = round(total_latency / latency_count, 1) if latency_count > 0 else None

    # Trend: compare latest vs previous
    trend = "stable"
    if total_runs >= 2:
        last_status = history_records[-1]["status"]
        prev_status = history_records[-2]["status"]
        if last_status == "passed" and prev_status != "passed":
            trend = "recovered"
        elif last_status != "passed" and prev_status == "passed":
            trend = "regressed"

    return {
        "package_name": package_name,
        "total_runs": total_runs,
        "passed_runs": passed_count,
        "failed_runs": total_runs - passed_count,
        "reliability_percentage": reliability_pct,
        "avg_latency_ms": avg_latency,
        "trend": trend,
        "history": history_records
    }


def generate_full_history_export(db_path: Optional[Path] = None, output_json: Optional[Path] = None) -> Dict[str, Any]:
    """Generate a combined JSON structure containing all runs and package histories."""
    init_db(db_path)
    runs = get_all_runs(db_path)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT package_name FROM package_results;")
    pkgs = [row[0] for row in cur.fetchall()]
    conn.close()

    package_histories = {}
    for pkg in pkgs:
        package_histories[pkg] = get_package_history_data(pkg, db_path)

    export_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs_tracked": len(runs),
        "runs": runs,
        "packages": package_histories
    }

    out = Path(output_json) if output_json else DEFAULT_HISTORY_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    return export_data


def backfill_known_git_runs(db_path: Optional[Path] = None) -> int:
    """Backfills runs from git commits if not already in the database."""
    init_db(db_path)
    known_commits = [
        {"ref": "9c5904d", "source": "git_commit_9c5904d"},
        {"ref": "763026c", "source": "git_commit_763026c"}
    ]
    imported_count = 0

    for item in known_commits:
        try:
            raw = subprocess.check_output(
                ["git", "show", f"{item['ref']}:data/matrix_results.json"],
                cwd=str(BASE_DIR)
            ).decode("utf-8")
            data = json.loads(raw)
            record_matrix_run(data, db_path=db_path, source=item["source"])
            imported_count += 1
            logging.info("Successfully backfilled run from git ref %s", item["ref"])
        except Exception as e:
            logging.warning("Could not backfill git ref %s: %s", item["ref"], e)

    return imported_count


if __name__ == "__main__":
    init_db()
    backfill_known_git_runs()
    export = generate_full_history_export()
    print(f"Recorded {export['total_runs_tracked']} runs across {len(export['packages'])} packages.")
