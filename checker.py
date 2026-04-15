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
import time
from ejr_old import find_ejr_violation, run_election
from ejr import find_ejr_violation_witness, convert_inputs_to_ejr_types


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
    instance, profile, outcome = run_election(filename, rule="greedy", util=Cardinality_Sat)
    violation = find_ejr_violation(instance, profile, outcome, util=Cardinality_Sat, verbose=False)
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


def test_ejr_algorithms(filename: str):
    violation1, time1 = timer(filename, ejr1)
    violation2, time2 = timer(filename, ejr2)

    print(f"ejr1 time: {time1:.4f}s, ejr2 time: {time2:.4f}s")
    print(
        f"ejr1 p-sets checked: {violation1.p_sets_checked}, ejr2 p-sets checked: {violation2.p_sets_checked}"
    )

    if (violation1.witness is None) or (violation2.witness is None):
        if not ((violation1.witness is None) and (violation2.witness is None)):
            print(
                "Discrepancy found!",
                f"violation1: {violation1.witness}",
                f"violation2: {violation2.witness}",
            )
        else:
            print("No violation found in either.")
    else:
        print("Violation in both.")

def run_all():
    elections_dir = "./elections/"
    files = [f for f in os.listdir(elections_dir) if f.endswith(".pb")]

    for filename in sorted(files):
        print(f"\n--- {filename} ---")
        try:
            test_ejr_algorithms(filename)
        except Exception as e:
            print(f"Error: {e}")

def run_one():
    filename = "Netherlands_Amsterdam_288.pb"
    print(f"\n--- {filename} ---")
    try:
        test_ejr_algorithms(filename)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_one()