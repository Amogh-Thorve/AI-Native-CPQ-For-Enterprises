# Configuration solver findings

Scope: `RulesValidator` (a pure port of `ConfigurationService.validate_configuration` and `validate_bundle`) against
`CpSatSolver` (OR-Tools CP-SAT). Nothing below was fixed on either side. Each divergence has a minimal example and a
test or probe that reproduces it.

## Divergences

### F1. Repeated option id is reported as a single-select violation (rules only)

- Rules: `services.py` (`validate_configuration`, step 1 and step 2) appends the option id to the group's chosen list
  once per occurrence in `option_ids`, then checks `len(chosen) > 1` for `SINGLE_SELECT`.
- Solver: the solver works on the set of picked options, so a repeated id is one pick.
- Minimal example: a `SINGLE_SELECT` group "Plan" with options Basic (id 1), Standard (id 2), and the selection
  `option_ids = [1, 1]`.
  - Rules: `SINGLE_SELECT` error "Configuration group 'Plan' only allows a single selection."
  - Solver: valid.
- Which side is right: arguably the solver. The user picked one option twice, not two options. The rules validator
  reports a false error. Not fixed here.
- Evidence: `test_duplicate_option_id_divergence_is_recorded` (strict xfail). In a probe of 1,440 random
  configurations with repeated ids, 496 disagreed. A second probe (different seed, same models) of 1,440 runs found 525 disagreements, and every one
  was a `SINGLE_SELECT` that only the rules validator reported.
- Also true at the API: the service rejects a legitimate single pick sent twice. Not exercised by the API tests.

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

The divergence in F1 is the strict xfail in `backend/app/domains/configuration/tests/test_solver.py`. If the rules
validator is fixed, the xfail will start passing and pytest will fail until the marker is removed. That is intended.
