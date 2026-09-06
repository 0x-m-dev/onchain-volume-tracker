#!/usr/bin/env bash
# Install studio git hooks into this repo's .git/hooks:
#   pre-commit — PII scan on staged files + python syntax on staged .py
#   pre-push   — PII scan on all tracked files + README-touched check
set -euo pipefail
cat > .git/hooks/pre-commit <<'EOF'
#!/usr/bin/env bash
set -e
bash tools/check_pii.sh --staged || exit 1
STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM -- '*.py' || true)
if [ -n "$STAGED_PY" ]; then
  echo "$STAGED_PY" | xargs python3 -m py_compile || { echo "pre-commit: python syntax FAILED"; exit 1; }
fi
echo "pre-commit: clean"
EOF
chmod +x .git/hooks/pre-commit
cat > .git/hooks/pre-push <<'EOF'
#!/usr/bin/env bash
set -e
bash tools/check_pii.sh --all || exit 1
bash tools/check_readme_push.sh || exit 1
EOF
chmod +x .git/hooks/pre-push
echo "hooks installed: pre-commit + pre-push"
