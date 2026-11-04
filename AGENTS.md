# AGENTS.md

Welcome to **`googletrans-tester`**! This repository provides an agentic testing harness, statistical telemetry collector, and interactive Vite-based dashboard for validating and comparing **all 37 PyPI packages and forks** of the Python `googletrans` ecosystem.

Mirrors and expands upon [`aikenf/googletrans-all`](https://github.com/aikenf/googletrans-all), [`aikenf/googletrans-test`](https://github.com/aikenf/googletrans-test), and [`flynn0/googletrans-curl-tester`](https://github.com/flynn0/googletrans-curl-tester).

---

## 🎯 Architecture & Objectives

There are 37 different PyPI distributions implementing, forking, or wrapping the unofficial Google Translate API:
1. `googletrans`
2. `googletrans-curl`
3. `googletrans-py`
4. `googletrans-py39`
5. `googletrans-python`
6. `googletrans-sw`
7. `googletrans-wheel`
8. `googletrans-di`
9. `googletrans-modified`
10. `py-googletrans`
11. `googletrans-wheel2-py`
12. `googletrans-temp`
13. `googletrans2`
14. `googletrans2020`
15. `googletransapi`
16. `googletransfork`
17. `googletranslate`
18. `googletranslate-neon-plugin`
19. `googletranslate-python`
20. `googletranslator-new`
21. `googletranswheel2`
22. `googletransx`
23. `vtrans`
24. `Flask-Googletrans`
25. `simple-googletrans`
26. `py-googletrans-html`
27. `ggtrans`
28. `paraphrase-googletranslate`
29. `SmallGoogleTranslator`
30. `cloud-translator`
31. `gotranslate`
32. `unlimited-machine-translator`
33. `mintrans`
34. `freetrans-py`
35. `py-trans`
36. `google-translate-py`
37. `python-translator`

Because Google regularly modifies its endpoints, token algorithms (e.g., `TKK`), rate limits, and network requirements, these forks exhibit varying states of functionality:
- **Async vs. Sync & Dual Support:** Modern versions (like `googletrans` 4.0.2) use `httpx` and require `await translator.translate(...)`, whereas legacy forks provide synchronous APIs. Crucially, `googletrans-curl` and `freetrans-py` support **both** paradigms: modern async via `from googletrans import Translator` / `from freetrans import Translator` (with `await translator.translate(...)`) and backward-compatible synchronous usage for older v3.x codebases via `SyncTranslator as Translator` (with `translator.translate(...)`). The runner tests and reports both implementations when present under `implementations`.
- **Import namespaces:** Most forks claim the top-level namespace `googletrans`, while others use custom package modules (e.g. `googletrans_di`, `googletrans_wheel`, `googletranswheel2`, `googletransx`, `vtrans`, `flask_googletrans`, `simple_googletrans`, `googletranslatepy`, `gtranslate`, `mintrans`, `freetrans`, `translator`, `paraphrase_googletranslate`, `unlimited_machine_translator`, `py_trans`, `google_translate_py`, `python_translator`).
- **Python version & dependency incompatibilities:** Older packages depend on removed standard library modules (like Python 3.13+ removing `cgi`, mitigated via `legacy-cgi`), missing requirements declarations (mitigated via `requests`, `aiofiles`, `beautifulsoup4`), or pin older `httpx` submodules (e.g. `ProxiesTypes`).
- **Defunct / Deprecated Implementations:** Packages whose endpoints or scraping structures are permanently removed (e.g. `google-translate-py` and `python-translator`) are cataloged under `"category": "defunct"`. Daily test matrix execution skips live testing for them to conserve resources, while PyPI/pepy/pypistats telemetry continues to be monitored and refreshed daily to track current volume.
- **UI & Theme Requirements:** The dashboard supports dynamic Dark and Light mode switching with CSS custom properties (`[data-theme="dark"]` and `[data-theme="light"]`) and local storage persistence. All tables use separate borders with overflow scrollbars to prevent border collapsing or clipping.

To test them without dependency collision, our agentic harness runs tests in isolated virtual environments or isolated sub-processes for each implementation.

---

## 🛠️ Repository Layout

```
googletrans-tester/
├── .github/
│   └── workflows/
│       ├── test-implementations.yml  # Matrix & scheduled test runner workflow
│       └── deploy-pages.yml          # GitHub Pages Vite dashboard deployment
├── data/
│   ├── packages.json                 # Definition and config for all 37 packages
│   ├── history.db                    # SQLite historical test runs database
│   ├── runs_history.json             # Structured multi-run history export
│   └── latest_results.json           # Cached test results & download telemetry
├── runner/
│   ├── history_db.py                 # SQLite test run recorder and analytics engine
│   ├── fetch_stats.py                # Telemetry collector (PyPI, pypistats.org, pepy.tech)
│   ├── run_matrix.py                 # Multi-package test executor (runs test suite per package)
│   └── test_single_target.py         # Sub-process test runner for an individual package
├── dashboard/                        # Modern Vite + Vanilla JS web application
│   ├── public/
│   │   ├── results.json              # Consumed by the Vite dashboard at runtime
│   │   └── history.json              # Historical runs payload
│   ├── src/
│   │   ├── main.js                   # Reactive UI rendering cards, tables & details
│   │   └── style.css                 # Dark/light theme with non-collapsing borders
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   ├── sync_dashboard_data.py        # Synchronizes runner output to dashboard/public/results.json
│   └── dev.sh                        # Development helper script
├── tests/                            # Unit test suite for harness and config integrity
├── requirements.txt                  # Core harness dependencies
├── requirements-harness.txt          # Runner dependencies (references requirements.txt)
├── README.md                         # Documentation and badges
└── AGENTS.md                         # Agentic guide (this file)
```

---

## 🚀 Key Commands

### 1. Collect Telemetry (PyPI, pypistats.org, pepy.tech)
```bash
python3 runner/fetch_stats.py
```
Fetches:
- Latest release version and upload timestamp from PyPI.
- Total lifetime downloads from pepy.tech.
- 2026 total downloads and last month downloads from pypistats.org.

### 2. Run Implementation Tests
```bash
python3 runner/run_matrix.py
```
Tests all 37 packages (or a specific package with `--package <name>`), recording:
- Installation success / failure
- Import resolution & module name
- Translation capability (English -> German, source detection)
- API style (async vs sync)
- Latency and detailed error diagnosis if failed.

### 3. Sync Data to Dashboard
```bash
python3 scripts/sync_dashboard_data.py
```
Merges test results and download stats into `dashboard/public/results.json` and `data/latest_results.json`.

### 4. Build & Preview Vite Dashboard
```bash
cd dashboard
npm install
npm run build
npm run preview
```

---

## 🔄 CI / GitHub Actions Workflows

1. **`test-implementations.yml` (`.github/workflows/test-implementations.yml`)**:
   - Runs on schedule (`0 5 * * *`) and `workflow_dispatch`.
   - Runs test matrix across implementations and collects latest statistics.
   - Commits updated `data/latest_results.json` and triggers dashboard deployment.

2. **`deploy-pages.yml` (`.github/workflows/deploy-pages.yml`)**:
   - Runs on push to `main` and on completion of `test-implementations.yml`.
   - Builds Vite application in `dashboard/` with base path `./`.
   - Deploys static site to GitHub Pages using official GitHub Actions Pages deployer.

---

## 🤖 Guidelines for AI Agents

- **Idempotency:** When adding new packages or test cases, ensure `data/packages.json` remains the single source of truth for target definitions.
- **Isolation:** Never install candidate packages globally; always test in ephemeral virtual environments or isolated temporary interpreters to avoid clashing `googletrans` namespace modules.
- **Graceful Failure:** Google Translate API requests can return HTTP 429 (rate limits) or network timeouts. Tests must capture and report error diagnostics clearly in the JSON payload without crashing the matrix runner.
- **Dashboard Integrity:** Keep the Vite dashboard dependency-free (vanilla JS + CSS) for fast builds, high reliability, and clean GitHub Pages deployment. Maintain proper CSS scoping for dark/light themes and prevent container border collapse.
