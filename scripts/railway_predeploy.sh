#!/usr/bin/env bash
set -euo pipefail

# Railway build cache cleanup for deterministic deploys
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -type f -name '*.pyc' -delete
rm -rf .pytest_cache

echo '✅ Pre-deploy cleanup completed'
