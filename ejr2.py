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
) -> bool:
    project_supporters = [set() for _ in range(len(projects))]
    for voter_idx, ballot in enumerate(approvals):
        for p in ballot:
            project_supporters[p].add(voter_idx)
    
    return True


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
