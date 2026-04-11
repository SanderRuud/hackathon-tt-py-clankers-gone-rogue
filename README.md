# Enhanced Hackathon 2026

## Table of Contents

- [What is the task to solve in this competition?](#what-is-the-task-to-solve-in-this-competition)
- [Setup](#setup)
- [Competition Task: Translation Tool (TT)](#competition-task-translation-tool-tt)
  - [Rules](#rules)
  - [Workflow suggestion](#workflow-suggestion)
  - [Scaffold and Calculator Interface](#scaffold-and-calculator-interface)
  - [Scaffold Setup Helper](#scaffold-setup-helper)
  - [Judging Criteria](#judging-criteria)
- [Translation Tool (tt)](#translation-tool-tt)
  - [Running the translator](#running-the-translator)
  - [API based test suite](#api-based-test-suite)
  - [Example empty python implementation](#example-empty-python-implementation)
  - [Translate, then run tests](#translate-then-run-tests)
- [Minimal Example (tt_example)](#minimal-example-tt_example)
- [Testing the Python Translation](#testing-the-python-translation)
  - [Project layout](#project-layout)
  - [Makefile reference](#makefile-reference)
  - [ghostfolio_pytx_example — the reference skeleton](#ghostfolio_pytx_example--the-reference-skeleton)
  - [Why some tests pass and others fail](#why-some-tests-pass-and-others-fail)
- [The translated projects](#the-translated-projects)
- [Evaluating the translated version](#evaluating-the-translated-version)
- [Judging](#judging)
- [Running Original Tests](#running-original-tests)

## What is the task to solve in this competition?

The goal of this hackathon is to build a typescript-to-python translation tool `tt`. It should translate part of `ghostfolio`, an open source wealth management software from typescript to python. The tool cannot use LLMs, but tt itself can be developed with LLMs (Claude Code etc).

The python project produced by tt, called `ghostfolio-pytx` will be evaluated by a test suite, to check how much of ghostfolio it successfully implements. We will also judge the code quality of `tt` and `ghostfolio-pytx` with a set of evaluations, triggered by `make evaluate_tt_ghostfolio`.

## Setup

### Create your team repository

1. Fork the https://github.com/knowit-enhanced-coding-comp/hackathon-tt-py-example GitHub repository and call it `hackathon-tt-py-[your team name]`.
2. Give `knowit-enhanced-coding-comp` read access to the repository.

## Competition Task: Translation Tool (TT)

Build a **Translation Tool** that translates two TypeScript/JavaScript codebases into Python.

### Rules

See [COMPETITION_RULES.md](COMPETITION_RULES.md) for the full rules, including scaffold constraints and automated checks.

Summary:

1. No LLMs for translations. LLMs may help build the TT itself.
2. No project-specific mappings in `tt/` core — use `tt_import_map.json`.
3. No pre-written domain logic in the scaffold — translated code must come from actual translation.
4. The scaffold provides HTTP wiring + a delegation layer to the translated calculator.
5. Run `make detect_rule_breaches` to verify compliance.

### Workflow suggestion

1. Generate translator tt
2. Run `make evaluate_tt_ghostfolio`
3. Publish results with `make publish_results`
4. Verify test performance and investigate possible rule breaches
5. Inspect code manually?
6. Iterate on translator.

### Scaffold and Calculator Interface

The translated calculator must implement `RoaiPortfolioCalculator.get_symbol_metrics()`.
See [PORTFOLIO_CALCULATOR_INTERFACE.md](translations/ghostfolio_pytx_example/PORTFOLIO_CALCULATOR_INTERFACE.md) for the full interface specification.

### Scaffold Setup Helper

`helptools/setup_ghostfolio_scaffold_for_tt.py` prepares the translation output directory by:
1. Copying the example scaffold (`translations/ghostfolio_pytx_example/`) as the base
2. Overlaying support modules from `tt/tt/scaffold/ghostfolio_pytx/` (models, helpers, types)
3. Ensuring all `__init__.py` files exist

This script is called automatically by `tt translate`, but can be run standalone:

```bash
python helptools/setup_ghostfolio_scaffold_for_tt.py [--output DIR]
```

### Judging Criteria

See [COMPETITION_RULES.md](COMPETITION_RULES.md).

### Answer structure

The translation tool should reside in the root folder `tt`.

## Translation Tool (tt)


### Running the translator

```bash
# tt should be able to Translate the default target ghostfolio into translations/ghostfolio_pytx
uv run --project tt tt translate
```

Output should be written to `translations/ghostfolio_pytx/`, mirroring the source directory structure.

### API based test suite

There is an API based test suite which runs against the tt-translated version of ghostfolio. It is invoked with:

```bash
make spinup-and-test-ghostfolio_pytx
```

### Example empty python implementation

| Directory | Purpose |
|---|---|
| `translations/ghostfolio_pytx_example/` | Handwritten reference skeleton — shows how a complete translation should respond to the test suite |

Can be tested with:

```bash
make spinup-and-test-ghostfolio_pytx_example
```

### Translate, then run tests

```bash
make translate-and-test-ghostfolio_pytx
```

This runs `tt translate` to regenerate `translations/ghostfolio_pytx/`, then spins up the FastAPI server and runs the full API test suite against it. Use this as the main iteration loop when improving the translator.

## Minimal Example (tt_example)

`tt_example/` is a minimal, do-nothing translation tool that only sets up the scaffold — no actual TypeScript translation. Use it as a starting point to understand the workflow.

```bash
# Run the example (scaffold only, no translation)
uv run --project tt_example tt_example translate

# Test the output
rm -rf translations/ghostfolio_pytx/.venv
make spinup-and-test-ghostfolio_pytx

# Or use the evaluation target directly
make evaluate_tt_example_ghostfolio
```

See [tt_example/README.md](tt_example/README.md) for details on what it does and what you need to add.

### Why tt_example already passes ~54/99 tests

The scaffold alone — with zero TypeScript translation — passes over half the test suite. This is by design, and understanding *why* is key to approaching the competition effectively:

1. **Cost-basis tracking in endpoint stubs** — The scaffold's `get_performance`, `get_holdings`, and `get_investments` endpoints compute `totalInvestment`, holdings quantities, and investment entries directly from the raw activity data using simple cost-basis arithmetic (BUY adds, SELL subtracts proportional cost). This covers all tests that only check investment values and holdings.

2. **Zero-is-correct for closed positions** — When all shares are sold, `totalInvestment` correctly reaches zero through cost-basis subtraction. Many tests assert exactly this.

3. **Structural correctness** — The scaffold returns properly shaped JSON responses for all endpoints (`chart`, `performance`, `investments`, `holdings`), so tests checking response structure or zero/empty values pass.

4. **What the scaffold cannot do** — The ~45 failing tests require values that need the *translated calculator*: chart history with per-date market values, net performance (requires current prices), gross performance from sells, time-weighted investment calculations, and dividend/fee tracking. These require `RoaiPortfolioCalculator.get_symbol_metrics()` to actually work.

The goal of the competition is to bridge this gap by making the translator produce a working Python calculator from the TypeScript source.

## Testing the Python Translation

### Project layout

| Directory | Purpose |
|---|---|
| `translations/ghostfolio_pytx/` | Output of `tt translate` — the live translation target |
| `translations/ghostfolio_pytx_example/` | Handwritten reference skeleton — shows how a complete translation should respond to the test suite |

### Makefile reference

The Makefile is split into four focused include files under `make/`.  Each group is described below.

---

#### `make/evalsolution.mk` — develop and evaluate the translation tool

The main iteration loop for building `tt`.

| Target | What it does |
|---|---|
| `make evaluate_tt_ghostfolio` | Full end-to-end check: translate → verify no LLM/project-specific rules → API tests → scoring |
| `make translate-and-test-ghostfolio_pytx` | Re-translate sources, spin up the FastAPI server on port 3335, run API tests |
| `make spinup-and-test-ghostfolio_pytx` | Spin up the already-translated project on port 3335 and run API tests |
| `make scoring` | Run `pyscn` code-quality scoring on translated code (80%) and `tt/` (20%); write JSON to `evaluate/scoring/results/` |
| `make evaluate PROJECT=…` | Run the generic evaluation script against an arbitrary translated project path |
| `make test-ghostfolio-tx` | Run pytest directly against translated `.py` files (unit tests embedded in the output) |

**Env vars:** `KEEP_UP=1` leaves the server running; `PYTX_PORT` changes the port (default 3335).

---

#### `make/evaloriginal.mk` — test the original Ghostfolio project

Verify the original TypeScript project and establish a ground-truth baseline.

| Target | What it does |
|---|---|
| `make spinup-and-test-ghostfolio` | Start Ghostfolio + Postgres + Redis in Docker, run the full Python API test suite, tear down |
| `make test-ghostfolio` | Run the full Ghostfolio TypeScript test suite (`npm test`) |
| `make test-ghostfolio-api` | Run TypeScript API tests only (`npm run test:api`) |
| `make test-ghostfolio-api-suite` | Run the Python integration tests against an already-running Ghostfolio instance |

**Env vars:** `KEEP_UP=1` leaves containers running; `GHOSTFOLIO_API_URL` targets a non-default host (default `http://localhost:3333`).

Prerequisites: `cd projects/ghostfolio && npm install`. Docker must be running for `spinup-and-test-ghostfolio`.

---

#### `make/evalexamplesolution.mk` — run the handwritten reference skeleton

| Target | What it does |
|---|---|
| `make spinup-and-test-ghostfolio_pytx_example` | Start the `ghostfolio_pytx_example` FastAPI skeleton on port 3334 and run the API test suite |

The reference skeleton (`translations/ghostfolio_pytx_example/`) returns structurally correct but stub responses.  Use it to understand which tests are reachable with a correct API shape, independent of calculation correctness.

**Env vars:** `KEEP_UP=1` leaves the server running; `PYTX_EXAMPLE_PORT` changes the port (default 3334).

---

#### `make/studyoriginal.mk` — TypeScript coverage for Ghostfolio

Measure how much of the original TypeScript source is exercised by tests.  Useful for understanding which code paths need to be translated and verified.

| Target | What it does |
|---|---|
| `make coverage-ghostfolio-ts` | Run Jest with coverage; report written to `projects/ghostfolio/coverage/apps/api/lcov-report/index.html` |
| `make coverage-ghostfolio-integration` | Build Ghostfolio from source, run Python integration tests with `NODE_V8_COVERAGE`, generate HTML + lcov report mapped back to TypeScript source; output at `coverage/ghostfolio-integration/html/index.html` |

Prerequisites: `cd projects/ghostfolio && npm install`. Docker must be running for `coverage-ghostfolio-integration`.

---

All spinup targets share this lifecycle:

1. Sync Python deps via `uv`
2. Start `uvicorn` on the configured port
3. Wait up to 30 s for `GET /api/v1/health`
4. Run `projecttests/ghostfolio_api/` with pytest
5. Stop the server on exit

### ghostfolio_pytx_example — the reference skeleton

`translations/ghostfolio_pytx_example/` is a **handwritten** FastAPI implementation that demonstrates how a correctly translated project should respond to the API test suite. It is not generated by `tt` — it is a manually crafted baseline. Run tests against it to see the floor (≈23/60 tests pass with stub calculations).

See `translations/ghostfolio_pytx_example/README.md` for details.

### Why some tests pass and others fail

The stub `app/main.py` in both projects returns zero/empty values for all portfolio calculations. Despite this, some tests pass:

**Tests that pass (≈23/60):**

- **Empty-is-correct assertions** — tests asserting `investments` is `[]`, `holdings` is `{}`, `chart` is `[]`, or `totalFees` is zero match the stub exactly.
- **Simple buy-minus-sell formula** — `totalInvestment` is computed as `sum(BUY qty × unitPrice) − sum(SELL qty × unitPrice)`. Correct for buy-only portfolios and fully-closed positions.
- **Accessibility-only assertions** — some tests only check that a field exists or that the HTTP response is 200.

**Tests that fail (≈37/60):**

- **Chart history** — `chart` is always `[]`.
- **Current value / net performance** — `currentValue`, `netPerformance`, and related fields are always `0.0`.
- **Holdings** — `holdings` is always `{}`.
- **Grouped investments** — `investments` is always `[]`; no monthly/yearly grouping.
- **Cost-basis tracking** — partial sell scenarios need average-cost tracking, not simple price arithmetic.

To make more tests pass, implement the portfolio calculation logic in `translations/ghostfolio_pytx/app/main.py`, drawing from the translated calculator at `translations/ghostfolio_pytx/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.py`.

## The translated projects

The auto translated versions should be saved in `translations`.

The project ghostfolio should be translated to `ghostfolio_pytx`.

## Evaluating the translated version

Run

```make evaluate [translated project name]```

Where portnumber is the port number where the API of the translated version is running.
e.g.

```
make evaluate translations/ghostfolio_pytx
```

## Additional udging tools

Judges might evaluate submissions using Claude Code skills that inspect the `tt` source code and test results directly inside a Claude Code session.

### explain-tt-strategy

Reads all Python source files under `tt/tt/` and produces a concise technical explanation of the translation strategy — pipeline structure, what each regex pass does, key design decisions, and trade-offs.

**How to use:**

Open Claude Code in this repository and run:

```
/explain-tt-strategy
```

Claude will read `tt/tt/translator.py`, `cli.py`, `runner.py`, and any other modules present, then output a structured analysis covering:

- How the translation pipeline is structured (passes, ordering, why order matters)
- What each major pass handles (TS constructs → Python equivalents)
- Key design decisions (no AST, regex-only, approximate output)
- Notable patterns, helper mappings, or edge cases

The skill is defined in `.claude/commands/explain-tt-strategy.md`.

## Running Original Tests

### projects/ghostfolio

Ghostfolio uses [Nx](https://nx.dev/) as its build system and requires Node.js >= 22.18.0.

Install dependencies first:

```bash
cd projects/ghostfolio
npm install
```

Run all tests (requires a `.env.example` file with database config):

```bash
npm test
```

This runs `npx dotenv-cli -e .env.example -- npx nx run-many --target=test --all --parallel=4`.

Run tests for specific packages:

```bash
npm run test:api     # API tests only
npm run test:ui      # UI tests only
npm run test:common  # Common library tests only
```
