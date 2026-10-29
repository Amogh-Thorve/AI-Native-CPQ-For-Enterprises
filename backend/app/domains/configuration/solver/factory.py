"""Chooses the solver from settings.CONFIG_SOLVER. The default is the rules validator; ortools loads only for cpsat."""
from backend.app.domains.configuration.solver.protocol import ConfigurationSolver
from backend.app.domains.configuration.solver.rules_validator import RulesValidator

SOLVERS = ("rules", "cpsat")


def get_solver(name: str) -> ConfigurationSolver:
    if name == "rules":
        return RulesValidator()
    if name == "cpsat":
        from backend.app.domains.configuration.solver.cpsat_solver import CpSatSolver
        return CpSatSolver()
    raise ValueError(f"Unknown CONFIG_SOLVER '{name}'. Use one of {SOLVERS}.")
