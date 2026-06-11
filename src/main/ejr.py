import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from numpy import sort
from pabutools.election import Project
from pabutools.utils import Numeric
from typing import Callable, Iterable
from src.main.typess import EJRViolationWitness, EJRViolationResult
from src.main.iteration_util import iterate_all_affordable_p_sets


def is_subsetset(p_set: tuple[int, ...], winning_set: set[int]) -> bool:
    for p in p_set:
        if p not in winning_set:
            return False
    return True


def find_ejr_violation_witness(
    approvals: list[set[int]],
    winning_set: set[int],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    utility_func: Callable[[Iterable[int], set[int]], Numeric],
    verbose: bool = True,
    exit_early: bool = False,
) -> EJRViolationResult:
    winning_util = [
        utility_func(winning_set, approvals[i]) for i in range(len(approvals))
    ]

    p_sets_checked = 0
    witnesses = []
    n = len(approvals)
    unsat_voter_union = set()
    unsat_voter_violation_union = set()
    satisfaction_degrees = {}
    p_sets_before_subset = 0
    p_sets_unsat_checked = 0

    def count_p_sets():
        nonlocal p_sets_checked
        p_sets_checked += 1

    def check_ejr(p_set: tuple[int, ...], voter_intersection: set[int]) -> bool:
        nonlocal p_sets_before_subset, p_sets_unsat_checked
        p_sets_before_subset = p_sets_before_subset + 1
        if is_subsetset(p_set, winning_set):
            return False  # T subsetset W

        p_sets_unsat_checked = p_sets_unsat_checked + 1

        unsat_voters = {
            i
            for i in voter_intersection
            if winning_util[i] < utility_func(p_set, approvals[i])
        }
        if not exit_early:
            unsat_voter_union.update(unsat_voters)

        # check if unsat_voters is T-cohesive, then EJR violation
        # done by computing the required size, for p_set to be affordable.
        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget
        if len(unsat_voters) >= needed_voters_larger_or_equal_to:
            if verbose:
                print(f"T: {p_set}, voters: {unsat_voters}")
            if exit_early:
                witnesses.append(EJRViolationWitness(p_set, unsat_voters, None))
                return True  # exit early, to find 1 witness

            unsat_voter_violation_union.update(unsat_voters)

            # for the voter i in the minimum set of voters, who is the closest to being satisfied
            # find the a in: a * util_p = util_win
            unsat_voters_list = list(unsat_voters)
            unsat_voters_util = [
                (winning_util[i] / utility_func(p_set, approvals[i]))
                for i in unsat_voters_list
            ]
            sorted_pairs = sorted(zip(unsat_voters_list, unsat_voters_util), key=lambda x: x[1])
            max_a_in_min_set_of_voters = sorted_pairs[
                int(needed_voters_larger_or_equal_to) - 1
            ][1]
            for i, a in sorted_pairs:
                if a >= max_a_in_min_set_of_voters:
                    satisfaction_degrees[i] = max(satisfaction_degrees.get(i, 0), a)
            witnesses.append(
                EJRViolationWitness(p_set, unsat_voters, max_a_in_min_set_of_voters)
            )
            return exit_early  # exit early, to find 1 witness

        return False  # continue searching for more witnesses, don't exit

    layers_checked = iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_ejr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(
        witness=witnesses,
        p_sets_checked=p_sets_checked,
        unsat_voter_union=(None if exit_early else unsat_voter_union),
        unsat_voter_violation_union=(
            None if exit_early else unsat_voter_violation_union
        ),
        p_sets_in_layer=layers_checked,
        satisfaction_degrees=(None if exit_early else satisfaction_degrees),
        p_sets_before_subset=p_sets_before_subset,
        p_sets_unsat_checked=p_sets_unsat_checked,
    )
