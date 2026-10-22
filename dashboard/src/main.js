import "./style.css";

// Resolve data url dynamically depending on base url (GitHub Pages or local dev)
const DATA_URL = `${import.meta.env.BASE_URL}results.json`;

let currentData = null;
let activeFilter = "all";
let searchQuery = "";
let currentView = "matrix";

function formatNumber(num) {
  if (num === null || num === undefined) return "0";
  return new Intl.NumberFormat("en-US").format(num);
}

function formatCompactNumber(num) {
  if (num === null || num === undefined) return "0";
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}k`;
  return String(num);
}

function formatDate(isoStr) {
  if (!isoStr) return "N/A";
  try {
    const d = new Date(isoStr);
    return d.toISOString().split("T")[0];
  } catch {
    return isoStr;
  }
}

function formatDateTime(isoStr) {
  if (!isoStr) return "N/A";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true
    });
  } catch {
    return isoStr;
  }
}

/**
 * Generates a Statuspage / UptimeRobot-style discrete daily tick bar.
 * Defaults to 30 rolling daily slots.
 */
function createSlaTickBar(history = [], daysCount = 30, isLarge = false) {
  const now = new Date();

  // Index history events by calendar date YYYY-MM-DD
  const dateMap = new Map();
  for (const h of history) {
    if (h.timestamp) {
      const dStr = h.timestamp.split("T")[0];
      // Keep last run in that day if multiple runs occur
      dateMap.set(dStr, h);
    }
  }

  const ticks = [];
  let passedDays = 0;
  let testedDays = 0;

  for (let i = daysCount - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().split("T")[0];
    const displayDate = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const run = dateMap.get(dateStr);

    if (run) {
      testedDays++;
      const isPass = run.status === "passed";
      if (isPass) passedDays++;
      const tooltip = `${displayDate}: ${run.status.toUpperCase()}${run.latency_ms ? ` (${run.latency_ms}ms)` : ""}${run.error_summary ? ` - ${run.error_summary}` : ""}`;
      ticks.push(`<div class="sla-tick ${isPass ? "pass" : "fail"}" title="${tooltip}"></div>`);
    } else {
      ticks.push(`<div class="sla-tick empty" title="${displayDate}: No scheduled run"></div>`);
    }
  }

  const uptimePct = testedDays > 0 ? ((passedDays / testedDays) * 100).toFixed(1) : "0.0";
  const pctClass = Number(uptimePct) >= 80 ? "high" : Number(uptimePct) >= 50 ? "medium" : "low";

  return `
    <div class="sla-bar-container ${isLarge ? "sla-bar-lg" : ""}">
      <div class="sla-bar">
        ${ticks.join("")}
      </div>
      <div class="sla-bar-legend">
        <span>${daysCount}d ago</span>
        <span class="sla-uptime-pill ${pctClass}">${uptimePct}% Uptime</span>
        <span>Today</span>
      </div>
    </div>
  `;
}

function renderSummaryCards(summary) {
  const container = document.getElementById("summary-section");
  if (!container) return;

  const totalRuns = summary.total_historical_runs || 1;
  const trend = summary.trend_summary || { stable: 0, regressed: 0, recovered: 0 };

  container.innerHTML = `
    <div class="card passed">
      <div class="card-label">Working Implementations</div>
      <div class="card-value">${summary.passed} <span style="font-size: 1rem; color: var(--text-muted); font-weight: 500;">/ ${summary.total_packages}</span></div>
      <div class="card-subtext">${summary.pass_rate}% live test pass rate</div>
    </div>
    <div class="card ${trend.regressed > 0 ? "failed" : "passed"}">
      <div class="card-label">Run History & Stability</div>
      <div class="card-value">${totalRuns} <span style="font-size: 1rem; color: var(--text-muted); font-weight: 500;">Runs</span></div>
      <div class="card-subtext">${trend.regressed > 0 ? `<span style="color: #f87171;">▼ ${trend.regressed} regressed</span>` : "All implementations stable"}</div>
    </div>
    <div class="card info">
      <div class="card-label">Lifetime Downloads</div>
      <div class="card-value">${formatCompactNumber(summary.total_downloads_lifetime)}</div>
      <div class="card-subtext">${formatNumber(summary.total_downloads_lifetime)} all-time (pepy.tech)</div>
    </div>
    <div class="card info">
      <div class="card-label">2026 Downloads</div>
      <div class="card-value">${formatCompactNumber(summary.total_downloads_2026)}</div>
      <div class="card-subtext">Current year volume (pypistats.org)</div>
    </div>
    <div class="card info">
      <div class="card-label">Last Month</div>
      <div class="card-value">${formatCompactNumber(summary.total_downloads_last_month)}</div>
      <div class="card-subtext">Active 30-day installations</div>
    </div>
  `;
}

function renderTable(packages) {
  const tbody = document.getElementById("packages-table-body");
  if (!tbody) return;

  const filtered = packages.filter((pkg) => {
    // 1. Pill Filter
    const status = pkg.test_result.status;
    const apiType = (pkg.test_result.api_type || "").toLowerCase();

    if (activeFilter === "passed" && status !== "passed") return false;
    if (activeFilter === "failed" && status === "passed") return false;
    if (activeFilter === "async" && apiType !== "async") return false;
    if (activeFilter === "sync" && apiType !== "sync") return false;

    // 2. Search query
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = pkg.name.toLowerCase().includes(q);
      const matchDesc = (pkg.description || "").toLowerCase().includes(q);
      const matchApi = apiType.includes(q);
      const matchModule = (pkg.default_module || "").toLowerCase().includes(q);
      if (!matchName && !matchDesc && !matchApi && !matchModule) return false;
    }

    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No packages match the selected criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((pkg) => {
      const isPassed = pkg.test_result.status === "passed";
      const statusBadge = isPassed
        ? `<span class="badge badge-passed">PASS</span>`
        : `<span class="badge badge-failed">FAIL</span>`;

      const apiBadge = `<span class="badge-api">${pkg.test_result.api_type || "n/a"}</span>`;
      const latency = pkg.test_result.tests?.translate_en_de?.latency_ms;
      const latencyStr = latency ? `${latency} ms` : "-";

      // Reliability metrics
      const rel = pkg.reliability || { percentage: 0, total_runs: 0, trend: "stable" };
      const relClass = rel.percentage >= 80 ? "high" : rel.percentage >= 50 ? "medium" : "low";

      const trendBadge =
        rel.trend === "regressed"
          ? `<span class="trend-badge regressed">▼ Regressed</span>`
          : rel.trend === "recovered"
          ? `<span class="trend-badge recovered">▲ Recovered</span>`
          : `<span class="trend-badge stable">Stable</span>`;

      const slaBarHtml = createSlaTickBar(pkg.history || [], 30, false);

      return `
        <tr>
          <td>${statusBadge}</td>
          <td>
            <div class="pkg-title">
              <a href="${pkg.pypi_url}" target="_blank" rel="noopener" class="pkg-name-link">${pkg.name}</a>
            </div>
            <div class="pkg-desc">${pkg.description}</div>
          </td>
          <td>
            <div class="rel-cell">
              <div class="rel-header">
                <span class="badge-rel ${relClass}">${rel.percentage}%</span>
                ${trendBadge}
              </div>
              ${slaBarHtml}
            </div>
          </td>
          <td>
            <div class="stat-mono">v${pkg.latest_release}</div>
            <div class="stat-secondary">${formatDate(pkg.latest_release_date)}</div>
          </td>
          <td>${apiBadge}</td>
          <td>
            <div class="stat-mono">${formatCompactNumber(pkg.downloads.lifetime)}</div>
            <div class="stat-secondary">${formatNumber(pkg.downloads.lifetime)}</div>
          </td>
          <td>
            <div class="stat-mono">${formatCompactNumber(pkg.downloads.year_2026)}</div>
            <div class="stat-secondary">${formatNumber(pkg.downloads.year_2026)}</div>
          </td>
          <td>
            <div class="stat-mono">${formatCompactNumber(pkg.downloads.last_month)}</div>
            <div class="stat-secondary">${formatNumber(pkg.downloads.last_month)}</div>
          </td>
          <td class="stat-mono">${latencyStr}</td>
          <td>
            <button class="btn-details" data-pkg="${pkg.id}">Inspect</button>
          </td>
        </tr>
      `;
    })
    .join("");

  // Attach modal trigger listeners
  tbody.querySelectorAll(".btn-details").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pkgId = btn.getAttribute("data-pkg");
      const target = packages.find((p) => p.id === pkgId);
      if (target) openModal(target);
    });
  });
}

function renderHistoryView(data) {
  const runs = data.runs_history || [];
  const packages = data.packages || [];

  // Update badge
  const runsBadge = document.getElementById("runs-count-badge");
  if (runsBadge) {
    runsBadge.textContent = `${runs.length} runs`;
  }

  const indicator = document.getElementById("history-runs-indicator");
  if (indicator) {
    indicator.textContent = `${runs.length} runs recorded in SQLite`;
  }

  // 1. Render History Runs Banner
  const banner = document.getElementById("history-runs-banner");
  if (banner) {
    banner.innerHTML = runs
      .map((r, idx) => {
        const isLatest = idx === runs.length - 1;
        const passRate = r.pass_rate ?? (r.total_packages ? round((r.passed_count / r.total_packages) * 100, 1) : 0);
        return `
          <div class="run-banner-card ${isLatest ? "latest" : ""}">
            <div class="run-banner-title">
              <span>Run #${idx + 1} ${isLatest ? "(Latest)" : ""}</span>
              <span class="badge-rel ${passRate >= 60 ? "high" : "medium"}">${passRate}% Pass</span>
            </div>
            <div class="run-banner-date">${formatDateTime(r.timestamp)}</div>
            <div class="run-banner-stats">
              <span class="run-stat-chip pass">✔ ${r.passed_count} Working</span>
              <span class="run-stat-chip fail">✖ ${r.failed_count} Broken</span>
              <span style="font-size: 0.75rem; color: var(--text-dim); margin-left: auto;">${r.total_packages} Tested</span>
            </div>
          </div>
        `;
      })
      .join("");
  }

  // 2. Render 30-Day SLA Overview Grid
  const slaContainer = document.getElementById("sla-overview-container");
  if (slaContainer) {
    slaContainer.innerHTML = packages
      .map((pkg) => {
        const rel = pkg.reliability || { percentage: 0, trend: "stable" };
        const relClass = rel.percentage >= 80 ? "high" : rel.percentage >= 50 ? "medium" : "low";
        const trendBadge =
          rel.trend === "regressed"
            ? `<span class="trend-badge regressed">▼ Regressed</span>`
            : rel.trend === "recovered"
            ? `<span class="trend-badge recovered">▲ Recovered</span>`
            : `<span class="trend-badge stable">Stable</span>`;

        return `
          <div class="sla-overview-card">
            <div class="sla-overview-header">
              <div class="sla-overview-name">${pkg.name}</div>
              <div style="display: flex; gap: 0.35rem; align-items: center;">
                <span class="badge-rel ${relClass}">${rel.percentage}%</span>
                ${trendBadge}
              </div>
            </div>
            ${createSlaTickBar(pkg.history || [], 30, false)}
          </div>
        `;
      })
      .join("");
  }

  // 3. Render History Matrix Table
  const tableHead = document.getElementById("history-table-head");
  const tableBody = document.getElementById("history-table-body");

  if (tableHead && tableBody) {
    // Header row
    const runHeaders = runs
      .map((r, idx) => {
        const isLatest = idx === runs.length - 1;
        return `
          <th>
            <div>Run #${idx + 1} ${isLatest ? "★" : ""}</div>
            <div style="font-size: 0.7rem; font-weight: normal; color: var(--text-muted);">${formatDateTime(r.timestamp)}</div>
          </th>
        `;
      })
      .join("");

    tableHead.innerHTML = `
      <tr>
        <th>PyPI Package</th>
        <th>Reliability</th>
        ${runHeaders}
        <th>Inspect</th>
      </tr>
    `;

    // Body rows
    tableBody.innerHTML = packages
      .map((pkg) => {
        const rel = pkg.reliability || { percentage: 0, total_runs: 0, trend: "stable" };
        const relClass = rel.percentage >= 80 ? "high" : rel.percentage >= 50 ? "medium" : "low";

        const trendBadge =
          rel.trend === "regressed"
            ? `<span class="trend-badge regressed">▼ Regressed</span>`
            : rel.trend === "recovered"
            ? `<span class="trend-badge recovered">▲ Recovered</span>`
            : `<span class="trend-badge stable">Stable</span>`;

        // Cells for each run
        const runCells = runs
          .map((run, runIdx) => {
            const histItem =
              (pkg.history || []).find((h) => h.run_id === run.run_id) ||
              (pkg.history && pkg.history[runIdx]);

            if (!histItem) {
              return `<td><span style="color: var(--text-dim);">-</span></td>`;
            }

            const isPass = histItem.status === "passed";
            const latencyStr = histItem.latency_ms ? `${histItem.latency_ms} ms` : "-";
            const errSnippet = histItem.error_summary
              ? histItem.error_summary.replace(/</g, "&lt;").slice(0, 45)
              : "";

            // Check if regressed or recovered compared to previous run
            let transitionBadge = "";
            if (runIdx > 0 && pkg.history && pkg.history[runIdx - 1]) {
              const prevPass = pkg.history[runIdx - 1].status === "passed";
              if (prevPass && !isPass) {
                transitionBadge = `<div style="font-size: 0.65rem; color: #f87171; font-weight: 700;">REGRESSED ✖</div>`;
              } else if (!prevPass && isPass) {
                transitionBadge = `<div style="font-size: 0.65rem; color: #34d399; font-weight: 700;">RECOVERED ✔</div>`;
              }
            }

            return `
              <td>
                <div class="history-cell ${isPass ? "pass" : "fail"}">
                  <div class="history-cell-status">
                    <span>${isPass ? "PASS" : "FAIL"}</span>
                    <span class="history-cell-latency">${latencyStr}</span>
                  </div>
                  ${transitionBadge}
                  ${
                    errSnippet
                      ? `<div class="history-cell-error" title="${histItem.error_summary}">${errSnippet}...</div>`
                      : ""
                  }
                </div>
              </td>
            `;
          })
          .join("");

        return `
          <tr>
            <td>
              <div class="pkg-title">
                <a href="${pkg.pypi_url}" target="_blank" rel="noopener" class="pkg-name-link">${pkg.name}</a>
              </div>
              <div class="pkg-desc">${pkg.description}</div>
            </td>
            <td>
              <div class="rel-cell">
                <div class="rel-header">
                  <span class="badge-rel ${relClass}">${rel.percentage}%</span>
                  ${trendBadge}
                </div>
                <div style="font-size: 0.725rem; color: var(--text-dim);">${rel.passed_runs || 0}/${rel.total_runs || 0} passed</div>
              </div>
            </td>
            ${runCells}
            <td>
              <button class="btn-details" data-pkg="${pkg.id}">Inspect</button>
            </td>
          </tr>
        `;
      })
      .join("");

    // Attach inspect buttons
    tableBody.querySelectorAll(".btn-details").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pkgId = btn.getAttribute("data-pkg");
        const target = packages.find((p) => p.id === pkgId);
        if (target) openModal(target);
      });
    });
  }

  // 4. Render Reliability Ranking Grid
  const rankingContainer = document.getElementById("reliability-ranking-container");
  if (rankingContainer) {
    const sortedByRel = [...packages].sort((a, b) => {
      const relA = a.reliability?.percentage || 0;
      const relB = b.reliability?.percentage || 0;
      if (relB !== relA) return relB - relA;
      return (b.downloads?.lifetime || 0) - (a.downloads?.lifetime || 0);
    });

    rankingContainer.innerHTML = sortedByRel
      .map((pkg) => {
        const rel = pkg.reliability || { percentage: 0, total_runs: 0, passed_runs: 0, trend: "stable" };
        const relClass = rel.percentage >= 80 ? "high" : rel.percentage >= 50 ? "medium" : "low";

        return `
          <div class="ranking-card">
            <div class="ranking-card-top">
              <span class="ranking-pkg-name">${pkg.name}</span>
              <span class="badge-rel ${relClass}">${rel.percentage}%</span>
            </div>
            <div class="ranking-bar-track">
              <div class="ranking-bar-fill ${relClass}" style="width: ${rel.percentage}%;"></div>
            </div>
            <div class="ranking-meta">
              <span>${rel.passed_runs} of ${rel.total_runs} runs passed</span>
              <span>Avg: ${rel.avg_latency_ms ? `${rel.avg_latency_ms} ms` : "n/a"}</span>
            </div>
          </div>
        `;
      })
      .join("");
  }
}

function openModal(pkg) {
  const modal = document.getElementById("modal-container");
  const modalBody = document.getElementById("modal-body");
  if (!modal || !modalBody) return;

  const isPassed = pkg.test_result.status === "passed";
  const tr = pkg.test_result;

  const translateTest = tr.tests?.translate_en_de || {};
  const detectTest = tr.tests?.detect_language || {};
  const importTest = tr.tests?.import || {};
  const pkgTest = tr.tests?.packaging || {};
  const rel = pkg.reliability || { percentage: 0, total_runs: 0, passed_runs: 0, trend: "stable" };

  // Statuspage SLA bar for this package
  const slaBarModal = createSlaTickBar(pkg.history || [], 30, true);

  // Generate historical timeline entries
  const historyItems = (pkg.history || [])
    .map((h, idx) => {
      const isRunPassed = h.status === "passed";
      const trTest = h.tests?.translate_en_de || {};
      const detTest = h.tests?.detect_language || {};

      return `
      <div class="history-run-item ${isRunPassed ? "passed" : "failed"}">
        <div class="history-run-header">
          <div class="history-run-date">
            Run #${idx + 1}: ${formatDateTime(h.timestamp)}
          </div>
          <span class="badge ${isRunPassed ? "badge-passed" : "badge-failed"}">${h.status.toUpperCase()}</span>
        </div>
        <div class="history-run-details">
          <span>Latency: <strong>${h.latency_ms ? `${h.latency_ms} ms` : "-"}</strong></span>
          <span>Version: <strong>${h.version ? `v${h.version}` : "n/a"}</strong></span>
          ${trTest.result ? `<span>Translation: <em>"${trTest.result}"</em></span>` : ""}
          ${detTest.result ? `<span>Detected: <em>${detTest.result}</em></span>` : ""}
        </div>
        ${
          h.error_summary
            ? `<div class="history-run-error-box">${h.error_summary}</div>`
            : ""
        }
      </div>
    `;
    })
    .join("");

  modalBody.innerHTML = `
    <div class="modal-header">
      <h3>
        ${pkg.name}
        <span class="badge ${isPassed ? "badge-passed" : "badge-failed"}">${tr.status}</span>
        <span class="badge-rel ${rel.percentage >= 80 ? "high" : rel.percentage >= 50 ? "medium" : "low"}" style="margin-left: 0.5rem;">
          ${rel.percentage}% Reliability
        </span>
      </h3>
      <p style="color: var(--text-muted); margin-top: 0.25rem;">${pkg.description}</p>
    </div>

    <!-- 30-Day SLA Uptime Bar in Modal -->
    <div class="modal-section">
      <h4>30-Day Rolling Uptime Bar</h4>
      <div style="margin-top: 0.5rem; max-width: 100%;">
        ${slaBarModal}
      </div>
    </div>

    <!-- Historical Test Runs Timeline -->
    <div class="modal-section">
      <h4>Historical Test Runs (${pkg.history ? pkg.history.length : 0} Tracked Executions)</h4>
      <div class="history-timeline">
        ${historyItems || '<div style="color: var(--text-dim);">No previous run records available.</div>'}
      </div>
    </div>

    <div class="modal-section">
      <h4>Telemetry & PyPI Metadata</h4>
      <div class="test-grid">
        <div class="test-item">
          <div class="test-item-title"><span>Latest Release</span><span>PyPI</span></div>
          <div class="test-item-content">v${pkg.latest_release} (${formatDate(pkg.latest_release_date)})</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>Import Namespace</span><span>Python</span></div>
          <div class="test-item-content"><code>import ${tr.module_name || pkg.default_module}</code></div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>API Paradigm</span><span>Async / Sync</span></div>
          <div class="test-item-content">${tr.api_type}</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>Total Lifetime Downloads</span><span>pepy.tech</span></div>
          <div class="test-item-content">${formatNumber(pkg.downloads.lifetime)}</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>2026 Downloads</span><span>pypistats.org</span></div>
          <div class="test-item-content">${formatNumber(pkg.downloads.year_2026)} (w/ mirrors: ${formatNumber(pkg.downloads.year_2026_with_mirrors)})</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>Last Month Downloads</span><span>pypistats.org</span></div>
          <div class="test-item-content">${formatNumber(pkg.downloads.last_month)} (last week: ${formatNumber(pkg.downloads.last_week)})</div>
        </div>
      </div>
    </div>

    <div class="modal-section">
      <h4>Latest Harness Test Run Breakdown</h4>
      <div class="test-grid">
        <div class="test-item">
          <div class="test-item-title"><span>Packaging / Install</span><span class="badge ${pkgTest.status === "passed" ? "badge-passed" : "badge-failed"}">${pkgTest.status}</span></div>
          <div class="test-item-content">${pkgTest.details || "-"}</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>Import Resolution</span><span class="badge ${importTest.status === "passed" ? "badge-passed" : "badge-failed"}">${importTest.status}</span></div>
          <div class="test-item-content">${importTest.details || "-"}</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>EN -> DE Translation</span><span class="badge ${translateTest.status === "passed" ? "badge-passed" : "badge-failed"}">${translateTest.status}</span></div>
          <div class="test-item-content">${translateTest.result ? `"${translateTest.result}" (${translateTest.latency_ms} ms)` : "-"}</div>
        </div>
        <div class="test-item">
          <div class="test-item-title"><span>Language Detection</span><span class="badge ${detectTest.status === "passed" ? "badge-passed" : "badge-failed"}">${detectTest.status}</span></div>
          <div class="test-item-content">${detectTest.result ? `Detected: ${detectTest.result} (${detectTest.latency_ms} ms)` : detectTest.details || "-"}</div>
        </div>
      </div>
    </div>

    ${
      tr.error_summary
        ? `
      <div class="modal-section">
        <h4>Latest Run Diagnosis & Error Output</h4>
        <div class="code-block">${tr.error_summary}</div>
      </div>
    `
        : ""
    }

    <div style="display: flex; gap: 0.75rem; margin-top: 1.5rem; flex-wrap: wrap;">
      <a href="${pkg.pypi_url}" target="_blank" rel="noopener" class="btn btn-github">View on PyPI</a>
      <a href="${pkg.pepy_url}" target="_blank" rel="noopener" class="btn btn-github">pepy.tech Stats</a>
      <a href="${pkg.pypistats_url}" target="_blank" rel="noopener" class="btn btn-github">pypistats.org Stats</a>
    </div>
  `;

  modal.classList.remove("hidden");
}

function switchView(viewName) {
  currentView = viewName;
  const matrixContainer = document.getElementById("view-matrix-container");
  const historyContainer = document.getElementById("view-history-container");
  const tabs = document.querySelectorAll(".view-tab");

  tabs.forEach((tab) => {
    if (tab.getAttribute("data-view") === viewName) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });

  if (viewName === "matrix") {
    matrixContainer?.classList.remove("hidden");
    historyContainer?.classList.add("hidden");
  } else {
    matrixContainer?.classList.add("hidden");
    historyContainer?.classList.remove("hidden");
    if (currentData) renderHistoryView(currentData);
  }
}

function initTheme() {
  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initialTheme = savedTheme || (prefersDark ? "dark" : "light");

  applyTheme(initialTheme);

  const toggleBtn = document.getElementById("theme-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      localStorage.setItem("theme", nextTheme);
    });
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.getElementById("theme-icon");
  const text = document.getElementById("theme-text");
  if (icon && text) {
    if (theme === "dark") {
      icon.textContent = "🌙";
      text.textContent = "Dark";
    } else {
      icon.textContent = "☀️";
      text.textContent = "Light";
    }
  }
}

function initEventListeners() {
  initTheme();

  // Modal close
  const closeBtn = document.getElementById("modal-close");
  const modal = document.getElementById("modal-container");
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.add("hidden");
    });
  }

  // Keyboard escape for modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
      modal.classList.add("hidden");
    }
  });

  // View Switcher Tabs
  const viewTabs = document.getElementById("view-tabs");
  if (viewTabs) {
    viewTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".view-tab");
      if (!tab) return;
      const targetView = tab.getAttribute("data-view");
      if (targetView) switchView(targetView);
    });
  }

  // Filter Pills
  const pillsContainer = document.getElementById("filter-pills");
  if (pillsContainer) {
    pillsContainer.addEventListener("click", (e) => {
      const btn = e.target.closest(".pill");
      if (!btn) return;
      pillsContainer.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.getAttribute("data-filter") || "all";
      if (currentData) renderTable(currentData.packages);
    });
  }

  // Search input
  const searchInput = document.getElementById("package-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.trim();
      if (currentData) renderTable(currentData.packages);
    });
  }
}

async function loadData() {
  const tsIndicator = document.getElementById("timestamp-indicator");
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status} fetching ${DATA_URL}`);
    const data = await response.json();
    currentData = data;

    const allPill = document.getElementById("pill-all");
    if (allPill && data.packages) {
      allPill.textContent = `All (${data.packages.length})`;
    }

    renderSummaryCards(data.summary);
    renderTable(data.packages);
    renderHistoryView(data);

    if (tsIndicator) {
      const date = new Date(data.generated_at);
      tsIndicator.textContent = `Updated: ${date.toLocaleString()}`;
    }
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
    if (tsIndicator) tsIndicator.textContent = "Failed to load results.json";
    const tbody = document.getElementById("packages-table-body");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--status-failed); padding: 2rem;">Error loading data: ${err.message}</td></tr>`;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadData();
});
