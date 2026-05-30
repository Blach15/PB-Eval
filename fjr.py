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
from pabutools.utils import Numeric
from typing import Callable, Iterable
import os
from typess import EJRViolationWitness, EJRViolationResult
from ejr import iterate_all_affordable_p_sets


def iterate_all_affordable_p_sets_fjr(
    approvals: list[set[int]],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    voters: set[int],
    callback: Callable[[tuple[int, ...], set[int]], bool],
    pre_callback: Callable[[], None] = lambda: None,
    verbose: bool = False,
):
    current_lattice_layer_worklist: list[tuple[int, ...]] = list()
    next_lattice_layer_worklist: list[tuple[int, ...]] = list()

    for pIdx in range(len(projects)):
        p_set: tuple[int, ...] = (pIdx,)
        next_lattice_layer_worklist.append(p_set)

    while len(next_lattice_layer_worklist) > 0:
        current_lattice_layer_worklist = next_lattice_layer_worklist
        surviving_lattice_layer_worklist: list[tuple[int, ...]] = []

        for p_set in current_lattice_layer_worklist:
            pre_callback()

            # check that p_set is affordable within budget
            if sum(costs[p] for p in p_set) > budget:
                continue

            # allow exit early, to find 1 witness
            if callback(p_set, voters):
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
                    next_lattice_layer_worklist.append(new_set)
                else:
                    # Since itemsets are sorted, if prefixes don't match, skip to next i
                    break

    return None


def find_fjr_violation_witness(
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

    def count_p_sets():
        nonlocal p_sets_checked
        p_sets_checked += 1

    # First pass: collect all voters that are ever unsatisfied by any affordable p_set
    all_unsat_voters: set[int] = set()

    def collect_unsat(p_set: tuple[int, ...], _voter_intersection: set[int]) -> bool:
        all_unsat_voters.update(
            i for i in range(n) if winning_util[i] < utility_func(p_set, approvals[i])
        )
        return False

    iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=collect_unsat,
    )

    def check_fjr(p_set: tuple[int, ...], voters: set[int]) -> bool:
        unsat_voters = {
            i for i in voters if winning_util[i] < utility_func(p_set, approvals[i])
        }

        # check if unsat_voters is T-cohesive, then EJR violation
        # done by computing the required size, for p_set to be affordable.
        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget
        if len(unsat_voters) >= needed_voters_larger_or_equal_to:
            if verbose:
                print(f"T: {p_set}, voters: {unsat_voters}")

            witnesses.append(EJRViolationWitness(p_set, unsat_voters, None))
            return exit_early  # exit early, to find 1 witness

        return False  # continue searching for more witnesses, don't exit early

    iterate_all_affordable_p_sets_fjr(
        approvals,
        costs,
        projects,
        budget,
        voters=all_unsat_voters,
        callback=check_fjr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(witness=witnesses, p_sets_checked=p_sets_checked)


# Idea 1: only usat voters are interesting:
# Run ejr, and store all the unsat voters, then try all those combinations.

# Idea 2: Iterate all T, find unsat for each T, then check if unsat is T-cohesive

# Idea 3: for each voter compute each combination of A, where they would be unsat, then be smart to filter out, that no more unsat will come above 
# like check all their interections when you move up the lattice 