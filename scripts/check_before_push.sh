#!/bin/bash
set -e  # Stoppt bei erstem Fehler

echo "=== Ruff Lint ==="
ruff check . --fix

echo "=== Ruff Format ==="
ruff format .

echo "=== Tests Python ==="
pytest tests/ -x --tb=short -q 2>&1 | tee test_results.txt

echo "=== Fertig ==="
