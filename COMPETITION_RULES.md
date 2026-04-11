# Competition Rules

## Table of Contents

- [Solution submission](#solution-submission)
- [Judging Criteria](#judging-criteria)
- [Core Rules](#core-rules)
- [Judging process](#judging-process)
- [Prizes](#prizes)
- [Wrapper Rules](#wrapper-rules)
  - [Project Layout](#project-layout)
- [What the Translated Code Must Provide](#what-the-translated-code-must-provide)
- [Automated Rule Checks](#automated-rule-checks)

## Solution submission

* At the end of the competition time, the team must reset their main branch to the commit they want to represent their final submission.
* The submission must include:
  * A runnable implementation of `tt`
  * SOLUTION.md file explaining the solution and the coding approach followed to produce it
    * The team must present the solution and the coding approach to the assistant judges
      * If selected for for the final, a short presentation must be done from the stage
    * It can contain visualizations

## Judging Criteria

The TT will be judged on:

1. **Rule compliance** — the translation tool must not break the rules above.
2. **Correctness** — translated Python code passes the API tests of the reference projects, and how many of them.
3. **Python code quality**, ranked by relevance:
   1. Elegance & Readability
   2. Maintainability
   3. Test coverage
   4. Avoid Duplication (DRY)
   5. Some specific code quality metrics, meausre by tooling `make scoring_codequality`
      1. health_score (0-100) - Overall code health score with letter grade (A-F)
      2. complexity_score - Code complexity analysis
      3. dead_code_score - Detection of unused/unreachable code
      4. duplication_score - Code duplication detection
      5. coupling_score - Module coupling/dependencies between components
      6. dependency_score - External dependency quality
      7. architecture_score - Overall architecture quality
4. **Understanding** — judges will evaluate how well competitors understand what their translator actually does. Automated scoring will be balanced with human evaluation of architectural choices, trade-offs, and the team's ability to explain their approach. A high test score from a tool the team cannot explain will be weighted down.
5. **Completion time** - If several teams solve all or the same number of tests, the earliest team to solve them will be assigned an extra advantage in the judging.

We use tools like pyscn for scoring the quality. Scoring: `make evaluate_tt_ghostfolio` runs tests (50%) + code quality via pyscn (50%). Judge review adjusts the final score.

The jury will be able to decide on how to balance these criteria when selecting the winner. The reason we do
not judge 100% deterministically is that we are not yet sure what the nature of solutions will be, and how it is
fair too compare them.

## Core Rules

1. The TT must **not** use LLMs for the actual translations.
2. You **may** use LLMs to help build the TT itself.
3. You may use the API tests to verify correctness of the translated code.
4. TT must not have project-specific logic which it simply copies into the translation. The translated code must be actually translated code, not pregenerated logic.
5. You may use AST libraries in python.
6. Your python code may not call node/js-tools or other external tools to translate the code. The translation should happen in python.
7. The judges will have a one week period to detect cheating or other rule breaches. This might change the final winner.
8. We expect the git commit log to reflect a gradual development of the solution, so do frequent commits.
9. The TT core (`tt/`) must contain **no project-specific mappings** (e.g. no hard-coded `@ghostfolio/…` import paths). Project-specific configuration belongs in `tt_import_map.json` inside the relevant scaffold directory, passed to the translator at call time.

## Judging process

* 15.15-15.30: Instructions
* 15.30-17.30: Initial coding time
  * Github access will be given at 15.30.
  * Work on solution.
  * Prepare SOLUTION.md for short presentation to judges
* 17.30-18.30: Coding and initial judge visits
  * 3 judges or assistant judges will visit each team and get a 3m explanation of solution and approach
  * The team can keep working on the solution in the mean time.
  * At 18.30: all coding stops and solution must be committed to main branch on github before 18.30.
* 18.30-19.00: Judges decide on three finalists
* 19.10-19.20: Finalists present their solution, result and approach
* 19.30: Winner is announced.

## Prizes

* Winning team: 30000 NOK
* 2nd place: 7500 NOK
* 3rd place: 5000 NOK
* Most innovative workflow / agent setup: 2500 NOK
* Best team cooperation: 2500 NOK
* Special jury award: 2500 NOK

Gift cards will be mailed to the winners after one week.

## Wrapper Rules

8. You are not allowed to add anything to `translations/ghostfolio_pytx_example/` before running `tt`.
9. TT must copy the wrapper layer (`app/main.py` and `app/wrapper/`) from `translations/ghostfolio_pytx_example/` into `translations/ghostfolio_pytx/` **without modification**. The wrapper files must remain byte-for-byte identical to the example.
10. TT places its translated code exclusively inside `app/implementation/`. Nothing outside that directory may be generated or modified by tt.
11. The wrapper layer provides HTTP wiring only — not domain calculations. It contains:
    - FastAPI endpoint handlers (controller)
    - Thin service delegation (empty-portfolio guards + calculator calls)
    - In-memory state management (UserState)
    - Auth helpers (`_make_tokens`, `_get_user`)
    - Abstract calculator interface
    - Market price lookup service
    - Shared interface dataclasses
12. The wrapper must **not** contain:
    - Financial arithmetic (cost-basis tracking, performance calculation, chart generation)
    - Position replay or investment grouping logic
    - Rule evaluation for portfolio reports

### Project Layout

The translated project uses a **wrapper / implementation** split:

```
translations/ghostfolio_pytx/app/
├── main.py                                          # immutable wrapper
├── wrapper/                                         # immutable wrapper layer
│   └── portfolio/
│       ├── portfolio_controller.py                  # FastAPI routes
│       ├── portfolio_service.py                     # thin delegation to calculator
│       ├── current_rate_service.py                  # market price lookups
│       ├── calculator/
│       │   └── portfolio_calculator.py              # abstract calculator interface
│       └── interfaces/                              # shared dataclasses
└── implementation/                                  # tt-generated code
    └── portfolio/
        └── calculator/
            └── roai/
                └── portfolio_calculator.py           # ROAI calculator (translated)
```

**Wrapper** (`app/main.py` + `app/wrapper/`): HTTP wiring, auth, thin service delegation, abstract interfaces. Copied verbatim from `translations/ghostfolio_pytx_example/` — tt must NOT modify these files.

**Implementation** (`app/implementation/`): The actual translated financial logic. This is the only code tt generates.

## What the Translated Code Must Provide

The translated calculator must implement the abstract interface defined in:
`app/wrapper/portfolio/calculator/portfolio_calculator.py`

Required methods:
- `get_performance()` → `{chart, firstOrderDate, performance: {...}}`
- `get_investments(group_by)` → `{investments: [{date, investment}]}`
- `get_holdings()` → `{holdings: {symbol: {...}}}`
- `get_details(base_currency)` → `{accounts, holdings, summary, ...}`
- `get_dividends(group_by)` → `{dividends: [{date, investment}]}`
- `evaluate_report()` → `{xRay: {categories, statistics}}`

## Automated Rule Checks

Run `make detect_rule_breaches` to verify compliance. The following checks are enforced:

| Check | What it detects |
|-------|-----------------|
| `detect_llm_usage` | LLM API imports/calls in `tt/` |
| `detect_direct_mappings` | Project-specific import paths in `tt/` core |
| `detect_explicit_implementation` | Domain logic in `tt/` (function size, domain identifiers, string comparisons) |
| `detect_explicit_financial_logic` | Financial arithmetic, variables, and nested loops in scaffold |
| `detect_scaffold_bloat` | Private helpers beyond the allowed set in scaffold `main.py` |
| `detect_code_block_copying` | 10+ line blocks from `tt/` appearing verbatim in translated output |
| `detect_interface_violation` | Calculator interface compliance |
| `detect_wrapper_modification` | Wrapper/main.py files modified from example (must be identical) |
