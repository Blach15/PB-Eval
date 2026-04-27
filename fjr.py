from numpy import sort
from pabutools.election import (
    Cardinality_Sat,
    Project,
    Instance,
    Profile,
    Cost_Sat,
    parse_pabulib,
)
from pabutools.rules import (
    greedy_utilitarian_welfare,
    BudgetAllocation,
)
from itertools import combinations, chain
from pabutools.utils import Numeric, combinations
from typing import Callable, Iterable
import os
from typess import EJRViolationWitness, EJRViolationResult


def iterate_all_affordable_p_sets_beta(
    approvals: list[set[int]],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    callback: Callable[[tuple[int], set[int]], bool],
    pre_callback: Callable[[], None] = lambda: None,
    verbose: bool = False,
):
    project_supporters = get_project_supporters(approvals, projects)

    n = len(approvals)

    current_lattice_layer_worklist: list[tuple[int]] = list()
    next_lattice_layer_worklist: list[tuple[int]] = list()
    voter_intersection_cache: dict[tuple[int], set[int]] = {}

    for pIdx in range(len(projects)):
        p_set: tuple[int] = (pIdx,)
        next_lattice_layer_worklist.append(p_set)
        voter_intersection_cache[p_set] = project_supporters[pIdx]

    while len(next_lattice_layer_worklist) > 0:
        current_lattice_layer_worklist = next_lattice_layer_worklist
        surviving_lattice_layer_worklist = []

        for p_set in current_lattice_layer_worklist:
            
            
            pre_callback()
            # Get cached voter_intersection or calculate if not in cache
            voter_intersection = voter_intersection_cache[p_set]
            if voter_intersection is None:
                raise ValueError(f"Voter intersection for {p_set} not found in cache.")
            # check that is cohesive set
            if len(voter_intersection) / n * budget < sum(costs[p] for p in p_set):
                continue  # can't afford

            # allow exit early, to find 1 witness
            if callback(p_set, voter_intersection):
                return None

            surviving_lattice_layer_worklist.append(p_set)

        if verbose and len(surviving_lattice_layer_worklist) != 0:
            print(
                f"Surviving layer size: {len(surviving_lattice_layer_worklist[0])}, {len(surviving_lattice_layer_worklist)}"
            )
        next_lattice_layer_worklist = list()

        # Apriori join: only join itemsets that share the first k-1 elements
        for i in range(len(surviving_lattice_layer_worklist)):
            for j in range(i + 1, len(surviving_lattice_layer_worklist)):
                itemset_i = surviving_lattice_layer_worklist[i]
                itemset_j = surviving_lattice_layer_worklist[j]

                # Check if they share the first k-1 elements (apriori property)
                if itemset_i[:-1] == itemset_j[:-1]:
                    # keep the new set sorted.
                    new_set = tuple(itemset_i + (itemset_j[-1],))
                    if new_set not in next_lattice_layer_worklist:
                        # Cache the voter_intersection as intersection of the two parent sets' intersections
                        voter_intersection_cache[new_set] = (
                            voter_intersection_cache[itemset_i]
                            & voter_intersection_cache[itemset_j]
                        )
                        next_lattice_layer_worklist.append(new_set)
                else:
                    # Since itemsets are sorted, if prefixes don't match, skip to next i
                    break

    return None



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
    witnesses = []
    n = len(approvals)

    def count_p_sets():
        nonlocal p_sets_checked
        p_sets_checked += 1

    def max_util_from_unpicked(voter_index: int, p_set: tuple[int]) -> Numeric:
        # marginal utility of adding best project to p_set for voter i
        max_util = 0
        for p in p_set:
            if p not in winning_set:
                util_p = utility_func((p,), approvals[voter_index])
                max_util = max(max_util, util_p)
        return max_util

    def check_ejr(p_set: tuple[int], voter_intersection: set[int]) -> bool:
        unsat_voters = {
            i
            for i in voter_intersection
            if winning_util[i] + max_util_from_unpicked(i, p_set)
            < utility_func(p_set, approvals[i])
        }

        # check if unsat_voters is T-cohesive, then EJR violation
        # done by computing the required size, for p_set to be affordable.
        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget
        if len(unsat_voters) >= needed_voters_larger_or_equal_to:

            witnesses.append(EJRViolationWitness(p_set, unsat_voters, None))
            return True  # exit early, to find 1 witness

        return False

    iterate_all_affordable_p_sets_beta(
        approvals,
        costs,
        projects,
        budget,
        callback=check_ejr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(witness=witnesses, p_sets_checked=p_sets_checked)





def get_project_supporters(approvals, projects) -> list[set[int]]:
    project_supporters = [set() for _ in range(len(projects))]
    for voter_idx, ballot in enumerate(approvals):
        for p in ballot:
            project_supporters[p].add(voter_idx)
    return project_supporters

