#!/usr/bin/env bash
# Push to main with retries. GitHub sometimes rejects a push with a transient server error
# (e.g. "fatal error in commit_refs_rules") or because another run pushed first.
# Rebase onto the latest main and try again before giving up, so one hiccup can't kill a post.
set -u
for i in 1 2 3 4 5; do
  if git pull --rebase --autostash -q origin main && git push -q origin HEAD:main; then
    echo "push ok (attempt $i)"; exit 0
  fi
  echo "push failed (attempt $i), retrying in $((i * 15))s"
  sleep $((i * 15))
done
echo "push failed after 5 attempts"; exit 1
