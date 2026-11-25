#!/usr/bin/env bash
# Audit seiza repository before publishing/committing to ensure zero secrets or hardcoded home paths.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

echo "==> Checking for accidental secrets or API tokens..."
if grep -rnE \
  '(TINYFISH_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\-_]{25,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' \
  "$REPO_ROOT/config" "$REPO_ROOT/local" "$REPO_ROOT/systemd" "$REPO_ROOT/run.sh" "$REPO_ROOT/README.md" \
  2>/dev/null | grep -v 'SENSITIVE_PATTERNS' | grep -v 're\.compile'; then
  echo "ERROR: Potential secret detected!"
  FAIL=1
fi

echo "==> Checking for hardcoded /home/<user> paths..."
if grep -rnE '/home/[a-zA-Z0-9_-]+' \
  "$REPO_ROOT/config" "$REPO_ROOT/local" "$REPO_ROOT/systemd" "$REPO_ROOT/run.sh" 2>/dev/null; then
  echo "ERROR: Hardcoded /home/<user> path detected! Use \$HOME or __HOME__."
  FAIL=1
fi

echo "==> Checking for leftover temporary branding..."
if grep -rniE 'byebye|kiriobsidian|cyber-glass|cyberglass' \
  "$REPO_ROOT/config" "$REPO_ROOT/local" "$REPO_ROOT/systemd" "$REPO_ROOT/run.sh" "$REPO_ROOT/README.md" \
  2>/dev/null | grep -v 'cyberglass_theme_mode.txt' | grep -v 'CyberGlass'; then
  echo "ERROR: Leftover old brand name detected!"
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
echo "✓ Security & portability audit passed (0 issues)."
