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
        layers_checked: int,
    ):
        self.witness = witness
        self.p_sets_checked = p_sets_checked
        self.unsat_voter_union = unsat_voter_union
        self.unsat_voter_violation_union = unsat_voter_violation_union
        self.layers_checked = layers_checked
