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
    n = len(approvals)
    voters = set(range(n))

    current_lattice_layer_worklist: list[tuple[int, ...]] = list()
    next_lattice_layer_worklist: list[tuple[int, ...]] = list()

    for pIdx in range(len(projects)):
        p_set: tuple[int, ...] = (pIdx,)
        next_lattice_layer_worklist.append(p_set)

    while len(next_lattice_layer_worklist) > 0:
        current_lattice_layer_worklist = next_lattice_layer_worklist
        surviving_lattice_layer_worklist: list[tuple[int, ...]] = []
        all_voters_unsat_in_layer = True
        print(f"Checking layer of size {len(current_lattice_layer_worklist)} sets")

        for p_set in current_lattice_layer_worklist:
            p_sets_checked += 1

            # check that p_set is affordable within budget
            if sum(costs[p] for p in p_set) > budget:
                continue

            unsat_voters = {
                i for i in voters if winning_util[i] < utility_func(p_set, approvals[i])
            }

            if unsat_voters != voters:
                all_voters_unsat_in_layer = False

            # check if unsat_voters is T-cohesive, then EJR violation
            # done by computing the required size, for p_set to be affordable.
            needed_voters_larger_or_equal_to = (
                sum(costs[p] for p in p_set) * n
            ) / budget
            if len(unsat_voters) >= needed_voters_larger_or_equal_to:
                if verbose:
                    print(f"T: {p_set}, voters: {unsat_voters}")

                return EJRViolationResult(
                    witness=[EJRViolationWitness(p_set, unsat_voters, None)],
                    p_sets_checked=p_sets_checked,
                    unsat_voter_union=None,
                )

            surviving_lattice_layer_worklist.append(p_set)

        if all_voters_unsat_in_layer:
            break

        print(
            f"Checked {len(current_lattice_layer_worklist[0])} sets in current layer, {p_sets_checked} total"
        )

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
    return EJRViolationResult(
        witness=[], p_sets_checked=p_sets_checked, unsat_voter_union=None
    )


# Idea 1: only usat voters are interesting:
# Run ejr, and store all the unsat voters, then try all those combinations.

# Idea 2: Iterate all T, find unsat for each T, then check if unsat is T-cohesive

# Idea 3: for each voter compute each combination of A, where they would be unsat, then be smart to filter out, that no more unsat will come above
# like check all their interections when you move up the lattice

# Idea 4: for card, if |W| = 3, then a violation cant have size 5 or more. -> done if no violation in layer 4
# cost? c(W) + i's min/max project cost?

# Idea 4.1: once all unsat, then only check rest of layer
