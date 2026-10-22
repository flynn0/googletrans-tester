import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGES_FILE = BASE_DIR / "data" / "packages.json"

REQUIRED_KEYS = {
    "id",
    "pypi_name",
    "description",
    "pypi_url",
    "pepy_url",
    "pypistats_url",
    "default_module",
}


def test_packages_file_exists():
    assert PACKAGES_FILE.is_file(), f"{PACKAGES_FILE} must exist"


def test_packages_count_and_keys():
    with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
        packages = json.load(f)

    assert isinstance(packages, list)
    assert len(packages) == 27, f"Expected 27 packages, got {len(packages)}"

    seen_ids = set()
    seen_names = set()

    for pkg in packages:
        missing = REQUIRED_KEYS - set(pkg.keys())
        assert not missing, f"Package {pkg.get('id')} missing keys: {missing}"

        pkg_id = pkg["id"]
        pypi_name = pkg["pypi_name"]

        assert pkg_id not in seen_ids, f"Duplicate package id: {pkg_id}"
        assert pypi_name not in seen_names, f"Duplicate pypi_name: {pypi_name}"
        seen_ids.add(pkg_id)
        seen_names.add(pypi_name)

        assert pkg["pypi_url"].startswith("https://pypi.org/project/")
        assert pkg["pepy_url"].startswith("https://pepy.tech/projects/")
        assert pkg["pypistats_url"].startswith("https://pypistats.org/packages/")
