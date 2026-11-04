# googletrans-tester

[![Test Implementations Matrix](https://github.com/flynn0/googletrans-tester/actions/workflows/test-implementations.yml/badge.svg)](https://github.com/flynn0/googletrans-tester/actions/workflows/test-implementations.yml)
[![Deploy Dashboard to GitHub Pages](https://github.com/flynn0/googletrans-tester/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/flynn0/googletrans-tester/actions/workflows/deploy-pages.yml)
[![Latest Release](https://img.shields.io/github/v/release/flynn0/googletrans-tester?color=blue)](https://github.com/flynn0/googletrans-tester/releases/tag/v0.1.3)

An agentic multi-target testing harness, statistical telemetry collector, and interactive Vite dashboard for validating and comparing **all 37 major PyPI packages and forks** of the Python `googletrans` ecosystem.

Mirrors and expands upon [`aikenf/googletrans-all`](https://github.com/aikenf/googletrans-all), [`aikenf/googletrans-test`](https://github.com/aikenf/googletrans-test), and [`flynn0/googletrans-curl-tester`](https://github.com/flynn0/googletrans-curl-tester).

---

## 📊 Live Dashboard

The interactive test dashboard is deployed to GitHub Pages:
👉 **[https://flynn0.github.io/googletrans-tester/](https://flynn0.github.io/googletrans-tester/)**

### Dashboard Features
- **Dark & Light Mode Switch:** One-click toggle in the header with persistent theme storage in `localStorage` and automatic OS preference detection.
- **Responsive, Non-Collapsing UI:** Clean separated borders, responsive grid layouts (`auto-fit`/`auto-fill`), and horizontal scroll views for full data visibility on desktop, tablet, and mobile without clipping.
- **30-Day Statuspage SLA Tick Bars:** Discrete daily slot visualizations showing reliability, uptime percentage, and historical transitions.
- **Working vs. Failing Status:** Real-time test results across all 37 candidate implementations.
- **PyPI & Telemetry Stats:** Lifetime downloads (pepy.tech), 2026 current year downloads (pypistats.org), and last month active volume.
- **Detailed Inspection Drawer:** View import resolutions, latency (ms), async vs. sync signatures, and error diagnostics.
- **Instant Search & Filter:** Filter by API paradigm (`async` / `sync`) or test status.

---

## 📦 Evaluated Implementations (37 Packages)

### Active & Evaluated Forks (35 Packages)

| Package | Status | API Paradigm | Lifetime DL (pepy) | Description |
|---|---|---|---|---|
| [`googletrans`](https://pypi.org/project/googletrans/) | ✅ PASS | `async` | 99.0M | The original and most widespread unofficial Google Translate API library. |
| [`googletrans-py`](https://pypi.org/project/googletrans-py/) | ✅ PASS | `sync` | 2.0M | Fork packaging synchronous 4.0.0 API. |
| [`Flask-Googletrans`](https://pypi.org/project/Flask-Googletrans/) | ✅ PASS | `async` | 88.0k | Flask web application extension for automated template translation. |
| [`py-trans`](https://pypi.org/project/py-trans/) | ✅ PASS | `async, sync` | 26.0k | Free translation library supporting multiple providers (Google Translate, Translate Dict) with async and sync support. |
| [`googletrans-py39`](https://pypi.org/project/googletrans-py39/) | ✅ PASS | `sync` | 23.0k | Python 3.9 compatibility fork. |
| [`googletrans-modified`](https://pypi.org/project/googletrans-modified/) | ✅ PASS | `sync` | 15.0k | Modified release with adjusted query handling. |
| [`mintrans`](https://pypi.org/project/mintrans/) | ✅ PASS | `async, sync` | 8.0k | Free multi-service translation API wrapper supporting Google Translate, Bing, and DeepL. |
| [`googletransfork`](https://pypi.org/project/googletransfork/) | ✅ PASS | `sync` | 6.0k | Fork package based on early googletrans release. |
| [`googletrans-sw`](https://pypi.org/project/googletrans-sw/) | ✅ PASS | `sync` | 4.0k | Swahili / customized distribution fork. |
| [`googletrans-wheel2-py`](https://pypi.org/project/googletrans-wheel2-py/) | ✅ PASS | `sync` | 3.0k | Wheel repackage fork targeting modern python versions. |
| [`googletranswheel2`](https://pypi.org/project/googletranswheel2/) | ✅ PASS | `sync` | 2.0k | Repackaged wheel with googletranswheel2 namespace. |
| [`gotranslate`](https://pypi.org/project/gotranslate/) | ✅ PASS | `sync` | 1.0k | Lightweight GoogleTranslator library with language detection, details, and emoji flags. |
| [`googletrans-curl`](https://pypi.org/project/googletrans-curl/) | ✅ PASS | `async, sync` | 903 | Modern fork utilizing curl-cffi and httpx[http2] for enhanced bypass and stability; supports both v4.x async Translator and legacy v3.x SyncTranslator. |
| [`freetrans-py`](https://pypi.org/project/freetrans-py/) | ✅ PASS | `async, sync` | 0 | Free multi-provider translation library with curl-cffi anti-rate-limiting; supports both async Translator and sync SyncTranslator. |
| [`googletransx`](https://pypi.org/project/googletransx/) | ❌ FAIL | `sync` | 1.0M | Independent fork using the googletransx namespace. |
| [`googletrans2`](https://pypi.org/project/googletrans2/) | ❌ FAIL | `sync` | 317.0k | Alternative distribution tracking the googletrans 2.x branch. |
| [`googletranslate`](https://pypi.org/project/googletranslate/) | ❌ FAIL | `-` | 177.0k | Candidate PyPI namespace tested for package availability. |
| [`ggtrans`](https://pypi.org/project/ggtrans/) | ❌ FAIL | `sync` | 157.0k | Lightweight repackage of free Google Translate API for Python. |
| [`googletrans2020`](https://pypi.org/project/googletrans2020/) | ❌ FAIL | `-` | 105.0k | Community fork providing updated translation endpoints from 2020. |
| [`py-googletrans`](https://pypi.org/project/py-googletrans/) | ❌ FAIL | `-` | 84.0k | PyPI release published under original py-googletrans repository name. |
| [`cloud-translator`](https://pypi.org/project/cloud-translator/) | ❌ FAIL | `sync` | 30.0k | Unified translation wrapper targeting Google Translate, Baidu, and Tencent. |
| [`paraphrase-googletranslate`](https://pypi.org/project/paraphrase-googletranslate/) | ❌ FAIL | `sync` | 25.0k | Paraphrasing engine built on top of google-trans-new. |
| [`googletranslate-python`](https://pypi.org/project/googletranslate-python/) | ❌ FAIL | `sync` | 22.0k | Google Translate client built on top of deep-translator. |
| [`googletrans-temp`](https://pypi.org/project/googletrans-temp/) | ❌ FAIL | `sync` | 21.0k | Temporary mirror release of googletrans v2.3.0. |
| [`googletransapi`](https://pypi.org/project/googletransapi/) | ❌ FAIL | `-` | 18.0k | Wrapper package providing translation and MP3 audio generation. |
| [`unlimited-machine-translator`](https://pypi.org/project/unlimited-machine-translator/) | ❌ FAIL | `function` | 16.0k | Batch document and DataFrame machine translation leveraging Google Translate. |
| [`simple-googletrans`](https://pypi.org/project/simple-googletrans/) | ❌ FAIL | `-` | 13.0k | Simple CLI and Python wrapper around googletrans with logging and batching. |
| [`googletrans-python`](https://pypi.org/project/googletrans-python/) | ❌ FAIL | `function` | 11.0k | Alternative wrapper providing direct translate() function. |
| [`SmallGoogleTranslator`](https://pypi.org/project/SmallGoogleTranslator/) | ❌ FAIL | `async, sync` | 9.0k | Minimalist async/sync Google Translator library scraping the web endpoint. |
| [`googletrans-di`](https://pypi.org/project/googletrans-di/) | ❌ FAIL | `-` | 9.0k | Fork using googletrans_di namespace. |
| [`googletranslator-new`](https://pypi.org/project/googletranslator-new/) | ❌ FAIL | `async, sync` | 6.0k | Convenient Russian/multilingual Google Translator client wrapper. |
| [`py-googletrans-html`](https://pypi.org/project/py-googletrans-html/) | ❌ FAIL | `sync` | 6.0k | Google Translate fork with specialized HTML preservation. |
| [`vtrans`](https://pypi.org/project/vtrans/) | ❌ FAIL | `sync` | 5.0k | Cross-platform self-updating translator supporting up to 130 languages. |
| [`googletrans-wheel`](https://pypi.org/project/googletrans-wheel/) | ❌ FAIL | `sync` | 2.0k | Binary wheel build with googletrans_wheel module namespace. |
| [`googletranslate-neon-plugin`](https://pypi.org/project/googletranslate-neon-plugin/) | ❌ FAIL | `-` | 2.0k | Neon AI framework translation plugin powered by Google Translate. |

### ⚠️ Defunct or Deprecated Implementations (2 Packages)

These packages rely on endpoints or HTML structures that have been permanently removed or discontinued by Google. To avoid wasted resources, daily matrix execution skips live testing for them, while download statistics continue to be collected and updated daily:

| Package | Status | Lifetime DL | 2026 Volume | Last Month | Reason / Defunct Endpoint |
|---|---|---|---|---|---|
| [`google-translate-py`](https://pypi.org/project/google-translate-py/) | ⚠️ DEFUNCT | 61.0k | ~1.8k | ~200 | Defunct Google Apps Script macro endpoint (`script.google.com/macros/s/AKfycb...` discontinued). |
| [`python-translator`](https://pypi.org/project/python-translator/) | ⚠️ DEFUNCT | 18.0k | ~1.5k | ~180 | Defunct HTML scraping target (`div.result-container` removed from Google Translate web interface). |

---

## ⚡ Dual Async & Synchronous Implementation Support

Modern `googletrans` forks have bifurcated across v3.x (synchronous) and v4.x (asynchronous with `httpx`):

### 1. `googletrans-curl` & `freetrans-py` (Dual Support)
Both `googletrans-curl` and `freetrans-py` provide full backward and modern forward compatibility out of the box using `curl-cffi` to eliminate HTTP 429 rate limits:

- **Modern Asynchronous API (v4.x compatible):**
  ```python
  import asyncio
  from googletrans import Translator
  # Or: from freetrans import Translator

  async def main():
      translator = Translator()
      result = await translator.translate("Hello world", dest="de")
      print(result.text)  # Hallo Welt

  asyncio.run(main())
  ```

- **Legacy Synchronous Drop-in API (v3.x compatible):**
  Compatible drop-in replacement for older codebases that used `googletrans` v3.x, requiring only updating the import statement:
  ```python
  from googletrans import SyncTranslator as Translator
  # Or: from freetrans import SyncTranslator as Translator

  translator = Translator()
  result = translator.translate("Hello world", dest="de")
  print(result.text)  # Hallo Welt
  ```
  `SyncTranslator` executes blocking requests safely via a persistent background event loop thread, supporting `translate()`, `detect()`, context managers (`with SyncTranslator() as translator:`), and session cleanup. Additionally, the async `Translator` exposes synchronous helpers `translator.translate_sync()` and `translator.detect_sync()`.

### 2. Other Evaluated Variants
- **`py-trans`:** Provides both `PyTranslator` (synchronous) and `Async_PyTranslator` (asynchronous) with multiple backend providers, passing translation tests.
- **`google-translate-py`:** Defines `Translator` and `AsyncTranslator` wrappers over Google Apps Script macros, but the endpoint currently fails.
- **`mintrans`:** Provides separate `GoogleTranslator` (synchronous) and `AsyncGoogleTranslator` (asynchronous) classes, though currently throttled by Google Translate rate limits on unauthenticated endpoints.
- **`googletranslator-new` & `SmallGoogleTranslator`:** Define classes with both `translate_sync` and `translate_async` methods, but currently fail due to obsolete token and HTML parsing algorithms.
- **Other 30 forks:** Either provide purely synchronous APIs (e.g. `googletrans-py`, `googletrans-sw`, `googletrans-modified`, `gotranslate`, `python-translator`) or strictly asynchronous APIs (`googletrans` 4.0.2, `Flask-Googletrans`). Official `googletrans` 4.0.2 does not provide `SyncTranslator`.

---

## 🛠️ Repository Layout

```
googletrans-tester/
├── .github/
│   └── workflows/
│       ├── test-implementations.yml  # Daily matrix test & telemetry updater
│       └── deploy-pages.yml          # GitHub Pages Vite deployment on push
├── data/
│   ├── packages.json                 # Single source of truth for all 37 packages
│   ├── history.db                    # SQLite historical test runs database
│   ├── runs_history.json             # Historical test runs JSON export
│   ├── stats.json                    # Raw telemetry data (PyPI, pypistats, pepy)
│   ├── matrix_results.json           # Raw harness test results
│   └── latest_results.json           # Combined dataset consumed by agents & dashboard
├── runner/
│   ├── history_db.py                 # SQLite test run recorder and analytics engine
│   ├── fetch_stats.py                # Telemetry collector
│   ├── run_matrix.py                 # Multi-target isolated test executor
│   └── test_single_target.py         # Sub-process test runner for a single target
├── dashboard/                        # Modern Vite + Vanilla JS web application
│   ├── public/
│   │   ├── results.json              # Dashboard data payload
│   │   └── history.json              # Historical runs payload
│   ├── src/
│   │   ├── main.js                   # Reactive UI rendering with dark/light mode
│   │   └── style.css                 # Responsive theme, dark/light CSS variables
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   ├── sync_dashboard_data.py        # Synchronizer for test and stats datasets
│   └── dev.sh                        # Development helper script
├── requirements.txt                  # Core harness dependencies
├── requirements-harness.txt          # Runner dependencies (references requirements.txt)
├── tests/                            # Test suite for harness and configuration integrity
├── AGENTS.md                         # Agentic guide and instructions
└── README.md                         # Repository documentation
```

---

## 🚀 Quickstart & Commands

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run harness unit tests
pytest tests/ -v
```

### 1. Collect Telemetry
```bash
python3 runner/fetch_stats.py
```
Fetches:
- Latest release version and upload timestamp from PyPI.
- Lifetime total downloads from pepy.tech.
- 2026 total downloads and last month downloads from pypistats.org.

### 2. Run Test Matrix
```bash
# Test all 37 packages
python3 runner/run_matrix.py
```
*(or test a specific package with `--package <name>`)*

### 3. Sync Data & Build Dashboard
```bash
python3 scripts/sync_dashboard_data.py

cd dashboard
npm install
npm run build
npm run preview
```

Or run everything with the helper script:
```bash
./scripts/dev.sh
```

---

## 🔄 CI / GitHub Actions Workflows

1. **`test-implementations.yml`**:
   - Runs on schedule (`0 5 * * *`) and `workflow_dispatch`.
   - Runs test matrix across all 37 implementations and collects latest statistics.
   - Commits updated telemetry data and automatically triggers dashboard deployment.

2. **`deploy-pages.yml`**:
   - Runs on push to `main` and manual dispatch.
   - Builds Vite application in `dashboard/` with relative base path `./`.
   - Deploys static site to GitHub Pages using official GitHub Actions Pages deployer.

---

## 🤖 Guidelines for AI Agents

See [`AGENTS.md`](./AGENTS.md) for full architecture instructions and agentic conventions.
