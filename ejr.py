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


def iterate_all_affordable_p_sets(
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


def find_ejr_violation_witness(
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

    def check_ejr(p_set: tuple[int], voter_intersection: set[int]) -> bool:
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

    iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_ejr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(witness=witnesses, p_sets_checked=p_sets_checked)


def powerset(iterable: Iterable):

    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))


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

            witnesses.append(EJRViolationWitness(p_set, unsat_voters, -2))
            return True  # exit early, to find 1 witness

        return False

    iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_ejr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(witness=witnesses, p_sets_checked=p_sets_checked)


def find_ejr_x_violation_witness(
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

    def min_util_from_unpicked(voter_index: int, p_set: tuple[int]) -> Numeric:
        # marginal utility of adding worst project to p_set for voter i
        min_util = 0
        for p in p_set:
            if p not in winning_set:
                util_p = utility_func((p,), approvals[voter_index])
                min_util = min(min_util, util_p)
        return min_util

    def check_ejr(p_set: tuple[int], voter_intersection: set[int]) -> bool:
        unsat_voters = {
            i
            for i in voter_intersection
            if winning_util[i] + min_util_from_unpicked(i, p_set)
            < utility_func(p_set, approvals[i])
        }

        # check if unsat_voters is T-cohesive, then EJR violation
        # done by computing the required size, for p_set to be affordable.
        needed_voters_larger_or_equal_to = (sum(costs[p] for p in p_set) * n) / budget
        if len(unsat_voters) >= needed_voters_larger_or_equal_to:

            witnesses.append(EJRViolationWitness(p_set, unsat_voters, -2))
            return True  # exit early, to find 1 witness

        return False

    iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_ejr,
        pre_callback=count_p_sets,
        verbose=verbose,
    )

    return EJRViolationResult(witness=witnesses, p_sets_checked=p_sets_checked)


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

    def check_pjr(p_set: tuple[int], voter_intersection: set[int]) -> bool:
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
                witnesses.append(EJRViolationWitness(p_set, unsat_voters, -1))
                # only find 1 witness
                return True

        return False  # continue searching for more witnesses, don't exit early

    iterate_all_affordable_p_sets(
        approvals,
        costs,
        projects,
        budget,
        callback=check_pjr,
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
    projects = sorted(instance, key=lambda p: str(p))
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

    def card_utility_func(project_set: Iterable[int], ballot: set[int]) -> Numeric:
        return len([a for a in project_set if a in ballot])

    def cost_utility_func(project_set: Iterable[int], ballot: set[int]) -> Numeric:
        return sum(costs[p] for p in ([a for a in project_set if a in ballot]))

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
        approvals,
        winning_set,
        costs,
        projects,
        budget,
        cost_utility_func,
        verbose=False,
    )
    print(violation.p_sets_checked)


# 1,2 - 3,4 - 3,5 - 4.5 -> {1,2,3,4,5} -> 3^{1,2,3,4,5}

# % 1,2,3
