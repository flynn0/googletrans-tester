#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== 0. Running unit test suite ==="
if command -v pytest >/dev/null 2>&1; then
  pytest "$DIR/tests" -v
fi

echo "=== 1. Fetching telemetry stats ==="
python3 "$DIR/runner/fetch_stats.py"

echo "=== 2. Running package test matrix ==="
python3 "$DIR/runner/run_matrix.py"

echo "=== 3. Synchronizing dashboard data ==="
python3 "$DIR/scripts/sync_dashboard_data.py"

echo "=== 4. Building dashboard ==="
cd "$DIR/dashboard"
npm install
npm run build

echo "=== Done! Run 'cd dashboard && npm run preview' to view the dashboard locally. ==="
