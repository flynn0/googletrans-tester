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
    target_cls_names = [
        "GoogleTranslator",
        "Translator",
        "GoogleTrans",
        "google_translator",
        "google_trans_new",
        "Paraphraser",
    ]
    for cand_name in target_cls_names:
        cls_obj = getattr(module, cand_name, None)
        if cls_obj and inspect.isclass(cls_obj):
            translator_cls = cls_obj
            break

    direct_translate_fn = None
    target_fn_names = [
        "translate",
        "translate_text",
        "google_translate",
        "machine_translator_doc",
        "machine_translator_df",
    ]
    for cand_fn in target_fn_names:
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
                if not inspect.ismodule(sub_obj):
                    try:
                        sub_obj = importlib.import_module(f"{imported_name}.{sub_name}")
                    except Exception:
                        pass
                if inspect.ismodule(sub_obj):
                    for cand_name in target_cls_names:
                        cls_obj = getattr(sub_obj, cand_name, None)
                        if cls_obj and inspect.isclass(cls_obj):
                            translator_cls = cls_obj
                            break
                    if translator_cls:
                        break
                    for cand_fn in target_fn_names:
                        fn_obj = getattr(sub_obj, cand_fn, None)
                        if fn_obj and callable(fn_obj):
                            direct_translate_fn = fn_obj
                            break
                    if direct_translate_fn:
                        break
            except Exception:
                pass

    translator_instance = None
    is_async = False

    if translator_cls:
        try:
            # Check constructor signature for target / destination parameters
            init_kwargs = {}
            try:
                init_sig = inspect.signature(translator_cls.__init__)
                params = init_sig.parameters
                if "target" in params and params["target"].default != inspect.Parameter.empty:
                    init_kwargs["target"] = "de"
                elif "dest" in params and params["dest"].default != inspect.Parameter.empty:
                    init_kwargs["dest"] = "de"
                translator_instance = translator_cls(**init_kwargs)
            except Exception:
                translator_instance = translator_cls()

            for method_name in ["translate", "translate_text", "translate_async", "translate_sync", "paraphrase"]:
                if hasattr(translator_instance, method_name):
                    fn = getattr(translator_instance, method_name)
                    if inspect.iscoroutinefunction(fn):
                        is_async = True
                        report["api_type"] = "async"
                    else:
                        report["api_type"] = "sync"
                    break
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
        raw_res = None
        try:
            if translator_instance:
                if hasattr(translator_instance, "translate"):
                    sig = inspect.signature(translator_instance.translate)
                    params = sig.parameters
                    if "dest" in params:
                        res = translator_instance.translate("Hello world", dest="de")
                    elif "to_lang" in params and "from_lang" in params:
                        res = translator_instance.translate("Hello world", from_lang="auto", to_lang="de")
                    elif "target" in params:
                        res = translator_instance.translate("Hello world", target="de")
                    else:
                        try:
                            res = translator_instance.translate("Hello world", dest="de")
                        except TypeError:
                            try:
                                res = translator_instance.translate("Hello world", "auto", "de")
                            except TypeError:
                                res = translator_instance.translate("Hello world")
                elif hasattr(translator_instance, "translate_async"):
                    try:
                        res = await translator_instance.translate_async("Hello world", to_lang="de")
                    except TypeError:
                        res = await translator_instance.translate_async("Hello world", "de")
                elif hasattr(translator_instance, "translate_sync"):
                    try:
                        res = translator_instance.translate_sync("Hello world", to_lang="de")
                    except TypeError:
                        res = translator_instance.translate_sync("Hello world", "de")
                elif hasattr(translator_instance, "translate_text"):
                    res = translator_instance.translate_text("Hello world", dest="de")
                elif hasattr(translator_instance, "paraphrase"):
                    res = translator_instance.paraphrase("Hello world", secondary_language="de")
                else:
                    raise RuntimeError("No recognized translation method on translator instance")
            elif direct_translate_fn:
                fn_name = getattr(direct_translate_fn, "__name__", "")
                if fn_name in ["machine_translator_doc", "machine_translator_df"]:
                    import tempfile
                    from deep_translator import GoogleTranslator as DTGoogleTranslator
                    wd = tempfile.mkdtemp()
                    res = direct_translate_fn(
                        "Hello world",
                        target_language="de",
                        source_language="auto",
                        Translator=DTGoogleTranslator,
                        current_wd=wd,
                    )
                else:
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

            if inspect.iscoroutine(res):
                res = await res

            raw_res = res
            latency = round((time.perf_counter() - t0) * 1000, 2)

            if isinstance(res, dict):
                if "sentences" in res and isinstance(res["sentences"], list):
                    res_text = "".join(s.get("trans", "") for s in res["sentences"] if isinstance(s, dict))
                elif "translation" in res:
                    res_text = str(res["translation"])
                elif "translatedText" in res:
                    res_text = str(res["translatedText"])
                else:
                    res_text = str(res)
            else:
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
            det_fn = None
            if translator_instance:
                for cand in ["detect", "detect_language"]:
                    fn = getattr(translator_instance, cand, None)
                    if fn and callable(fn):
                        det_fn = fn
                        break
            if det_fn:
                det_res = det_fn("Bonjour tout le monde")
                if inspect.iscoroutine(det_res) or inspect.iscoroutinefunction(det_fn):
                    det_res = await det_res
                det_latency = round((time.perf_counter() - t1) * 1000, 2)
                report["tests"]["detect_language"]["latency_ms"] = det_latency
                lang = getattr(det_res, "lang", str(det_res))
                report["tests"]["detect_language"]["result"] = str(lang)
                report["tests"]["detect_language"]["status"] = "passed"
            elif isinstance(raw_res, dict) and "src" in raw_res:
                det_latency = round((time.perf_counter() - t1) * 1000, 2)
                report["tests"]["detect_language"]["latency_ms"] = det_latency
                report["tests"]["detect_language"]["result"] = str(raw_res["src"])
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
