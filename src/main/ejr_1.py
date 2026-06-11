import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pabutools.election import Project
from pabutools.utils import Numeric
from typing import Callable, Iterable
from src.main.typess import EJRViolationWitness, EJRViolationResult
from src.main.iteration_util import iterate_all_affordable_p_sets


def find_ejr_1_violation_witness(
    approvals: list[set[int]],
    winning_set: set[int],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    utility_func: Callable[[Iterable[int], set[int]], Numeric],
    verbose: bool = True,
) -> EJRViolationResult:
    winning_util = [
        utility_func(winning_set, approvals[i]) for i in range(len(approvals))
    ]

    p_sets_checked = 0
    p_sets_before_subset = 0
    p_sets_unsat_checked = 0
    witnesses = []
    n = len(approvals)

    def count_p_sets():
        nonlocal p_sets_checked
        p_sets_checked += 1

    def max_util_from_unpicked(
        voter_index: int, p_set: tuple[int, ...]
    ) -> tuple[int | None, Numeric]:
        # marginal utility of adding best project to p_set for voter i
        max_util = 0
        max_proj = None
        for p in p_set:
            if p not in winning_set:
                util_p = utility_func((p,), approvals[voter_index])
                if util_p > max_util:
                    max_util = util_p
                    max_proj = p
        if max_proj is None:
            return None, -1
        return max_proj, max_util

    def check_ejr_1(p_set: tuple[int, ...], voter_intersection: set[int]) -> bool:
        nonlocal p_sets_before_subset, p_sets_unsat_checked
        p_sets_before_subset = p_sets_before_subset + 1
        voters_projects = {
            i: max_util_from_unpicked(i, p_set) for i in voter_intersection
        }

        # Check if any voter has no project available
        if any(p is None for i, (p, util) in voters_projects.items()):
            return False  # T subsetset W

        p_sets_unsat_checked = p_sets_unsat_checked + 1

        unsat_voters = {
            i
            for i in voter_intersection
            if winning_util[i] + voters_projects[i][1]
            <= utility_func(p_set, approvals[i])
        }

        # check if unsat_voters is T-cohesive, then EJR violation
        # done by computing the required size, for p_set to be affordable.
        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget
        if len(unsat_voters) >= needed_voters_larger_or_equal_to:

            witnesses.append(EJRViolationWitness(p_set, unsat_voters, None))
            return True  # exit early, to find 1 witness

        return False

    layers_checked = iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_ejr_1,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(
        witness=witnesses,
        p_sets_checked=p_sets_checked,
        unsat_voter_union=None,
        unsat_voter_violation_union=None,
        p_sets_in_layer=layers_checked,
        satisfaction_degrees=None,
        p_sets_before_subset=p_sets_before_subset,
        p_sets_unsat_checked=p_sets_unsat_checked,
    )
