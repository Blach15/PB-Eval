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
from typing import Callable
import os
from typess import EJRViolationWitness, EJRViolationResult


def interate_all_affordable_p_sets(
    approvals: list[set[int]],
    winning_set: set[int],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    callback: Callable[[frozenset[int], set[int]], bool],
    pre_callback: Callable[[], None] = lambda: None,
    verbose: bool = False,
):
    project_supporters = get_project_supporters(approvals, projects)

    n = len(approvals)

    current_lattice_layer_worklist: set[frozenset[int]] = set()
    next_lattice_layer_worklist: set[frozenset[int]] = set()
    voter_intersection_cache: dict[frozenset[int], set[int]] = {}

    for pIdx in range(len(projects)):
        p_set = frozenset({pIdx})
        next_lattice_layer_worklist.add(p_set)
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
        next_lattice_layer_worklist = set()

        # Convert to sorted tuples for apriori join
        sorted_itemsets = sorted(
            [tuple(sorted(p_set)) for p_set in surviving_lattice_layer_worklist]
        )

        # Apriori join: only join itemsets that share the first k-1 elements
        for i in range(len(sorted_itemsets)):
            for j in range(i + 1, len(sorted_itemsets)):
                itemset_i = sorted_itemsets[i]
                itemset_j = sorted_itemsets[j]

                # Check if they share the first k-1 elements (apriori property)
                if itemset_i[:-1] == itemset_j[:-1]:
                    new_set = frozenset(itemset_i) | frozenset(itemset_j)
                    if new_set not in next_lattice_layer_worklist:
                        # Cache the voter_intersection as intersection of the two parent sets' intersections
                        voter_intersection_cache[new_set] = (
                            voter_intersection_cache[frozenset(itemset_i)]
                            & voter_intersection_cache[frozenset(itemset_j)]
                        )
                        next_lattice_layer_worklist.add(new_set)
                else:
                    # Since itemsets are sorted, if prefixes don't match, skip to next i
                    break

    return None


def find_ejr_violation_witness(
    approvals: list[set[int]],
    winning_set: set[int],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    utility_func: Callable[[set[int] | frozenset[int], set[int]], Numeric],
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

    def check_ejr(p_set: frozenset[int], voter_intersection: set[int]) -> bool:
        unsat_voters = {
            i
            for i in voter_intersection
            if winning_util[i] < utility_func(p_set, approvals[i])
        }

        # check if unsat_voters is T-cohesive, then EJR violation
        # done by computing the required size, for p_set to be affordable.
        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget
        if len(unsat_voters) >= needed_voters_larger_or_equal_to:
            if verbose:
                print(f"T: {p_set}, voters: {unsat_voters}")

            # for the voter i in the minimum set of voters, who is the closest to being satisfied
            # find the a in: a * util_p = util_win
            unsat_voters_util = [
                (winning_util[i] / utility_func(p_set, approvals[i]))
                for i in unsat_voters
            ]
            max_a_in_min_set_of_voters = sort(unsat_voters_util)[
                int(needed_voters_larger_or_equal_to) - 1
            ]
            witnesses.append(
                EJRViolationWitness(p_set, unsat_voters, max_a_in_min_set_of_voters)
            )

        return False  # continue searching for more witnesses, don't exit early

    interate_all_affordable_p_sets(
        approvals,
        winning_set,
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


def convert_inputs_to_ejr_types(
    instance: Instance,
    profile: Profile,
    outcome_greedy: BudgetAllocation | list[BudgetAllocation],
) -> tuple[list[set[int]], set[int], list[Numeric], list[Project], Numeric]:
    """
    Converts inputs from `instance`, `profile`, and `outcome_greedy` to the types required by `find_ejr_violation_witness`.

    Returns:
        approvals: list[set[int]]
        winning_set: set[int]
        costs: list[Numeric]
        projects: list[Project]
        budget: Numeric
    """
    projects = list(instance)
    proj_to_idx = {p: idx for idx, p in enumerate(projects)}

    approvals = [set(proj_to_idx[p] for p in ballot) for ballot in profile]

    # Ensure winning_set contains integers (indices of projects)
    winning_set = set()
    if isinstance(outcome_greedy, list):
        for alloc in outcome_greedy:
            if isinstance(alloc, Project):
                winning_set.add(proj_to_idx[alloc])
            elif isinstance(alloc, BudgetAllocation):
                # Handle BudgetAllocation appropriately (e.g., extract relevant projects or indices)
                raise NotImplementedError(
                    "Handling of BudgetAllocation in outcome_greedy is not implemented."
                )
                pass
    elif isinstance(outcome_greedy, Project):
        winning_set.add(proj_to_idx[outcome_greedy])
    elif isinstance(outcome_greedy, BudgetAllocation):
        # Handle single BudgetAllocation appropriately
        raise NotImplementedError(
            "Handling of BudgetAllocation in outcome_greedy is not implemented."
        )
        pass

    costs = [p.cost for p in projects]
    budget = instance.budget_limit

    return (approvals, winning_set, costs, projects, budget)


if __name__ == "__main__":

    def card_utility_func(
        project_set: set[int] | frozenset[int], ballot: set[int]
    ) -> Numeric:
        return len(project_set & ballot)

    def cost_utility_func(
        project_set: set[int] | frozenset[int], ballot: set[int]
    ) -> Numeric:
        return sum(costs[p] for p in (project_set & ballot))

    path = os.path.join("./elections/", "Hungary_Budapest_2024.pb")
    # path = os.path.join("./elections/", "Netherlands_Amsterdam_332.pb")
    instance, profile = parse_pabulib(path)
    outcome_greedy = greedy_utilitarian_welfare(
        instance, profile, sat_class=Cost_Sat, analytics=False
    )

    (approvals, winning_set, costs, projects, budget) = convert_inputs_to_ejr_types(
        instance, profile, outcome_greedy
    )

    violation = find_ejr_violation_witness(
        approvals, winning_set, costs, projects, budget, cost_utility_func
    )
    print(violation)
    print(outcome_greedy)


# 1,2 - 3,4 - 3,5 - 4.5 -> {1,2,3,4,5} -> 3^{1,2,3,4,5}

# % 1,2,3
