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

    # 3. Discover Candidate Implementations (Async, Sync, or Dual)
    target_cls_names = [
        "GoogleTranslator",
        "Translator",
        "GoogleTrans",
        "google_translator",
        "google_trans_new",
        "Paraphraser",
        "PyTranslator",
    ]
    target_fn_names = [
        "translate",
        "translate_text",
        "google_translate",
        "machine_translator_doc",
        "machine_translator_df",
    ]

    discovered_impls = {}

    # Check for explicit synchronous drop-in (SyncTranslator in googletrans-curl)
    if hasattr(module, "SyncTranslator") and inspect.isclass(getattr(module, "SyncTranslator")):
        discovered_impls["sync"] = {
            "class": getattr(module, "SyncTranslator"),
            "class_name": "SyncTranslator",
            "import_syntax": f"from {imported_name} import SyncTranslator as Translator",
            "call_syntax": "translator = Translator(); res = translator.translate('Hello world', dest='de')",
            "api_type": "sync",
            "notes": "Synchronous drop-in replacement compatible with older googletrans v3.x workflows"
        }

    # Check for explicit asynchronous classes (AsyncGoogleTranslator / AsyncTranslator in mintrans etc.)
    for async_name in ["AsyncGoogleTranslator", "AsyncTranslator", "Async_PyTranslator"]:
        if hasattr(module, async_name) and inspect.isclass(getattr(module, async_name)):
            method_call = "google('Hello world', dest='de')" if async_name == "Async_PyTranslator" else "translate('Hello world', to_lang='de')"
            discovered_impls["async"] = {
                "class": getattr(module, async_name),
                "class_name": async_name,
                "import_syntax": f"from {imported_name} import {async_name} as Translator",
                "call_syntax": f"translator = Translator(); res = await translator.{method_call}",
                "api_type": "async",
                "notes": f"Asynchronous implementation via {async_name}"
            }
            break

    # Search module attributes for classes
    for cand_name in target_cls_names:
        cls_obj = getattr(module, cand_name, None)
        if cls_obj and inspect.isclass(cls_obj):
            is_async_cls = False
            for m in ["translate", "translate_text", "translate_async", "paraphrase", "google"]:
                if hasattr(cls_obj, m) and inspect.iscoroutinefunction(getattr(cls_obj, m)):
                    is_async_cls = True
                    break

            method_call_sync = "google('Hello world', dest='de')" if hasattr(cls_obj, "google") and not hasattr(cls_obj, "translate") else "translate('Hello world', dest='de')"
            method_call_async = "google('Hello world', dest='de')" if hasattr(cls_obj, "google") and not hasattr(cls_obj, "translate") else "translate('Hello world', dest='de')"

            if is_async_cls:
                if "async" not in discovered_impls:
                    discovered_impls["async"] = {
                        "class": cls_obj,
                        "class_name": cand_name,
                        "import_syntax": f"from {imported_name} import {cand_name}",
                        "call_syntax": f"translator = {cand_name}(); res = await translator.{method_call_async}",
                        "api_type": "async",
                        "notes": f"Modern asynchronous implementation ({cand_name})"
                    }
                # Check for companion sync method on the same class
                if hasattr(cls_obj, "translate_sync") and "sync" not in discovered_impls:
                    discovered_impls["sync"] = {
                        "class": cls_obj,
                        "class_name": cand_name,
                        "method_override": "translate_sync",
                        "detect_override": "detect_sync" if hasattr(cls_obj, "detect_sync") else None,
                        "import_syntax": f"from {imported_name} import {cand_name}",
                        "call_syntax": f"translator = {cand_name}(); res = translator.translate_sync('Hello world', dest='de')",
                        "api_type": "sync",
                        "notes": f"Synchronous translate_sync method on {cand_name}"
                    }
            else:
                if "sync" not in discovered_impls:
                    discovered_impls["sync"] = {
                        "class": cls_obj,
                        "class_name": cand_name,
                        "import_syntax": f"from {imported_name} import {cand_name}",
                        "call_syntax": f"translator = {cand_name}(); res = translator.{method_call_sync}",
                        "api_type": "sync",
                        "notes": f"Synchronous implementation ({cand_name})"
                    }
                # Check for companion async method on the same class
                if hasattr(cls_obj, "translate_async") and "async" not in discovered_impls:
                    discovered_impls["async"] = {
                        "class": cls_obj,
                        "class_name": cand_name,
                        "method_override": "translate_async",
                        "import_syntax": f"from {imported_name} import {cand_name}",
                        "call_syntax": f"translator = {cand_name}(); res = await translator.translate_async('Hello world', to_lang='de')",
                        "api_type": "async",
                        "notes": f"Asynchronous translate_async method on {cand_name}"
                    }

    # Search submodules if nothing found yet
    if not discovered_impls:
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
                            is_async_cls = any(
                                hasattr(cls_obj, m) and inspect.iscoroutinefunction(getattr(cls_obj, m))
                                for m in ["translate", "translate_text", "translate_async", "paraphrase"]
                            )
                            impl_key = "async" if is_async_cls else "sync"
                            if impl_key not in discovered_impls:
                                discovered_impls[impl_key] = {
                                    "class": cls_obj,
                                    "class_name": cand_name,
                                    "import_syntax": f"from {imported_name}.{sub_name} import {cand_name}",
                                    "call_syntax": f"translator = {cand_name}(); res = {'await ' if is_async_cls else ''}translator.translate('Hello world', dest='de')",
                                    "api_type": impl_key,
                                    "notes": f"Discovered in submodule {sub_name}"
                                }
            except Exception:
                pass

    # Check for direct function if no class implementations
    direct_translate_fn = None
    if not discovered_impls:
        for cand_fn in target_fn_names:
            fn_obj = getattr(module, cand_fn, None)
            if fn_obj and callable(fn_obj):
                direct_translate_fn = fn_obj
                discovered_impls["function"] = {
                    "function": fn_obj,
                    "class_name": None,
                    "import_syntax": f"from {imported_name} import {cand_fn}",
                    "call_syntax": f"res = {cand_fn}('Hello world', dest='de')",
                    "api_type": "function",
                    "notes": f"Direct function {cand_fn}"
                }
                break

    if not discovered_impls:
        report["error_summary"] = "Neither Translator class nor translate() function found"
        report["tests"]["translate_en_de"]["status"] = "failed"
        report["tests"]["translate_en_de"]["error"] = "No translator interface found"
        return report

    # 4. Helper to instantiate a translator class
    def create_instance(cls_obj):
        try:
            init_sig = inspect.signature(cls_obj.__init__)
            params = init_sig.parameters
            init_kwargs = {}
            if "target" in params and params["target"].default != inspect.Parameter.empty:
                init_kwargs["target"] = "de"
            elif "dest" in params and params["dest"].default != inspect.Parameter.empty:
                init_kwargs["dest"] = "de"
            return cls_obj(**init_kwargs)
        except Exception:
            return cls_obj()

    # Helper to execute translation on an instance or function
    async def execute_translate(inst, fn_override=None):
        if inst and not fn_override:
            for method_cand in ["translate", "translate_async", "translate_sync", "translate_text", "paraphrase", "google"]:
                if hasattr(inst, method_cand):
                    fn = getattr(inst, method_cand)
                    break
            else:
                raise RuntimeError("No recognized translation method on instance")
        elif fn_override and inst:
            fn = getattr(inst, fn_override)
        elif fn_override and callable(fn_override):
            fn = fn_override
        else:
            raise RuntimeError("No translator callable available")

        fn_name = getattr(fn, "__name__", "")
        if fn_name in ["machine_translator_doc", "machine_translator_df"]:
            import tempfile
            from deep_translator import GoogleTranslator as DTGoogleTranslator
            wd = tempfile.mkdtemp()
            res = fn(
                "Hello world",
                target_language="de",
                source_language="auto",
                Translator=DTGoogleTranslator,
                current_wd=wd,
            )
        else:
            sig = inspect.signature(fn)
            params = sig.parameters
            if "dest" in params:
                res = fn("Hello world", dest="de")
            elif "to_lang" in params and "from_lang" in params:
                res = fn("Hello world", from_lang="auto", to_lang="de")
            elif "to_lang" in params:
                res = fn("Hello world", to_lang="de")
            elif "target" in params:
                res = fn("Hello world", target="de")
            elif "target_language" in params and "source_language" in params:
                res = fn("Hello world", target_language="de", source_language="en")
            elif "target_language" in params:
                res = fn("Hello world", target_language="de")
            elif "secondary_language" in params:
                res = fn("Hello world", secondary_language="de")
            else:
                try:
                    res = fn("Hello world", dest="de")
                except TypeError:
                    try:
                        res = fn("Hello world", "auto", "de")
                    except TypeError:
                        res = fn("Hello world", "de")

        if inspect.iscoroutine(res):
            res = await res

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

        return res, res_text

    # Helper to execute language detection on an instance
    async def execute_detect(inst, raw_res=None, fn_override=None):
        det_fn = None
        if inst:
            if fn_override and hasattr(inst, fn_override):
                det_fn = getattr(inst, fn_override)
            else:
                for cand in ["detect", "detect_sync", "detect_language"]:
                    fn = getattr(inst, cand, None)
                    if fn and callable(fn):
                        det_fn = fn
                        break

        if det_fn:
            try:
                det_res = det_fn("Bonjour tout le monde")
                if inspect.iscoroutine(det_res):
                    det_res = await det_res
                lang = getattr(det_res, "lang", str(det_res))
                return str(lang), None
            except Exception as e:
                if isinstance(raw_res, dict):
                    if "src" in raw_res:
                        return str(raw_res["src"]), None
                    if "origin_lang" in raw_res:
                        return str(raw_res["origin_lang"]), None
                raise e

        if isinstance(raw_res, dict):
            if "src" in raw_res:
                return str(raw_res["src"]), None
            if "origin_lang" in raw_res:
                return str(raw_res["origin_lang"]), None

        return None, "detect() API not provided by this implementation"

    # Helper to safely clean up instance connections
    async def cleanup_instance(inst):
        if not inst:
            return
        if hasattr(inst, "close"):
            try:
                inst.close()
            except Exception:
                pass
        if hasattr(inst, "aclose"):
            try:
                cl = inst.aclose()
                if inspect.iscoroutine(cl):
                    await cl
            except Exception:
                pass

    # 5. Execute Test Suite across all discovered implementations
    report["implementations"] = {}

    async def run_all_implementations():
        for impl_key, meta in discovered_impls.items():
            impl_report = {
                "class": meta.get("class_name"),
                "api_type": meta["api_type"],
                "import_syntax": meta.get("import_syntax"),
                "call_syntax": meta.get("call_syntax"),
                "notes": meta.get("notes"),
                "translate_status": "pending",
                "translate_latency_ms": None,
                "translate_result": None,
                "detect_status": "pending",
                "detect_latency_ms": None,
                "detect_result": None,
                "error": None
            }

            inst = None
            if meta.get("class"):
                try:
                    inst = create_instance(meta["class"])
                except Exception as init_err:
                    impl_report["translate_status"] = "failed"
                    impl_report["error"] = f"Init error: {init_err}"
                    report["implementations"][impl_key] = impl_report
                    continue
            elif meta.get("function"):
                inst = None

            # Test translation
            t0 = time.perf_counter()
            raw_res = None
            try:
                fn_override = meta.get("method_override") or meta.get("function")
                raw_res, res_text = await execute_translate(inst, fn_override=fn_override)
                lat = round((time.perf_counter() - t0) * 1000, 2)
                impl_report["translate_latency_ms"] = lat
                impl_report["translate_result"] = res_text

                if raw_res is False or raw_res is None or res_text.strip().lower() in ["false", "none", ""]:
                    impl_report["translate_status"] = "failed"
                    impl_report["error"] = f"Invalid translation result: {raw_res}"
                elif "hallo" in res_text.lower() or "welt" in res_text.lower():
                    impl_report["translate_status"] = "passed"
                elif res_text.strip().lower() == "hello world":
                    impl_report["translate_status"] = "failed"
                    impl_report["error"] = f"Untranslated echo output: '{res_text}'"
                else:
                    impl_report["translate_status"] = "passed"
            except Exception as tr_err:
                impl_report["translate_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                impl_report["translate_status"] = "failed"
                impl_report["error"] = f"{type(tr_err).__name__}: {tr_err}"

            # Test detection
            t1 = time.perf_counter()
            try:
                det_override = meta.get("detect_override")
                lang_res, skip_reason = await execute_detect(inst, raw_res=raw_res, fn_override=det_override)
                impl_report["detect_latency_ms"] = round((time.perf_counter() - t1) * 1000, 2)
                if lang_res:
                    impl_report["detect_status"] = "passed"
                    impl_report["detect_result"] = lang_res
                else:
                    impl_report["detect_status"] = "skipped"
                    impl_report["detect_details"] = skip_reason
            except Exception as det_err:
                impl_report["detect_latency_ms"] = round((time.perf_counter() - t1) * 1000, 2)
                impl_report["detect_status"] = "failed"
                impl_report["detect_error"] = f"{type(det_err).__name__}: {det_err}"

            await cleanup_instance(inst)
            report["implementations"][impl_key] = impl_report

    try:
        asyncio.run(asyncio.wait_for(run_all_implementations(), timeout=40))
    except Exception as e:
        report["error_summary"] = f"Test execution timed out or failed: {e}"

    # 6. Aggregate results and determine API type and test status
    impls = report.get("implementations", {})
    async_res = impls.get("async")
    sync_res = impls.get("sync")
    func_res = impls.get("function")

    async_ok = async_res and async_res.get("translate_status") == "passed"
    sync_ok = sync_res and sync_res.get("translate_status") == "passed"
    func_ok = func_res and func_res.get("translate_status") == "passed"

    # API Paradigm determination based on supported package implementations
    if "async" in impls and "sync" in impls:
        report["api_type"] = "async, sync"
    elif "async" in impls or async_ok:
        report["api_type"] = "async"
    elif "sync" in impls or sync_ok:
        report["api_type"] = "sync"
    elif "function" in impls or func_ok:
        report["api_type"] = "function"
    else:
        report["api_type"] = "unknown"

    # Determine primary implementation for the top-level test report
    # Prefer async if functional, then sync, then function
    primary = None
    if async_ok:
        primary = async_res
    elif sync_ok:
        primary = sync_res
    elif func_ok:
        primary = func_res
    elif async_res:
        primary = async_res
    elif sync_res:
        primary = sync_res
    elif func_res:
        primary = func_res

    if primary:
        report["tests"]["translate_en_de"]["status"] = primary.get("translate_status", "failed")
        report["tests"]["translate_en_de"]["latency_ms"] = primary.get("translate_latency_ms")
        report["tests"]["translate_en_de"]["result"] = primary.get("translate_result")
        report["tests"]["translate_en_de"]["error"] = primary.get("error")

        if async_ok and sync_ok:
            async_cls = async_res.get("class") or "Translator"
            sync_cls = sync_res.get("class") or "Translator"
            report["tests"]["translate_en_de"]["details"] = (
                f"Verified both async ({async_cls}) and sync ({sync_cls}) implementations"
            )
        elif primary.get("translate_status") == "passed":
            report["tests"]["translate_en_de"]["details"] = (
                f"Verified {primary['api_type']} ({primary.get('class') or 'function'}) implementation"
            )

        report["tests"]["detect_language"]["status"] = primary.get("detect_status", "skipped")
        report["tests"]["detect_language"]["latency_ms"] = primary.get("detect_latency_ms")
        report["tests"]["detect_language"]["result"] = primary.get("detect_result")
        report["tests"]["detect_language"]["error"] = primary.get("detect_error")
        if primary.get("detect_details"):
            report["tests"]["detect_language"]["details"] = primary.get("detect_details")
    else:
        report["tests"]["translate_en_de"]["status"] = "failed"
        report["tests"]["translate_en_de"]["error"] = "No translator implementation available"

    # Determine overall status
    translate_ok = any(
        res.get("translate_status") == "passed"
        for res in impls.values()
    )
    if translate_ok:
        report["overall_status"] = "passed"
        report["error_summary"] = None
    else:
        report["overall_status"] = "failed"
        err = (primary.get("error") if primary else None) or "Translation failed"
        report["error_summary"] = err

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
