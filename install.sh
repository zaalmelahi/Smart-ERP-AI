#!/bin/bash
# Smart ERP AI - Installation script
# Fetches Frappe Assistant Core from zaalmelahi fork, then Smart ERP AI, then installs.
#
# Usage:
#   cd /path/to/bench && bash install.sh [site_name]
#   With site: bash install.sh site.local
#   Or: curl -sSL .../install.sh | bash

set -e

FAC_REPO="https://github.com/zaalmelahi/Frappe_Assistant_Core.git"
SMART_ERP_AI_REPO="https://github.com/zaalmelahi/Smart-ERP-AI.git"

# Resolve bench root (supports: bench root, or apps/smart_erp_ai)
if [ -d "apps" ]; then
	BENCH_ROOT="."
elif [ -d "../apps" ]; then
	BENCH_ROOT=".."
elif [ -d "../../apps" ]; then
	BENCH_ROOT="../.."
else
	BENCH_ROOT="."
fi

cd "$BENCH_ROOT" 2>/dev/null || true
if [ ! -d "apps" ]; then
	echo "Error: Run this script from your bench root or apps/smart_erp_ai"
	echo "  cd /path/to/bench && bash install.sh [site_name]"
	echo "  cd /path/to/bench/apps/smart_erp_ai && bash install.sh [site_name]"
	exit 1
fi

echo "=== 1. Fetching Frappe Assistant Core ==="
if [ ! -d "apps/frappe_assistant_core" ]; then
	bench get-app "$FAC_REPO"
else
	echo "  frappe_assistant_core already in bench"
fi

echo ""
echo "=== 2. Fetching Smart ERP AI ==="
if [ ! -d "apps/smart_erp_ai" ]; then
	bench get-app "$SMART_ERP_AI_REPO"
else
	echo "  smart_erp_ai already in bench"
fi

echo ""
SITE_NAME="$1"
if [ -n "$SITE_NAME" ]; then
	echo "=== 3. Installing Smart ERP AI on site: $SITE_NAME ==="
	bench --site "$SITE_NAME" install-app smart_erp_ai
	echo ""
	echo "Done! Smart ERP AI is installed on $SITE_NAME"
else
	echo "=== Next step: Install on your site ==="
	echo "  bench --site YOUR_SITE install-app smart_erp_ai"
fi
