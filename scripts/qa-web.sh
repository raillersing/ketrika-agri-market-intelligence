#!/usr/bin/env sh
# Runs inside the dedicated web container, never on the host.
set -eu
if [ "${KETRIKA_QA_WEB_SNAPSHOT:-}" != "1" ]; then
  cp "$0" /tmp/ketrika-qa-web-runner.sh
  export KETRIKA_QA_WEB_SNAPSHOT=1
  exec sh /tmp/ketrika-qa-web-runner.sh "$@"
fi
if [ "${KETRIKA_QUALIFICATION:-}" != "1" ]; then
  echo "Qualification web command requires the isolated profile" >&2
  exit 1
fi
# Only the named source volume is written; host source is read-only.
tar -C /workspace/web --exclude=node_modules --exclude=.next '--exclude=*.tsbuildinfo' '--exclude=.env*' -cf /tmp/ketrika-web-source.tar .
tar -C /app -xf /tmp/ketrika-web-source.tar
cd /app
case "${1:-check}" in
  check)
    node scripts/qa-check.mjs
    ;;
  dev) exec pnpm dev ;;
  negative-build) node scripts/qa-negative-build.mjs ;;
  *) echo "Unknown qualification web command" >&2; exit 1 ;;
esac
