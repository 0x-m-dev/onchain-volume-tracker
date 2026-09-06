#!/usr/bin/env bash
# PII / secret gate — fail the push if staged (or all tracked) files contain
# high-precision personal-data or credential patterns.
# Usage: check_pii.sh [--staged|--all]  (default: --staged)
set -euo pipefail
MODE="${1:---staged}"
if [ "$MODE" = "--staged" ]; then
  FILES=$(git diff --cached --name-only --diff-filter=ACM || true)
else
  FILES=$(git ls-files || true)
fi
[ -z "$FILES" ] && { echo "pii-gate: no files to scan"; exit 0; }

PATTERNS=(
  # email addresses
  '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
  # US phone numbers (with separators — avoids matching bare numeric IDs)
  '\b([0-9]{3}[-. ()]{1,3}[0-9]{3}[-. ]?[0-9]{4})\b'
  # SSN-like
  '\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b'
  # private keys
  'BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY'
  # provider tokens
  'sk-[A-Za-z0-9_-]{10,}'
  'gh[pousr]_[A-Za-z0-9_]{10,}'
  'xox[bpas]-[A-Za-z0-9-]{10,}'
  'AKIA[0-9A-Z]{16}'
  'AIza[0-9A-Za-z_-]{10,}'
  # discord bot tokens (classic 24.6.27 + newer variable formats)
  'mfa\.[A-Za-z0-9_.-]{10,}'
  '[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{20,}'
)
HITS=0
for pat in "${PATTERNS[@]}"; do
  # shellcheck disable=SC2086
  MATCHES=$(echo "$FILES" | xargs grep -nE -e "$pat" 2>/dev/null | grep -v 'users\.noreply\.github\.com' || true)
  if [ -n "$MATCHES" ]; then
    echo "pii-gate HIT [$pat]:"
    echo "$MATCHES" | head -n 10
    HITS=1
  fi
done
if [ "$HITS" -ne 0 ]; then
  echo "pii-gate: BLOCKED — remove personal data/secrets before pushing."
  exit 1
fi
echo "pii-gate: clean"
