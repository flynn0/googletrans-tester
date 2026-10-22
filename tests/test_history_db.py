import json
import os
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from runner.history_db import (
    init_db,
    record_matrix_run,
    get_all_runs,
    get_package_history_data,
    generate_full_history_export,
    backfill_known_git_runs
)


def test_init_and_record_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_history.db"
        json_path = Path(tmp_dir) / "test_history.json"

        init_db(db_path)
        assert db_path.is_file()

        # Mock run 1 (Pass)
        run1_data = {
            "summary": {"total": 2, "passed": 2, "failed": 0, "timestamp": "2026-10-10T10:00:00Z"},
            "results": {
                "googletrans": {
                    "overall_status": "passed",
                    "installed_version": "4.0.2",
                    "api_type": "async",
                    "tests": {"translate_en_de": {"status": "passed", "latency_ms": 250.0}}
                },
                "googletrans-curl": {
                    "overall_status": "passed",
                    "installed_version": "4.1.0",
                    "api_type": "async",
                    "tests": {"translate_en_de": {"status": "passed", "latency_ms": 800.0}}
                }
            }
        }

        # Mock run 2 (googletrans regressed)
        run2_data = {
            "summary": {"total": 2, "passed": 1, "failed": 1, "timestamp": "2026-10-12T10:00:00Z"},
            "results": {
                "googletrans": {
                    "overall_status": "failed",
                    "installed_version": "4.0.2",
                    "api_type": "async",
                    "error_summary": "Untranslated echo output: 'Hello world'",
                    "tests": {"translate_en_de": {"status": "failed", "latency_ms": 400.0}}
                },
                "googletrans-curl": {
                    "overall_status": "passed",
                    "installed_version": "4.1.0",
                    "api_type": "async",
                    "tests": {"translate_en_de": {"status": "passed", "latency_ms": 750.0}}
                }
            }
        }

        record_matrix_run(run1_data, db_path=db_path)
        record_matrix_run(run2_data, db_path=db_path)

        runs = get_all_runs(db_path)
        assert len(runs) == 2
        assert runs[0]["passed_count"] == 2
        assert runs[1]["passed_count"] == 1

        # Check googletrans reliability
        gt_hist = get_package_history_data("googletrans", db_path=db_path)
        assert gt_hist["total_runs"] == 2
        assert gt_hist["passed_runs"] == 1
        assert gt_hist["failed_runs"] == 1
        assert gt_hist["reliability_percentage"] == 50.0
        assert gt_hist["trend"] == "regressed"

        # Check googletrans-curl reliability
        curl_hist = get_package_history_data("googletrans-curl", db_path=db_path)
        assert curl_hist["total_runs"] == 2
        assert curl_hist["passed_runs"] == 2
        assert curl_hist["reliability_percentage"] == 100.0
        assert curl_hist["trend"] == "stable"

        # Check JSON export
        export = generate_full_history_export(db_path=db_path, output_json=json_path)
        assert json_path.is_file()
        assert export["total_runs_tracked"] == 2
        assert "googletrans" in export["packages"]
        assert export["packages"]["googletrans"]["reliability_percentage"] == 50.0
