# Configuration solver findings

Scope: `RulesValidator` (a pure port of `ConfigurationService.validate_configuration` and `validate_bundle`) against
`CpSatSolver` (OR-Tools CP-SAT). Nothing below was fixed on either side. Each divergence has a minimal example and a
test or probe that reproduces it.

## Divergences

### F1. Repeated option id is reported as a single-select violation (rules only). FIXED

- Status: fixed. The solver's reading is the one kept: a repeated option id is one pick.
- Original rules behaviour: `services.py` (`validate_configuration`, step 1) appended the option id to the group's
  chosen list once per occurrence in `option_ids`, then step 2 checked `len(chosen) > 1` for `SINGLE_SELECT`.
- Original solver behaviour: the solver works on the set of picked options, so a repeated id is one pick.
- Minimal example: a `SINGLE_SELECT` group "Plan" with options Basic (id 1), Standard (id 2), and the selection
  `option_ids = [1, 1]`.
  - Before the fix, rules: `SINGLE_SELECT` error "Configuration group 'Plan' only allows a single selection."
  - Before the fix, solver: valid.
- Which side was right: the solver. The user picked one option twice, not two options.
- What changed: the chosen-list append in `services.py` (`validate_configuration`) and in the rules port
  (`solver/rules_validator.py`, `validate_selections`) now skips an id already in that group's chosen list. The first
  occurrence keeps its place, so order is preserved. Nothing else changed: quantity checks still run for every
  occurrence, as they did before and as the solver does, and the other rules are untouched.
- Evidence before the fix: `test_duplicate_option_id_divergence_is_recorded` was a strict xfail. In a probe of 1,440
  random configurations with repeated ids, 496 disagreed. A second probe (different seed, same models) of 1,440 runs
  found 525 disagreements, and every one was a `SINGLE_SELECT` that only the rules validator reported.
- Evidence after the fix: the same test name, `test_duplicate_option_id_divergence_is_recorded`, is now a normal test
  that asserts both implementations accept `[1, 1]` and still report the real two-plan conflict for `[1, 1, 2]`. A
  probe of 1,440 random runs on bench plan models, with one id repeated in every selection (1,387 runs had a repeated
  id), found 0 disagreements between the rules port and the solver.
- The service change has the same shape as the port change, but no test exercises the service path for repeated ids.
  The DB-backed equivalence test needs the dev database, so it was not run for this fix.

## Checked, no divergence

| Area | Evidence |
|---|---|
| Random selections on bench plan models (valid and invalid mixed, unknown option ids) | `test_random_selections_on_bench_models_agree`: 960 runs, no disagreement. A 640-run first sample also agreed. |
| Quantity bounds (min, max, negative) on options | Hand-built cases in `test_solver.py`, plus a probe of 2,880 random runs with quantities in {-1, 0, 1, 2, 4} and bounds 1..3. No disagreement. |
| Inactive options in a valid group, including REQUIRES and EXCLUDES pointing at an inactive target | Probe of 1,440 runs with quantities and every fourth option inactive (the same probe as the quantity row). No disagreement. |
| Unknown group, option from another group, option id not in the model | Hand-built cases in `test_solver.py`. Both agree. |
| Bundles: required components, quantity bounds, inactive products | Hand-built cases, plus a probe of 400 random bundles (2 to 6 components, random required and active flags, quantities -1 to 6). No disagreement. |
| Rules port against the real `ConfigurationService`, on bench products in the dev database | `test_rules_port_and_cpsat_match_service_on_bench_products_in_database`: 40 products, 8 selections each. The port matches the service's validity and error types, and the solver matches the port. |
| `CONFIG_SOLVER=cpsat` through the existing API test | `test_configuration.py` passes with the solver selected. |

## Solver scope

- Modelled: single and multi select groups, required groups, single-select caps, REQUIRES, EXCLUDES, option quantity
  bounds, bundle components (required, quantity bounds).
- Checked in Python before the model (same as the rules validator, not solver constraints): unknown group or option,
  option in the wrong group, negative quantity, selected bundle component whose product is inactive.
- Nested bundle configurations are passed through a callback (`NestedCheck`). Both implementations call the same
  callback, so the solver does not model nested rules. No random probe exercises nested configurations.
- MULTI_SELECT groups have no cap in either implementation. This is not a divergence, but it is a gap: the rules
  validator does not check it, and neither does the solver.
- Conflict sets: each conflict is a minimal unsat core (deletion-based minimisation), and independent conflicts are
  found by removing a core's gates and searching again. In every probe the solver's conflict count matched the rules
  validator's. A conflict that shares a rule with another may be reported once, so the solver is not guaranteed to
  list every rule error.

## Pre-existing issues found while reading (not solver findings, not fixed)

- **P1. AI tool drops quantities.** `domains/ai/tools/definitions.py:138` builds `SelectionItem(group_id, option_ids)`
  without `quantities`, so the assistant path never checks quantity bounds. The solver cannot help here until the tool
  passes quantities.
- **P2. Broken rules route.** `domains/configuration/routes.py:152` calls `service.rule_repo`. The attribute is
  `config_repo`, so `GET /configuration/rules` raises `AttributeError`. Confirmed by reading; not reproduced over HTTP.
- **P3. Draft cloning can raise KeyError.** `services.py` (around lines 463-473) indexes an option map for every active
  rule, but groups from inactive options are never cloned. Reported in the exploration pass; not reproduced here.

## How to reproduce

```bash
python -m pytest backend/app/domains/configuration -q -W ignore
python -m bench.solver_bench --sizes 100 1000 5000 --selections 200
```

F1 (repeated option ids) is covered by `test_duplicate_option_id_divergence_is_recorded` in
`backend/app/domains/configuration/tests/test_solver.py`. It is a normal passing test; the former strict xfail was removed.
