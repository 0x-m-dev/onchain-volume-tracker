#!/usr/bin/env bash
# README freshness gate — every push must touch the root README.
# As a pre-push hook it reads git's "<lref> <lsha> <rref> <rsha>" lines from
# stdin. Run directly, it compares HEAD against @{upstream}.
# Bypass (with intent): git push --no-verify
set -uo pipefail
git rev-parse --git-dir >/dev/null 2>&1 || { echo "readme check: not a git repo"; exit 1; }

Z40="0000000000000000000000000000000000000000"
RANGES=""
FAIL=0

if [ -t 0 ]; then
  # Direct run: diff upstream..HEAD.
  if git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
    BASE=$(git merge-base '@{upstream}' HEAD 2>/dev/null || true)
    [ -n "$BASE" ] && RANGES="$BASE..HEAD"
  else
    RANGES="HEAD"
  fi
else
  # Pre-push hook mode: exact ranges git is about to push.
  while read -r _ local_sha _ remote_sha; do
    [ -z "${local_sha:-}" ] && continue
    if [ "$remote_sha" = "$Z40" ]; then
      if git ls-tree -r "$local_sha" --name-only | grep -qi '^readme'; then
        echo "readme check: new branch, README present"
      else
        echo "readme check: BLOCKED — new branch without a root README.md"
        FAIL=1
      fi
    elif [ "$local_sha" != "$remote_sha" ]; then
      RANGES="$RANGES $remote_sha..$local_sha"
    fi
  done
fi

FILES=""
for r in $RANGES; do
  if [ "$r" = "HEAD" ]; then
    F="$([ -f README.md ] && echo README.md || true)"
    FILES="$FILES $F"
  else
    FILES="$FILES $(git diff --name-only "$r" || true)"
  fi
done

[ "$FAIL" -ne 0 ] && exit 1
# shellcheck disable=SC2086
FILES_TRIMMED=$(echo $FILES)
[ -z "$FILES_TRIMMED" ] && { echo "readme check: nothing new to push"; exit 0; }
if echo "$FILES_TRIMMED" | tr ' ' '\n' | grep -qi '^readme'; then
  echo "readme check: README updated in this push"
  exit 0
fi
echo "readme check: BLOCKED — this push touches: $(echo "$FILES_TRIMMED" | head -c 220)"
echo "Update the root README.md (what changed + how to run/verify), commit it into the push, and retry."
echo "Bypass: git push --no-verify"
exit 1
