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
from pabutools.election import (
    Project,
    Instance,
    Cost_Sat,
    parse_pabulib,
)
from pabutools.rules import (
    greedy_utilitarian_welfare,
)
from pabutools.utils import Numeric
from typing import Callable
import os
import time
from ejr import convert_pabutools_election, find_ejr_violation
from ejr2 import find_ejr_violation_witness, convert_inputs_to_ejr_types


def parsefile(filename: str):
    path = os.path.join("./elections/", filename)
    instance, profile = parse_pabulib(path)
    outcome = greedy_utilitarian_welfare(
        instance, profile, sat_class=Cardinality_Sat, analytics=False
    )
    return instance, profile, outcome


def ejr2(filename: str):
    instance, profile, outcome = parsefile(filename)

    def card_utility_func(
        project_set: set[int] | frozenset[int], ballot: set[int]
    ) -> Numeric:
        return len(project_set & ballot)

    def cost_utility_func(
        project_set: set[int] | frozenset[int], ballot: set[int]
    ) -> Numeric:
        return sum(costs[p] for p in (project_set & ballot))

    (approvals, winning_set, costs, projects, budget) = convert_inputs_to_ejr_types(
        instance, profile, outcome
    )

    violation = find_ejr_violation_witness(
        approvals,
        winning_set,
        costs,
        projects,
        budget,
        card_utility_func,
        verbose=False,
    )
    return violation


def ejr1(filename: str):
    instance, profile, outcome = parsefile(filename)
    project_names, costs, approvals, winners, budget = convert_pabutools_election(
        instance, profile, outcome
    )
    violation = find_ejr_violation(
        costs, approvals, winners, budget, project_names, verbose=False
    )
    return violation


def run_both(filename: str):
    violation1 = ejr1(filename)
    violation2 = ejr2(filename)

    return violation1, violation2


def timer(filename: str, ejr_func):
    start = time.time()
    violation = ejr_func(filename)
    timing = time.time() - start

    return violation, timing


if __name__ == "__main__":
    # filename = "Hungary_Budapest_2024.pb"
    filename = "Netherlands_Amsterdam_622.pb"

    violation1, time1 = timer(filename, ejr1)
    violation2, time2 = timer(filename, ejr2)

    print(f"ejr1 time: {time1:.4f}s, ejr2 time: {time2:.4f}s")

    if (violation1 is None) or (violation2 is None):
        if not ((violation1 is None) and (violation2 is None)):
            print(
                "Discrepancy found!",
                f"violation1: {violation1}",
                f"violation2: {violation2}",
            )
        else:
            print("No violation found in either.")
    else:
        print("Violation in both.")
