"""
OR-Tools CP-SAT implementation of the configuration solver.

Model
- One boolean per active option (chosen or not) and one per bundle component (selected or not).
- The user's selection is fixed by assumptions: a chosen option is assumed true, every other option is assumed false.
- Each rule, required group, single-select cap, quantity bound and bundle requirement is a gated constraint:
  a fresh literal r enforces the constraint with OnlyEnforceIf(r), and r is added as an assumption.

Conflicts
- Solve under all assumptions. If the model is infeasible, the solver returns an unsat core of assumptions.
- The core is minimised by deletion (drop one assumption, re-solve, keep the drop if still infeasible).
- Gates in the minimal core become Conflicts. They are removed from the assumptions and the search repeats, so
  independent conflicts are all reported, one minimal core at a time.

Deterministic input checks (unknown group or option, group mismatch, negative quantity, inactive bundle product) are
done in Python, exactly as the rules validator does them. They are not solver constraints.
"""
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model

from backend.app.domains.configuration.solver.protocol import (
    BundleModel, Conflict, ComponentSelection, NestedCheck, ProductModel, Invalid, Result, Selection, result_from,
)

SOLVE_TIME_LIMIT_S = 10.0


class _Session:
    """One CP-SAT model plus the bookkeeping to turn unsat cores into conflicts."""

    def __init__(self) -> None:
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solver.parameters.num_workers = 1
        self.solver.parameters.max_time_in_seconds = SOLVE_TIME_LIMIT_S
        self.literal_by_index: Dict[int, cp_model.IntVar] = {}
        self.state: List[int] = []
        self.gate_meaning: Dict[int, Conflict] = {}
        self.gates: List[int] = []

    def literal(self, var) -> int:
        self.literal_by_index[var.Index()] = var
        self.literal_by_index[var.Not().Index()] = var.Not()
        return var.Index()

    def assume_state(self, var, on: bool) -> None:
        lit = var if on else var.Not()
        self.literal_by_index[lit.Index()] = lit
        self.state.append(lit.Index())

    def gate(self, conflict: Conflict, enforce: Callable[[cp_model.IntVar], None]) -> None:
        r = self.model.NewBoolVar(f"gate_{len(self.gates)}")
        enforce(r)
        self.literal_by_index[r.Index()] = r
        self.gates.append(r.Index())
        self.gate_meaning[r.Index()] = conflict

    def _solve(self, indices: Sequence[int]) -> Optional[List[int]]:
        """None when feasible; otherwise the solver's sufficient assumptions."""
        self.model.ClearAssumptions()
        self.model.AddAssumptions([self.literal_by_index[i] for i in indices])
        status = self.solver.Solve(self.model)
        if status == cp_model.INFEASIBLE:
            return list(self.solver.sufficient_assumptions_for_infeasibility())
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"CP-SAT returned {self.solver.status_name(status)}")
        return None

    def _minimise(self, core: List[int]) -> List[int]:
        current = list(core)
        i = 0
        while i < len(current):
            trial = current[:i] + current[i + 1:]
            smaller = self._solve(trial)
            if smaller is not None:
                current = [c for c in smaller if c in trial]
                i = 0
            else:
                i += 1
        return current

    def conflicts(self) -> List[Conflict]:
        found: List[Conflict] = []
        remaining = list(self.gates)
        while True:
            core = self._solve(self.state + remaining)
            if core is None:
                break
            core = self._minimise(core)
            in_core = [i for i in core if i in self.gate_meaning]
            if not in_core:
                raise RuntimeError("Unsatisfiable without any rule assumption; the model itself is inconsistent.")
            for index in in_core:
                found.append(self.gate_meaning[index])
                remaining.remove(index)
        return found


class CpSatSolver:
    name = "cpsat"

    def validate(self, model: ProductModel, selections: Sequence[Selection]) -> Result:
        direct: List[Conflict] = []
        groups = list(model.groups)
        groups_by_id = {g.id: g for g in groups}
        options_by_id = {o.id: o for g in groups for o in g.options if o.is_active}
        picked: Set[int] = set()
        quantity_checks: List[Tuple[int, Conflict]] = []

        for sel in selections:
            if sel.group_id not in groups_by_id:
                direct.append(Conflict("INVALID_OPTION", f"Group ID {sel.group_id} is not defined or active for this product.", group_id=sel.group_id))
                continue
            group = groups_by_id[sel.group_id]
            for opt_id in sel.option_ids:
                if opt_id not in options_by_id:
                    direct.append(Conflict("INVALID_OPTION", f"Option ID {opt_id} is invalid or inactive.", group_id=sel.group_id, option_id=opt_id))
                    continue
                option = options_by_id[opt_id]
                if option.group_id != group.id:
                    direct.append(Conflict("INVALID_OPTION", f"Option ID {opt_id} does not belong to configuration group {group.name}.", group_id=sel.group_id, option_id=opt_id))
                    continue
                picked.add(opt_id)
                qty = 1
                if sel.quantities and str(opt_id) in sel.quantities:
                    qty = sel.quantities[str(opt_id)]
                if qty < 0:
                    direct.append(Conflict("QUANTITY", f"Quantity for option {option.name} cannot be negative.", group_id=group.id, option_id=opt_id))
                    continue
                if option.min_quantity is not None and qty < option.min_quantity:
                    quantity_checks.append((opt_id, Conflict("QUANTITY", f"Quantity {qty} for option {option.name} is below minimum ({option.min_quantity}).", group_id=group.id, option_id=opt_id)))
                elif option.max_quantity is not None and qty > option.max_quantity:
                    quantity_checks.append((opt_id, Conflict("QUANTITY", f"Quantity {qty} for option {option.name} is above maximum ({option.max_quantity}).", group_id=group.id, option_id=opt_id)))

        session = _Session()
        x = {oid: session.model.NewBoolVar(f"opt_{oid}") for oid in options_by_id}
        for oid, var in x.items():
            session.assume_state(var, oid in picked)

        for group in groups:
            members = [x[o.id] for o in group.options if o.is_active]
            if group.required:
                conflict = Conflict("REQUIRED_GROUP", f"Configuration group '{group.name}' requires a selection.", group_id=group.id)
                if members:
                    session.gate(conflict, lambda r, m=members: session.model.Add(sum(m) >= 1).OnlyEnforceIf(r))
                else:
                    session.gate(conflict, lambda r: session.model.AddBoolOr([]).OnlyEnforceIf(r))
            if group.selection_type == "SINGLE_SELECT" and len(members) > 1:
                conflict = Conflict("SINGLE_SELECT", f"Configuration group '{group.name}' only allows a single selection.", group_id=group.id)
                session.gate(conflict, lambda r, m=members: session.model.Add(sum(m) <= 1).OnlyEnforceIf(r))

        for oid, conflict in quantity_checks:
            session.gate(conflict, lambda r: session.model.AddBoolOr([]).OnlyEnforceIf(r))

        for rule in model.rules:
            if rule.source_option_id not in picked:
                continue
            source = x[rule.source_option_id]
            target = x.get(rule.target_option_id)
            if rule.rule_type == "REQUIRES":
                conflict = Conflict("REQUIRES", rule.message, option_id=rule.source_option_id)
                if target is None:
                    session.gate(conflict, lambda r, s=source: session.model.Add(s == 0).OnlyEnforceIf(r))
                else:
                    session.gate(conflict, lambda r, s=source, t=target: session.model.Add(t >= s).OnlyEnforceIf(r))
            elif rule.rule_type == "EXCLUDES" and target is not None:
                conflict = Conflict("EXCLUDES", rule.message, option_id=rule.source_option_id)
                session.gate(conflict, lambda r, s=source, t=target: session.model.Add(s + t <= 1).OnlyEnforceIf(r))

        return result_from(direct + session.conflicts())

    def validate_bundle(self, model: BundleModel, selections: Sequence[ComponentSelection], nested: Optional[NestedCheck] = None) -> Result:
        direct: List[Conflict] = []
        comps = [c for c in model.components if c.is_active]
        by_id = {s.component_id: s for s in selections}
        session = _Session()
        y = {c.id: session.model.NewBoolVar(f"comp_{c.id}") for c in comps}

        for comp in comps:
            sel = by_id.get(comp.id)
            is_selected = bool(sel and sel.selected)
            session.assume_state(y[comp.id], is_selected)
            if comp.required:
                session.gate(
                    Conflict("REQUIRED_COMPONENT", f"Core Component '{comp.product_name}' is required.", option_id=comp.id),
                    lambda r, v=y[comp.id]: session.model.Add(v >= 1).OnlyEnforceIf(r),
                )

        for comp in comps:
            sel = by_id.get(comp.id)
            if not (sel and sel.selected):
                continue
            if not comp.product_active:
                direct.append(Conflict("INACTIVE_PRODUCT", f"Product '{comp.product_name}' is inactive and cannot be selected.", option_id=comp.id))
                continue
            qty = sel.quantity
            if qty < 0:
                direct.append(Conflict("QUANTITY", f"Quantity for '{comp.product_name}' cannot be negative.", option_id=comp.id))
                continue
            if qty < comp.min_quantity:
                session.gate(
                    Conflict("QUANTITY", f"Quantity {qty} for '{comp.product_name}' is below bundle minimum ({comp.min_quantity}).", option_id=comp.id),
                    lambda r: session.model.AddBoolOr([]).OnlyEnforceIf(r),
                )
            elif comp.max_quantity is not None and qty > comp.max_quantity:
                session.gate(
                    Conflict("QUANTITY", f"Quantity {qty} for '{comp.product_name}' is above bundle maximum ({comp.max_quantity}).", option_id=comp.id),
                    lambda r: session.model.AddBoolOr([]).OnlyEnforceIf(r),
                )
            if sel.has_configuration and nested is not None:
                nested_result = nested(sel)
                if isinstance(nested_result, Invalid):
                    for conflict in nested_result.conflicts:
                        direct.append(Conflict("CONFIGURATION", f"Product '{comp.product_name}' configuration error: {conflict.message}", option_id=comp.id))

        return result_from(direct + session.conflicts())
