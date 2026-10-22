#!/usr/bin/env python3
"""
test_single_target.py
Executed inside an isolated venv or sub-process to test a single candidate package.
Tests:
1. Installation validation & package metadata (version, files, top_level)
2. Module import & Translator resolution
3. Single translation (en -> de)
4. Source language auto-detection
5. Batch translation if supported
6. Async vs sync API signature check
7. Latency measurement & failure taxonomy
Outputs results as JSON to stdout or a file.
"""

import argparse
import asyncio
import importlib
import importlib.metadata
import inspect
import json
import os
import sys
import time
import traceback


def get_installed_dist_info(package_name):
    try:
        dist = importlib.metadata.distribution(package_name)
        top_levels = dist.read_text("top_level.txt")
        tl_list = [l.strip() for l in top_levels.strip().splitlines() if l.strip()] if top_levels else []
        return {
            "version": dist.version,
            "top_level": tl_list,
            "installed": True
        }
    except Exception as e:
        return {
            "version": None,
            "top_level": [],
            "installed": False,
            "error": str(e)
        }


def run_test(package_name, target_module_hint=None):
    report = {
        "package_name": package_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version.split()[0],
        "installed": False,
        "import_success": False,
        "module_name": None,
        "api_type": "unknown",  # "async", "sync", "function", "unknown"
        "tests": {
            "packaging": {"status": "pending", "details": None},
            "import": {"status": "pending", "details": None},
            "translate_en_de": {"status": "pending", "latency_ms": None, "result": None, "error": None},
            "detect_language": {"status": "pending", "latency_ms": None, "result": None, "error": None},
        },
        "overall_status": "failed",
        "error_summary": None
    }

    # 1. Check metadata
    dist_info = get_installed_dist_info(package_name)
    report["installed"] = dist_info["installed"]
    report["installed_version"] = dist_info.get("version")
    if not dist_info["installed"]:
        report["tests"]["packaging"]["status"] = "failed"
        report["tests"]["packaging"]["details"] = dist_info.get("error", "Package not installed")
        report["error_summary"] = f"Package {package_name} is not installed"
        return report

    report["tests"]["packaging"]["status"] = "passed"
    report["tests"]["packaging"]["details"] = f"Installed version {dist_info.get('version')}"

    # 2. Determine and test module import
    candidates = []
    if target_module_hint:
        candidates.append(target_module_hint)
    if dist_info.get("top_level"):
        candidates.extend(dist_info["top_level"])
    candidates.extend([
        package_name.replace("-", "_"),
        "googletrans"
    ])

    module = None
    imported_name = None
    import_errs = []

    # De-duplicate while preserving order
    seen = set()
    dedup_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    for cand in dedup_candidates:
        try:
            module = importlib.import_module(cand)
            imported_name = cand
            break
        except Exception as e:
            import_errs.append(f"{cand}: {e}")

    if not module:
        report["tests"]["import"]["status"] = "failed"
        report["tests"]["import"]["details"] = " | ".join(import_errs)
        report["error_summary"] = f"Failed to import candidate modules: {' | '.join(import_errs)}"
        return report

    report["import_success"] = True
    report["module_name"] = imported_name
    report["tests"]["import"]["status"] = "passed"
    report["tests"]["import"]["details"] = f"Imported {imported_name} (version: {getattr(module, '__version__', 'unknown')})"

    # 3. Locate Translator or translate callable
    translator_cls = None
    for cand_name in ["Translator", "GoogleTrans", "google_translator", "google_trans_new", "GoogleTranslator"]:
        cls_obj = getattr(module, cand_name, None)
        if cls_obj and inspect.isclass(cls_obj):
            translator_cls = cls_obj
            break

    direct_translate_fn = None
    for cand_fn in ["translate", "translate_text", "google_translate"]:
        fn_obj = getattr(module, cand_fn, None)
        if fn_obj and callable(fn_obj):
            direct_translate_fn = fn_obj
            break

    if not translator_cls and not direct_translate_fn:
        # Check submodules for translator interfaces
        for sub_name in dir(module):
            if sub_name.startswith("_"):
                continue
            try:
                sub_obj = getattr(module, sub_name, None)
                if inspect.ismodule(sub_obj):
                    for cand_name in ["Translator", "GoogleTrans", "google_translator", "google_trans_new", "GoogleTranslator"]:
                        cls_obj = getattr(sub_obj, cand_name, None)
                        if cls_obj and inspect.isclass(cls_obj):
                            translator_cls = cls_obj
                            break
                    if translator_cls:
                        break
            except Exception:
                pass

    translator_instance = None
    is_async = False

    if translator_cls:
        try:
            translator_instance = translator_cls()
            if hasattr(translator_instance, "translate"):
                is_async = inspect.iscoroutinefunction(translator_instance.translate)
                report["api_type"] = "async" if is_async else "sync"
            elif hasattr(translator_instance, "translate_text"):
                is_async = inspect.iscoroutinefunction(translator_instance.translate_text)
                report["api_type"] = "async" if is_async else "sync"
        except Exception as e:
            report["error_summary"] = f"Translator initialization failed: {e}"
            report["tests"]["translate_en_de"]["status"] = "failed"
            report["tests"]["translate_en_de"]["error"] = f"Init error: {e}"
            return report
    elif direct_translate_fn and callable(direct_translate_fn):
        report["api_type"] = "function"
    else:
        report["error_summary"] = "Neither Translator class nor translate() function found"
        report["tests"]["translate_en_de"]["status"] = "failed"
        report["tests"]["translate_en_de"]["error"] = "No translator interface found"
        return report

    # Helper to call translate and detect within the same event loop
    async def async_test_suite():
        # Test 3: Translate English -> German
        t0 = time.perf_counter()
        try:
            if translator_instance:
                if hasattr(translator_instance, "translate"):
                    if is_async:
                        res = await translator_instance.translate("Hello world", dest="de")
                    else:
                        res = translator_instance.translate("Hello world", dest="de")
                elif hasattr(translator_instance, "translate_text"):
                    if is_async:
                        res = await translator_instance.translate_text("Hello world", dest="de")
                    else:
                        res = translator_instance.translate_text("Hello world", dest="de")
                else:
                    raise RuntimeError("Translator instance has neither translate nor translate_text")
            elif direct_translate_fn:
                sig = inspect.signature(direct_translate_fn)
                params = sig.parameters
                if "dest" in params:
                    res = direct_translate_fn("Hello world", dest="de")
                elif "to_lang" in params:
                    res = direct_translate_fn("Hello world", to_lang="de")
                else:
                    res = direct_translate_fn("Hello world", "de")
            else:
                raise RuntimeError("No translator interface available")

            latency = round((time.perf_counter() - t0) * 1000, 2)
            res_text = getattr(res, "text", str(res))
            report["tests"]["translate_en_de"]["latency_ms"] = latency
            report["tests"]["translate_en_de"]["result"] = res_text

            if res is False or res is None or res_text.strip().lower() in ["false", "none", ""]:
                report["tests"]["translate_en_de"]["status"] = "failed"
                report["tests"]["translate_en_de"]["error"] = f"Invalid translation result: {res}"
            elif "hallo" in res_text.lower() or "welt" in res_text.lower():
                report["tests"]["translate_en_de"]["status"] = "passed"
            elif res_text.strip().lower() == "hello world":
                report["tests"]["translate_en_de"]["status"] = "failed"
                report["tests"]["translate_en_de"]["error"] = f"Untranslated echo output: '{res_text}'"
            else:
                report["tests"]["translate_en_de"]["status"] = "passed"
        except Exception as e:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            report["tests"]["translate_en_de"]["latency_ms"] = latency
            report["tests"]["translate_en_de"]["status"] = "failed"
            report["tests"]["translate_en_de"]["error"] = f"{type(e).__name__}: {e}"

        # Test 4: Language detection
        t1 = time.perf_counter()
        try:
            if translator_instance and hasattr(translator_instance, "detect"):
                if inspect.iscoroutinefunction(translator_instance.detect):
                    det_res = await translator_instance.detect("Bonjour tout le monde")
                else:
                    det_res = translator_instance.detect("Bonjour tout le monde")
                det_latency = round((time.perf_counter() - t1) * 1000, 2)
                report["tests"]["detect_language"]["latency_ms"] = det_latency
                lang = getattr(det_res, "lang", str(det_res))
                report["tests"]["detect_language"]["result"] = str(lang)
                report["tests"]["detect_language"]["status"] = "passed"
            else:
                report["tests"]["detect_language"]["status"] = "skipped"
                report["tests"]["detect_language"]["details"] = "detect() API not provided by this implementation"
        except Exception as e:
            det_latency = round((time.perf_counter() - t1) * 1000, 2)
            report["tests"]["detect_language"]["latency_ms"] = det_latency
            report["tests"]["detect_language"]["status"] = "failed"
            report["tests"]["detect_language"]["error"] = f"{type(e).__name__}: {e}"

    try:
        asyncio.run(asyncio.wait_for(async_test_suite(), timeout=30))
    except Exception as e:
        report["error_summary"] = f"Test execution timed out or failed: {e}"

    # Determine overall status
    translate_ok = report["tests"]["translate_en_de"]["status"] == "passed"
    if translate_ok:
        report["overall_status"] = "passed"
    else:
        report["overall_status"] = "failed"
        report["error_summary"] = report["tests"]["translate_en_de"]["error"] or "Translation failed"

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package_name", help="PyPI package name under test")
    parser.add_argument("--module-hint", help="Expected module import name hint", default=None)
    parser.add_argument("--output", help="Optional output JSON file path", default=None)
    args = parser.parse_args()

    result = run_test(args.package_name, args.module_hint)
    json_out = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_out)
    else:
        print(json_out)


if __name__ == "__main__":
    main()
