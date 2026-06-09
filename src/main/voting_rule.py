import sys, os

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
import time
import json

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

def voting_rule(
    instance: Instance,
    profile: AbstractProfile,
) -> BudgetAllocation | list[BudgetAllocation]:
    return method_of_equal_shares(
                instance, profile, sat_class=Cost_Sat
            )
