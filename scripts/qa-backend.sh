#!/usr/bin/env sh
# Runs inside the dedicated backend container, never on the host.
set -eu
if [ "${KETRIKA_QA_BACKEND_SNAPSHOT:-}" != "1" ]; then
  cp "$0" /tmp/ketrika-qa-backend-runner.sh
  export KETRIKA_QA_BACKEND_SNAPSHOT=1
  exec sh /tmp/ketrika-qa-backend-runner.sh "$@"
fi
if [ "${KETRIKA_QUALIFICATION:-}" != "1" ]; then
  echo "Qualification backend command requires the isolated profile" >&2
  exit 1
fi
# Snapshot only versioned tooling inputs, never ambient .env or host dependencies.
# All Python execution then uses the named volume, not Windows bind filesystem I/O.
tar -C /workspace/backend '--exclude=__pycache__' -cf /tmp/ketrika-backend-source.tar src tests alembic alembic.ini pyproject.toml README.md uv.lock
tar -C /app -xf /tmp/ketrika-backend-source.tar
python -m ketrika.core.qualification environment
cd /app
# Load only declared test plugins, not ambient plugins from ML transitive packages.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
run_pytest() {
  pytest -p pytest_asyncio.plugin -p pytest_cov.plugin -p _hypothesis_pytestplugin -p pytest_httpserver.pytest_plugin "$@"
}
case "${1:-check}" in
  prepare)
    alembic upgrade head
    python -m ketrika.normalize.loader seed
    ;;
  serve) exec uvicorn ketrika.api.main:app --host 0.0.0.0 --port 8000 ;;
  check)
    ruff check src tests
    ruff format --check src tests
    mypy src tests
    python -m ketrika.core.execution_plan --root /workspace
    export KETRIKA_QA_INVENTORY=/app/.venv/qa-inventory.json
    export KETRIKA_QA_INVENTORY_OWNER_PID=$$
    run_pytest -m 'not network' --maxfail=10 --cov=ketrika.core --cov=ketrika.extraction --cov=ketrika.normalize --cov-report=term-missing --cov-report=json:/app/.venv/qa-coverage.json --junitxml=/app/.venv/qa-tests.xml
    python -m ketrika.core.qualification_reports check-junit /app/.venv/qa-tests.xml /app/.venv/qa-inventory.json --root /workspace --commit "$KETRIKA_SOURCE_COMMIT" --minimum-tests 340 --minimum-integrations 32
    python -m ketrika.core.qualification coverage /app/.venv/qa-coverage.json
    ;;
  test)
    shift
    run_pytest -m 'not network' "$@"
    ;;
  governance) python -m ketrika.core.execution_plan --root /workspace ;;
  qa)
    [ "$#" -eq 2 ] || { echo "QA requires exactly one task ID" >&2; exit 1; }
    python -m ketrika.core.qa_manifest "$2"
    ;;
  *) echo "Unknown qualification backend command" >&2; exit 1 ;;
esac
