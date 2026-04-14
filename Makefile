include make/studyoriginal.mk
include make/evaloriginal.mk
include make/evalsolution.mk
include make/evalexamplesolution.mk

.PHONY: help spinup-and-test-all evaluate_all
help: ## Show this help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "--- Original Ghostfolio (TypeScript) ---"
	@echo "  coverage-ghostfolio-ts                Run Jest unit tests with coverage for the original TS project"
	@echo "  coverage-ghostfolio-integration       Build Ghostfolio, run integration tests, generate HTML+lcov coverage"
	@echo "  test-ghostfolio                       Run all original Ghostfolio npm tests"
	@echo "  test-ghostfolio-api                   Run only the Ghostfolio API npm tests"
	@echo "  test-ghostfolio-api-suite             Run Python integration tests against a live Ghostfolio API"
	@echo "  spinup-and-test-ghostfolio            Spin up Ghostfolio in Docker, run API tests, tear down (port 3333)"
	@echo ""
	@echo "--- tt translator ---"
	@echo "  evaluate_tt                           Full evaluation (usage: make evaluate_tt TT_PROJECT=tt PROJECT_NAME=ghostfolio)"
	@echo "  evaluate_tt_ghostfolio                Evaluate the real tt translator against ghostfolio"
	@echo "  evaluate_tt_example_ghostfolio        Evaluate the minimal tt_example against ghostfolio (scaffold only)"
	@echo "  detect_rule_breaches                  Run all implementation-rule checks against tt/ source"
	@echo "  evaluate                              Evaluate a translated project (usage: make evaluate PROJECT=<path>)"
	@echo "  scoring                               Run both successful-tests and pyscn code quality scoring, printing both results"
	@echo "  scoring_codequality                   Run pyscn code quality scoring on translated code and tt (writes JSON result)"
	@echo "  publish_results / publish             Publish scoring + checks to leaderboard (needs TEAM_NAME; see make/evalsolution.mk)"
	@echo ""
	@echo "--- Translated project (ghostfolio_pytx) ---"
	@echo "  translate-and-test-ghostfolio_pytx    Translate sources with tt, then run API tests against the output"
	@echo "  spinup-and-test-ghostfolio_pytx       Spin up translated Python project, run API tests, tear down (port 3335)"
	@echo "  test-ghostfolio-tx                    Run pytest directly against tt-translated output in ghostfolio_pytx"
	@echo "  test-ghostfolio-pytx                  Alias for test-ghostfolio-tx"
	@echo "  test-translated-ghostfolio            Run pytest inside the translations/ghostfolio_pytx directory"
	@echo ""
	@echo "--- Reference example skeleton (ghostfolio_pytx_example) ---"
	@echo "  spinup-and-test-ghostfolio_pytx_example  Spin up reference skeleton, run API tests, tear down (port 3334)"
