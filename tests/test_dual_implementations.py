"""
tests/test_dual_implementations.py
Unit tests verifying and documenting dual implementation functionality
(async v4.x vs sync v3.x SyncTranslator) across googletrans distributions.
"""

import inspect
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from runner.test_single_target import run_test


class MockDualModule:
    """Mock module simulating googletrans-curl with both async Translator and sync SyncTranslator."""
    __version__ = "4.1.0"

    class Translator:
        async def translate(self, text, dest="en", **kwargs):
            class Res:
                text = "Hallo Welt"
            return Res()

        async def detect(self, text, **kwargs):
            class Det:
                lang = "fr"
            return Det()

    class SyncTranslator:
        def translate(self, text, dest="en", **kwargs):
            class Res:
                text = "Hallo Welt"
            return Res()

        def detect(self, text, **kwargs):
            class Det:
                lang = "fr"
            return Det()


class MockSyncOnlyModule:
    """Mock module simulating legacy forks (e.g. googletrans-py) with sync Translator only."""
    __version__ = "3.1.0a0"

    class Translator:
        def translate(self, text, dest="en", **kwargs):
            class Res:
                text = "Hallo Welt"
            return Res()

        def detect(self, text, **kwargs):
            class Det:
                lang = "fr"
            return Det()


class MockAsyncOnlyModule:
    """Mock module simulating standard googletrans 4.0.2 with async Translator only."""
    __version__ = "4.0.2"

    class Translator:
        async def translate(self, text, dest="en", **kwargs):
            class Res:
                text = "Hallo Welt"
            return Res()

        async def detect(self, text, **kwargs):
            class Det:
                lang = "fr"
            return Det()


def test_googletrans_curl_import_compatibility_simulation():
    """
    Documents and verifies that older synchronous v3.x syntax:
        from googletrans import SyncTranslator as Translator
        translator = Translator()
        res = translator.translate('Hello world', dest='de')
    and modern asynchronous v4.x syntax:
        from googletrans import Translator
        translator = Translator()
        res = await translator.translate('Hello world', dest='de')
    are both fully supported by googletrans-curl.
    """
    mod = MockDualModule()

    # 1. Sync v3.x drop-in usage
    SyncTranslator = getattr(mod, "SyncTranslator")
    sync_t = SyncTranslator()
    assert hasattr(sync_t, "translate")
    assert not inspect.iscoroutinefunction(sync_t.translate)
    sync_res = sync_t.translate("Hello world", dest="de")
    assert sync_res.text == "Hallo Welt"

    # 2. Async v4.x usage
    AsyncTranslator = getattr(mod, "Translator")
    async_t = AsyncTranslator()
    assert hasattr(async_t, "translate")
    assert inspect.iscoroutinefunction(async_t.translate)


def test_dual_implementation_discovery_in_matrix_results():
    """Verifies that data/matrix_results.json contains both async and sync implementations for googletrans-curl."""
    import json
    matrix_file = BASE_DIR / "data" / "matrix_results.json"
    if not matrix_file.exists():
        pytest.skip("matrix_results.json not found")

    with open(matrix_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    curl_res = data.get("results", {}).get("googletrans-curl")
    if not curl_res or not curl_res.get("installed"):
        pytest.skip("googletrans-curl not tested in matrix_results yet")

    assert curl_res["api_type"] == "async, sync"
    assert "implementations" in curl_res
    impls = curl_res["implementations"]

    assert "async" in impls
    assert "sync" in impls
    assert impls["sync"]["class"] == "SyncTranslator"
    assert "SyncTranslator as Translator" in impls["sync"]["import_syntax"]
    assert impls["sync"]["translate_status"] == "passed"

    assert impls["async"]["class"] == "Translator"
    assert impls["async"]["translate_status"] == "passed"
    assert "both async" in curl_res["tests"]["translate_en_de"]["details"].lower()


def test_all_four_dual_packages_in_matrix_results():
    """Verifies that googletrans-curl, mintrans, googletranslator-new, and SmallGoogleTranslator report dual async, sync support."""
    import json
    matrix_file = BASE_DIR / "data" / "matrix_results.json"
    if not matrix_file.exists():
        pytest.skip("matrix_results.json not found")

    with open(matrix_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", {})
    expected_dual = ["googletrans-curl", "mintrans", "googletranslator-new", "SmallGoogleTranslator"]

    for name in expected_dual:
        pkg = results.get(name)
        assert pkg is not None, f"Package {name} should be present in results"
        assert pkg.get("api_type") == "async, sync", f"Package {name} should have api_type 'async, sync', got {pkg.get('api_type')}"
        impls = pkg.get("implementations", {})
        assert "async" in impls and "sync" in impls, f"Package {name} should have both async and sync implementations"
