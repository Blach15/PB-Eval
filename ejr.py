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


def find_ejr_violation_witness(
    approvals: list[set[int]],
    winning_set: set[int],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    utility_func: Callable[[set[int] | frozenset[int], set[int]], Numeric],
    verbose: bool = True,
) -> EJRViolationResult:
    project_supporters = get_project_supporters(approvals, projects)
    winning_util = [
        utility_func(winning_set, approvals[i]) for i in range(len(approvals))
    ]

    n = len(approvals)

    current_lattice_layer_worklist: set[frozenset[int]] = set()
    next_lattice_layer_worklist: set[frozenset[int]] = set()

    for pIdx in range(len(projects)):
        next_lattice_layer_worklist.add(frozenset({pIdx}))

    p_sets_checked = 0

    while len(next_lattice_layer_worklist) > 0:
        current_lattice_layer_worklist = next_lattice_layer_worklist
        surviving_lattice_layer_worklist = []

        # print(
        #    f"Current layer size: {len(current_lattice_layer_worklist[0])}, {len(current_lattice_layer_worklist)}"
        # )

        for p_set in current_lattice_layer_worklist:
            p_sets_checked += 1

            voter_intersection = set()
            for p in p_set:
                voter_intersection = (
                    project_supporters[p]
                    if len(voter_intersection) == 0
                    else voter_intersection & project_supporters[p]  # bug here ?
                )
            # check that is cohesive set
            if len(voter_intersection) / n * budget < sum(costs[p] for p in p_set):
                continue  # can't afford

            unsat_voters = {
                i
                for i in voter_intersection
                if winning_util[i] < utility_func(p_set, approvals[i])
            }
            # if len(unsat_voters) == 0: #bug?
            #     continue

            # check if coheisive set violates EJR
            # bug: missnig coheisive check.
            # instead check unsat_voters for cohesive, then withness
            if len(unsat_voters) / n * budget >= sum(costs[p] for p in p_set):
                if verbose:
                    print(f"T: {p_set}, voters: {unsat_voters}")
                return EJRViolationResult(
                    witness=EJRViolationWitness(p_set, unsat_voters),
                    p_sets_checked=p_sets_checked,
                )

            surviving_lattice_layer_worklist.append(p_set)

        # create all combinations, apriori style
        if verbose and len(surviving_lattice_layer_worklist) != 0:
            print(
                f"Surviving layer size: {len(surviving_lattice_layer_worklist[0])}, {len(surviving_lattice_layer_worklist)}"
            )
        next_lattice_layer_worklist = set()
        for i in range(len(surviving_lattice_layer_worklist)):
            for j in range(i + 1, len(surviving_lattice_layer_worklist)):
                new_set = (
                    surviving_lattice_layer_worklist[i]
                    | surviving_lattice_layer_worklist[j]
                )
                if (
                    len(new_set) == len(surviving_lattice_layer_worklist[i]) + 1
                    and new_set not in next_lattice_layer_worklist
                ):
                    next_lattice_layer_worklist.add(frozenset(new_set))

    return EJRViolationResult(witness=None, p_sets_checked=p_sets_checked)


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
