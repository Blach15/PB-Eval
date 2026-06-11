from typing import Optional

from pabutools.utils import Numeric


class EJRViolationWitness:
    def __init__(
        self, p_set: tuple[int, ...], voters: set[int], max_util: Numeric | None
    ):
        self.p_set = p_set
        self.voters = voters
        self.max_util = max_util

    def __str__(self):
        return f"p_set_size: {len(self.p_set)}, p_set: {self.p_set}, support_count: {len(self.voters)}, max_util: {self.max_util}"


class EJRViolationResult:
    def __init__(
        self,
        witness: list[EJRViolationWitness],
        p_sets_checked: int,
        unsat_voter_union: Optional[set[int]],
        unsat_voter_violation_union: Optional[set[int]],
        p_sets_in_layer: dict[int, int],
        satisfaction_degrees: Optional[dict[int, float]],
        p_sets_before_subset: Optional[int] = None,
        p_sets_unsat_checked: Optional[int] = None,
    ):
        self.witness = witness
        self.p_sets_checked = p_sets_checked
        self.unsat_voter_union = unsat_voter_union
        self.unsat_voter_violation_union = unsat_voter_violation_union
        self.p_sets_in_layer = p_sets_in_layer
        self.satisfaction_degrees = satisfaction_degrees
        self.p_sets_before_subset = p_sets_before_subset
        self.p_sets_unsat_checked = p_sets_unsat_checked

    @property
    def layers_checked(self) -> int:
        return max(self.p_sets_in_layer.keys(), default=0)
