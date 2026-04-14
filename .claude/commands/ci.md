# CI — translate, test, rule-check

Run the full development feedback loop:
1. Translate TypeScript → Python with `tt translate`
2. Spin up the FastAPI server and run the API test suite
3. Run all rule-breach checks

```bash
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

echo "========================================"
echo " STEP 1/3: tt translate"
echo "========================================"
uv run --project tt tt translate

echo ""
echo "========================================"
echo " STEP 2/3: API tests"
echo "========================================"
bash projecttests/tools/kill_ghostfolio_pytx.sh 2>/dev/null || true
EXIT_CODE=0
bash projecttests/tools/spinup_and_test_ghostfolio_pytx.sh || EXIT_CODE=$?
bash projecttests/tools/kill_ghostfolio_pytx.sh 2>/dev/null || true

echo ""
echo "========================================"
echo " STEP 3/3: Rule-breach checks"
echo "========================================"
bash evaluate/checks/detect_rule_breaches.sh

echo ""
echo "========================================"
if [ "$EXIT_CODE" -eq 0 ]; then
  echo " DONE — all tests passed, no rule breaches"
else
  echo " DONE — tests finished (exit $EXIT_CODE), see output above"
fi
echo "========================================"
exit $EXIT_CODE
```
