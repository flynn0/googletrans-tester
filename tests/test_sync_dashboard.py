import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.sync_dashboard_data import sync


def test_sync_dashboard_generates_valid_payload():
    sync()

    latest_file = BASE_DIR / "data" / "latest_results.json"
    dashboard_file = BASE_DIR / "dashboard" / "public" / "results.json"

    assert latest_file.is_file()
    assert dashboard_file.is_file()

    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "generated_at" in data
    assert "metadata" in data
    assert "summary" in data
    assert "packages" in data

    with open(BASE_DIR / "data" / "packages.json", "r", encoding="utf-8") as f:
        pkg_defs = json.load(f)

    assert data["summary"]["total_packages"] == len(pkg_defs)
    assert len(data["packages"]) == len(pkg_defs)
    assert data["summary"]["passed"] + data["summary"]["failed"] == len(pkg_defs)
