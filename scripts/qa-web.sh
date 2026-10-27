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
# Source and dependencies use separate named volumes; configs are copied into the
# ephemeral container layer. The host source remains read-only.
tar -C /workspace/web --exclude=node_modules --exclude=.next '--exclude=*.tsbuildinfo' '--exclude=.env*' -cf /tmp/ketrika-web-source.tar .
tar -C /app -xf /tmp/ketrika-web-source.tar
cd /app
case "${1:-check}" in
  check)
    node scripts/qa-check.mjs
    ;;
  dev) exec pnpm dev ;;
  serve)
    test -s .next/BUILD_ID && test -s .next/standalone/server.js || {
      echo "Qualification requires the completed standalone frontend build" >&2
      exit 1
    }
    mkdir -p .next/standalone/.next
    cp -R .next/static .next/standalone/.next/
    if [ -d public ]; then cp -R public .next/standalone/; fi
    export HOSTNAME=0.0.0.0 PORT=3000 NODE_ENV=production
    exec node .next/standalone/server.js
    ;;
  negative-build) node scripts/qa-negative-build.mjs ;;
  *) echo "Unknown qualification web command" >&2; exit 1 ;;
esac
