from pabutools.election import (
    Project,
    Instance,
    ApprovalBallot,
    ApprovalProfile,
    Cost_Sat,
    parse_pabulib,
)
from pabutools.rules import (
    greedy_utilitarian_welfare,
    sequential_phragmen,
    method_of_equal_shares,
)
from pabutools.utils import Numeric
from typing import Callable
import os


def normalize_input(instance, profile, outcome):
    project_names = []
    project_costs = []
    for p in list(instance):
        project_names.append(p.name)
        project_costs.append(p.cost)

    return True


def find_ejr_violation_witness(
    approvals: list[set[int]],
    winning_set: set[int],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    utility_func: Callable[[set[int], set[int]], int],
) -> bool:
    project_supporters = get_project_supporters(approvals, projects)
    winning_util = [
        utility_func(winning_set, approvals[i]) for i in range(len(approvals))
    ]

    current_lattice_layer_worklist = []
    next_lattice_layer_worklist = []

    for p in projects:
        next_lattice_layer_worklist.append({p})

    while len(next_lattice_layer_worklist) > 0:
        current_lattice_layer_worklist = next_lattice_layer_worklist
        next_lattice_layer_worklist = []

        for p_set in current_lattice_layer_worklist:
            unsat_voters = {
                i
                for i in range(len(approvals))
                if winning_util[i] < utility_func(p_set, approvals[i]) * budget
            }
            if len(unsat_voters) == 0:
                continue

            # try and make a T-cohesive set out of p_set and unsat_voters
            

        next_lattice_layer_worklist = []  # todo: generate next layer of lattice

    return True


def get_project_supporters(approvals, projects) -> list[set[int]]:
    project_supporters = [set() for _ in range(len(projects))]
    for voter_idx, ballot in enumerate(approvals):
        for p in ballot:
            project_supporters[p].add(voter_idx)
    return project_supporters


def convert_inputs_to_ejr_types(
    instance: Instance, profile: ApprovalProfile, outcome_greedy: list[int]
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
    winning_set = set(outcome_greedy)
    costs = [p.cost for p in projects]
    budget = instance.budget_limit

    return (approvals, winning_set, costs, projects, budget)
