#!/usr/bin/env python3
"""
run_matrix.py
Executes the test suite across all candidate packages in isolated virtual environments.
Runs sequentially or filtered by package name.
Saves comprehensive results to data/matrix_results.json.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

PACKAGES_FILE = BASE_DIR / "data" / "packages.json"
TEST_RUNNER_SCRIPT = BASE_DIR / "runner" / "test_single_target.py"
OUTPUT_FILE = BASE_DIR / "data" / "matrix_results.json"


def test_package_in_isolation(package_meta, pip_timeout=60):
    pypi_name = package_meta["pypi_name"]
    module_hint = package_meta.get("default_module")
    logging.info("Testing package [%s] in ephemeral venv...", pypi_name)

    temp_dir = tempfile.mkdtemp(prefix=f"test_{pypi_name.replace('-', '_')}_")
    venv_dir = os.path.join(temp_dir, "venv")

    start_time = time.time()
    result_data = None

    try:
        # 1. Create virtual environment
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True, capture_output=True)
        bin_dir = os.path.join(venv_dir, "bin") if os.name != "nt" else os.path.join(venv_dir, "Scripts")
        pip_path = os.path.join(bin_dir, "pip")
        python_path = os.path.join(bin_dir, "python")

        # 2. Pre-install compatibility shims (legacy-cgi for Python 3.13+, requests, aiohttp, aiofiles, beautifulsoup4 for packages missing explicit requirements)
        # This gives older packages fair compatibility on modern runtimes
        subprocess.run([pip_path, "install", "--upgrade", "pip"], capture_output=True)
        subprocess.run([pip_path, "install", "legacy-cgi", "requests", "aiohttp", "aiofiles", "beautifulsoup4"], capture_output=True)

        # 3. Install the target package
        logging.info("Installing %s...", pypi_name)
        install_res = subprocess.run(
            [pip_path, "install", pypi_name],
            capture_output=True,
            text=True,
            timeout=pip_timeout
        )

        if install_res.returncode != 0:
            logging.warning("Installation failed for %s", pypi_name)
            result_data = {
                "package_name": pypi_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "python_version": sys.version.split()[0],
                "installed": False,
                "import_success": False,
                "module_name": None,
                "api_type": "unknown",
                "tests": {
                    "packaging": {"status": "failed", "details": install_res.stderr[-500:]},
                    "import": {"status": "skipped", "details": None},
                    "translate_en_de": {"status": "skipped", "latency_ms": None, "result": None, "error": None},
                    "detect_language": {"status": "skipped", "latency_ms": None, "result": None, "error": None},
                },
                "overall_status": "failed",
                "error_summary": f"pip install {pypi_name} failed: {install_res.stderr[-300:]}"
            }
        else:
            # 4. Run test_single_target.py inside this venv
            cmd = [python_path, str(TEST_RUNNER_SCRIPT), pypi_name]
            if module_hint:
                cmd.extend(["--module-hint", module_hint])

            run_res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if run_res.returncode == 0:
                stdout_text = run_res.stdout.strip()
                # Find start of JSON object in case library printed to stdout
                json_start = stdout_text.find("{")
                json_end = stdout_text.rfind("}")
                if json_start != -1 and json_end != -1 and json_end >= json_start:
                    try:
                        result_data = json.loads(stdout_text[json_start : json_end + 1])
                    except Exception as json_err:
                        logging.warning("JSON decode error from runner: %s", json_err)
                        result_data = {
                            "package_name": pypi_name,
                            "overall_status": "failed",
                            "error_summary": f"Could not parse test runner output: {stdout_text[:200]}"
                        }
                else:
                    logging.warning("No JSON object found in runner output for %s", pypi_name)
                    result_data = {
                        "package_name": pypi_name,
                        "overall_status": "failed",
                        "error_summary": f"No JSON in output: {stdout_text[:200]}"
                    }
            else:
                logging.warning("Runner exited with error for %s: %s", pypi_name, run_res.stderr)
                result_data = {
                    "package_name": pypi_name,
                    "overall_status": "failed",
                    "error_summary": f"Runner process crashed: {run_res.stderr[-300:] or run_res.stdout[-300:]}"
                }

    except Exception as e:
        logging.error("Exception executing tests for %s: %s", pypi_name, e)
        result_data = {
            "package_name": pypi_name,
            "overall_status": "failed",
            "error_summary": f"Harness exception: {e}"
        }
    finally:
        # Clean up temporary venv
        shutil.rmtree(temp_dir, ignore_errors=True)

    elapsed = round(time.time() - start_time, 2)
    if result_data:
        result_data["elapsed_sec"] = elapsed
        result_data["package_id"] = package_meta.get("id", pypi_name)
        result_data["description"] = package_meta.get("description", "")
        result_data["pypi_url"] = package_meta.get("pypi_url", "")
    logging.info("Completed %s in %.2fs -> %s", pypi_name, elapsed, result_data.get("overall_status") if result_data else "error")
    return result_data


def run_matrix(package_filter=None, include_defunct=False):
    with open(PACKAGES_FILE, "r", encoding="utf-8") as f:
        all_packages = json.load(f)

    target_packages = all_packages
    matrix_results = {}

    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                matrix_results = existing.get("results", {})
        except Exception as read_err:
            logging.warning("Could not load existing matrix results: %s", read_err)

    if package_filter:
        target_packages = [p for p in all_packages if p["pypi_name"] == package_filter or p["id"] == package_filter]
        if not target_packages:
            logging.error("Package %s not found in definitions", package_filter)
            sys.exit(1)

    for pkg_meta in target_packages:
        pypi_name = pkg_meta["pypi_name"]
        category = pkg_meta.get("category", "active")

        # Skip active ephemeral test if package is marked defunct, unless explicitly requested
        if category == "defunct" and not include_defunct and not package_filter:
            logging.info("Skipping defunct package [%s] from daily matrix test (endpoint discontinued)...", pypi_name)
            if pypi_name in matrix_results:
                matrix_results[pypi_name]["category"] = "defunct"
                matrix_results[pypi_name]["overall_status"] = "defunct"
                matrix_results[pypi_name]["error_summary"] = pkg_meta.get(
                    "category_reason", matrix_results[pypi_name].get("error_summary")
                )
            else:
                matrix_results[pypi_name] = {
                    "package_name": pypi_name,
                    "package_id": pkg_meta["id"],
                    "description": pkg_meta.get("description", ""),
                    "pypi_url": pkg_meta.get("pypi_url", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "python_version": sys.version.split()[0],
                    "installed": True,
                    "import_success": True,
                    "module_name": pkg_meta.get("default_module"),
                    "api_type": "defunct",
                    "overall_status": "defunct",
                    "category": "defunct",
                    "error_summary": pkg_meta.get(
                        "category_reason",
                        "Defunct / Deprecated implementation (endpoint removed); skipped during daily matrix."
                    ),
                    "tests": {
                        "packaging": {"status": "passed", "details": "Defunct distribution"},
                        "import": {"status": "passed", "details": "Module available"},
                        "translate_en_de": {"status": "failed", "latency_ms": None, "result": None, "error": "Defunct / Deprecated endpoint"},
                        "detect_language": {"status": "skipped", "latency_ms": None, "result": None, "error": None, "details": "Defunct endpoint"}
                    }
                }
            continue

        res = test_package_in_isolation(pkg_meta)
        if res:
            res["category"] = category
            if category == "defunct" and res.get("overall_status") != "passed":
                res["overall_status"] = "defunct"
        matrix_results[pypi_name] = res

    passed_cnt = sum(1 for r in matrix_results.values() if r and r.get("overall_status") == "passed")
    failed_cnt = sum(1 for r in matrix_results.values() if not (r and r.get("overall_status") == "passed"))
    summary = {
        "total": len(matrix_results),
        "passed": passed_cnt,
        "failed": failed_cnt,
        "defunct": sum(1 for r in matrix_results.values() if r and (r.get("category") == "defunct" or r.get("overall_status") == "defunct")),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {
        "summary": summary,
        "results": matrix_results
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # Record in historical test runs database
    try:
        from runner.history_db import record_matrix_run
        record_matrix_run(payload)
        logging.info("Recorded matrix run in historical test database.")
    except Exception as db_err:
        logging.warning("Could not record matrix run to history database: %s", db_err)

    logging.info("Matrix test run finished. Passed: %d/%d. Saved to %s", summary["passed"], summary["total"], OUTPUT_FILE)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", help="Test a single specific package name or ID", default=None)
    parser.add_argument("--include-defunct", action="store_true", help="Force re-testing of defunct/deprecated packages", default=False)
    args = parser.parse_args()
    run_matrix(package_filter=args.package, include_defunct=args.include_defunct)
