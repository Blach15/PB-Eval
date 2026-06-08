import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pabutools.election import Project
from pabutools.utils import Numeric
from typing import Callable, Iterable
from src.main.typess import EJRViolationWitness, EJRViolationResult
from src.main.iteration_util import iterate_all_affordable_p_sets


def find_pjr_violation_witness(
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
    witnesses = []
    n = len(approvals)

    approvals_union: set[int] = set()
    for ballot in approvals:
        approvals_union |= ballot

    # Precompute per-project utility w.r.t. approvals_union (additive, non-negative).
    # Sort descending so high-contribution projects are tried first, enabling earlier pruning.
    proj_util = {p: utility_func((p,), approvals_union) for p in winning_set}
    sorted_winning = sorted(winning_set, key=lambda p: proj_util[p], reverse=True)

    def count_p_sets():
        nonlocal p_sets_checked
        p_sets_checked += 1

    util_p_sets = []

    def check_pjr(p_set: tuple[int, ...], voter_intersection: set[int]) -> bool:
        unsat_voters = {
            i
            for i in voter_intersection
            if winning_util[i] < utility_func(p_set, approvals[i])
        }

        util_p = utility_func(p_set, approvals_union)
        # create powerset of winning set, while for each subset X: util(X) < util_p

        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget

        approval_winning_intersection = [
            frozenset(winning_set & approvals[i]) for i in unsat_voters
        ]
        map_from_project_set_to_count = {}
        for i in approval_winning_intersection:
            map_from_project_set_to_count[i] = (
                map_from_project_set_to_count.get(i, 0) + 1
            )

        # Generator: yields only subsets of winning_set whose utility < util_p.
        # Since utility is additive and non-negative, any superset of a set with
        # util >= util_p also has util >= util_p, so those branches are pruned.
        def subsets_below_util(idx: int, current: list, current_util):
            yield tuple(current)
            for i in range(idx, len(sorted_winning)):
                p = sorted_winning[i]
                new_util = current_util + proj_util[p]
                if new_util < util_p:
                    current.append(p)
                    yield from subsets_below_util(i + 1, current, new_util)
                    current.pop()

        for x in subsets_below_util(0, [], 0):
            # Check if there are enough voters whose approval sets form a subset of x, such that they are a T-cohesive group. If so, then PJR violation.
            count_voters_with_subset_x = 0
            for their_proj, count in map_from_project_set_to_count.items():
                if their_proj.issubset(x):
                    count_voters_with_subset_x += count
            if count_voters_with_subset_x >= needed_voters_larger_or_equal_to:
                if verbose:
                    print(f"T: {p_set}, voters: {unsat_voters}, X: {x}")
                witnesses.append(EJRViolationWitness(p_set, unsat_voters, None))
                # only find 1 witness
                return True

        return False  # continue searching for more witnesses, don't exit early

    layers_checked = iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_pjr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(
        witness=witnesses,
        p_sets_checked=p_sets_checked,
        unsat_voter_union=None,
        unsat_voter_violation_union=None,
        p_sets_in_layer=layers_checked,
    )
