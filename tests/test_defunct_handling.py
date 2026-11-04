import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

PACKAGES_FILE = BASE_DIR / "data" / "packages.json"
LATEST_RESULTS = BASE_DIR / "data" / "latest_results.json"
DASHBOARD_RESULTS = BASE_DIR / "dashboard" / "public" / "results.json"


def test_packages_defunct_classification():
    with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
        packages = json.load(f)

    defunct_pkgs = [p for p in packages if p.get("category") == "defunct"]
    defunct_names = {p["pypi_name"] for p in defunct_pkgs}

    assert "google-translate-py" in defunct_names
    assert "python-translator" in defunct_names
    assert len(defunct_pkgs) == 2

    for p in defunct_pkgs:
        assert "category_reason" in p and len(p["category_reason"]) > 10


def test_results_metadata_version_v013():
    for fpath in [LATEST_RESULTS, DASHBOARD_RESULTS]:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["metadata"]["version"] == "v0.1.3"
        assert "v0.1.3" in data["metadata"]["release_url"]
        assert data["summary"]["defunct_count"] == 2
        assert data["summary"]["total_packages"] == 37


def test_defunct_packages_preserve_telemetry_in_dashboard():
    with open(LATEST_RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    by_name = {p["name"]: p for p in data["packages"]}

    gt_py = by_name["google-translate-py"]
    assert gt_py["category"] == "defunct"
    assert gt_py["test_result"]["status"] == "defunct"
    assert gt_py["downloads"]["year_2026"] > 0
    assert gt_py["downloads"]["last_month"] > 0
    assert gt_py["downloads"]["lifetime"] > 0

    py_tr = by_name["python-translator"]
    assert py_tr["category"] == "defunct"
    assert py_tr["test_result"]["status"] == "defunct"
    assert py_tr["downloads"]["year_2026"] > 0
    assert py_tr["downloads"]["last_month"] > 0
    assert py_tr["downloads"]["lifetime"] > 0
