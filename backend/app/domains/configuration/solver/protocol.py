"""
Solver seam for configuration validation.

Implementations take an in-memory snapshot of a product's configuration (ProductModel) and a list of selections, and
return Valid or Invalid with the conflicts. They never touch the database, so the rules validator and the CP-SAT solver
can be compared on identical input and benchmarked without database round trips.
"""
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Protocol, Sequence, Tuple, Union


@dataclass(frozen=True)
class OptionModel:
    id: int
    group_id: int
    name: str
    min_quantity: Optional[int]
    max_quantity: Optional[int]
    is_active: bool


@dataclass(frozen=True)
class GroupModel:
    id: int
    name: str
    required: bool
    selection_type: str  # SINGLE_SELECT or MULTI_SELECT
    options: Tuple[OptionModel, ...]


@dataclass(frozen=True)
class RuleModel:
    rule_type: str  # REQUIRES or EXCLUDES
    source_option_id: int
    target_option_id: int
    message: str


@dataclass(frozen=True)
class ProductModel:
    product_id: int
    groups: Tuple[GroupModel, ...]
    rules: Tuple[RuleModel, ...]


@dataclass(frozen=True)
class Selection:
    group_id: int
    option_ids: Tuple[int, ...]
    # Same shape as the API: keys are option ids as strings. None or missing means quantity 1.
    quantities: Optional[Mapping[str, int]] = None


@dataclass(frozen=True)
class ComponentModel:
    id: int
    product_name: str
    product_active: bool
    required: bool
    is_active: bool
    min_quantity: int
    max_quantity: Optional[int]


@dataclass(frozen=True)
class BundleModel:
    bundle_id: int
    components: Tuple[ComponentModel, ...]


@dataclass(frozen=True)
class ComponentSelection:
    component_id: int
    selected: bool
    quantity: int
    # Nested product configuration. Checked by the callback passed to validate_bundle, not by the solver.
    has_configuration: bool = False


@dataclass(frozen=True)
class Conflict:
    rule_type: str
    message: str
    group_id: Optional[int] = None
    option_id: Optional[int] = None


@dataclass(frozen=True)
class Valid:
    pass


@dataclass(frozen=True)
class Invalid:
    conflicts: Tuple[Conflict, ...]


Result = Union[Valid, Invalid]

# Given a nested selection, returns that product's configuration result. Used for bundle nested configurations.
NestedCheck = Callable[[ComponentSelection], Result]


def result_from(conflicts: Sequence[Conflict]) -> Result:
    return Valid() if not conflicts else Invalid(tuple(conflicts))


class ConfigurationSolver(Protocol):
    name: str

    def validate(self, model: ProductModel, selections: Sequence[Selection]) -> Result: ...

    def validate_bundle(
        self, model: BundleModel, selections: Sequence[ComponentSelection], nested: Optional[NestedCheck] = None,
    ) -> Result: ...
