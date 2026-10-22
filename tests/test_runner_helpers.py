import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from runner.fetch_stats import parse_metric_suffix
from runner.test_single_target import get_installed_dist_info


def test_parse_metric_suffix():
    assert parse_metric_suffix("500") == 500
    assert parse_metric_suffix("1.5k") == 1500
    assert parse_metric_suffix("2M") == 2000000
    assert parse_metric_suffix("1.25G") == 1250000000
    assert parse_metric_suffix("") == 0
    assert parse_metric_suffix("invalid") == 0


def test_get_installed_dist_info_nonexistent():
    info = get_installed_dist_info("definitely-non-existent-package-xyz-999")
    assert info["installed"] is False
    assert info["version"] is None
    assert info["top_level"] == []
    assert "error" in info


def test_get_installed_dist_info_installed():
    info = get_installed_dist_info("packaging")
    assert info["installed"] is True
    assert info["version"] is not None
