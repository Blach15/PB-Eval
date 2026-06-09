from collections.abc import Iterable
import sys, os

from src.main.checker import _build_ejr_inputs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pabutools.election import (
    AbstractProfile,
    Cardinality_Sat,
    Cost_Sat,
    Instance,
    parse_pabulib,
)
from pabutools.rules import (
    BudgetAllocation,
    completion_by_rule_combination,
    greedy_utilitarian_welfare,
    sequential_phragmen,
    method_of_equal_shares,
)
from pabutools.utils import Numeric
from ejr import find_ejr_violation_witness
import time
import json

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def map_types(instance: Instance, profile: AbstractProfile):
    projects = sorted(instance, key=lambda p: str(p))
    proj_name_to_idx: dict[str, int] = {str(p): idx for idx, p in enumerate(projects)}
    approvals = [set(proj_name_to_idx[str(p)] for p in ballot) for ballot in profile]
    costs = [p.cost for p in projects]
    budget = instance.budget_limit
    return approvals, costs, projects, budget, proj_name_to_idx

def voting_rule(
    instance: Instance,
    profile: AbstractProfile,
) -> BudgetAllocation | list[BudgetAllocation]:
    
    

    approvals, costs, projects, budget, proj_name_to_idx = map_types(instance, profile)


    def cost_utility_func(project_set: Iterable[int], ballot: set[int]) -> Numeric:
        return sum(costs[p] for p in project_set if p in ballot)

    outcome1 = method_of_equal_shares(
                instance, profile, sat_class=Cost_Sat
            )

    winning_set = {proj_name_to_idx[str(p)] for p in outcome1}
    print(f"Winning set: {winning_set}")


    violations = find_ejr_violation_witness(
        approvals,
        winning_set,
        costs,
        projects,
        budget,
        cost_utility_func,
        verbose=False,
        exit_early=False,
    )

    if violations.satisfaction_degrees is None:
        raise ValueError("Expected satisfaction degrees to be computed for FJR violation witness.")
    
    violations_dict = {i: 1 - d for i, d in violations.satisfaction_degrees.items()}

    # scale by how violated they are
    def card_utility_func(project_set: Iterable[int], voter_i: int) -> Numeric:
        return violations_dict[voter_i] * len([a for a in project_set if a in approvals[voter_i]])

    P = {proj_name_to_idx[str(p)] for p in projects} - winning_set

    def greedy_completion_rule():
        2
    
    return method_of_equal_shares(
                instance, profile, sat_class=Cost_Sat
            )
