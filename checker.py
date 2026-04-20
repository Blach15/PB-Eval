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
    sequential_phragmen,
    method_of_equal_shares,
    BudgetAllocation,
)
from pabutools.utils import Numeric
from typing import Callable
import os
import time
import json
from ejr import find_ejr_violation_witness, convert_inputs_to_ejr_types
from typess import EJRViolationWitness, EJRViolationResult


def parsefile(filename: str):
    path = os.path.join("./elections/", filename)
    instance, profile = parse_pabulib(path)

    # Compute metadata
    projects = list(instance)
    costs = [p.cost for p in projects]
    approvals = [set(ballot) for ballot in profile]


    average_project_cost = sum(costs) / len(projects)
    projects_to_voters_ratio = len(costs) / len(approvals)
    vote_length = sum(len(ballot) for ballot in approvals) / len(approvals)
    vote_length_to_projects_ratio = vote_length / len(projects)

    metadata = {
        "number_of_voters": float(len(approvals)),
        "number_of_projects": float(len(projects)),
        "vote_length": float(vote_length),
        "average_project_cost": float(average_project_cost),
        "projects_to_voters_ratio": float(projects_to_voters_ratio),
        "vote_length_to_projects_ratio": float(vote_length_to_projects_ratio),
        "min_length": instance.meta.get("min_length", None),
        "max_length": instance.meta.get("max_length", None),
        "max_sum_cost": instance.meta.get("max_sum_cost", None),
    }
    print(f"Metadata for {filename}: {metadata}")



    return instance, profile, metadata


def check_ejr(instance, profile, outcome, utility_func):
    """Check EJR violation for a given outcome and utility function."""
    (approvals, winning_set, costs, projects, budget) = convert_inputs_to_ejr_types(
        instance, profile, outcome
    )

    violation = find_ejr_violation_witness(
        approvals,
        winning_set,
        costs,
        projects,
        budget,
        utility_func,
        verbose=False,
    )
    return violation


def format_ejr_result(violation: EJRViolationResult, elapsed_time):
    """Format EJR violation result and timing into JSON structure."""
    return {
        "time": elapsed_time,
        "p_sets_checked": violation.p_sets_checked,
        "violation_found": len(violation.witness) != 0,
        "amount_of_violation": len(violation.witness),
        "violation_degree": (  # % of p_set util gotten
            None
            if len(violation.witness) == 0
            else float(min(map(lambda w: w.max_util, violation.witness)))
        ),
    }


def test_ejr_algorithms(filename: str):
    # Parse file to get instance, profile, and metadata
    instance, profile, metadata = parsefile(filename)

    # Get costs for utility functions
    projects = list(instance)
    costs = [p.cost for p in projects]

    # Define utility functions
    def card_utility_func(
        project_set: set[int] | frozenset[int], ballot: set[int]
    ) -> Numeric:
        return len(project_set & ballot)

    def cost_utility_func(
        project_set: set[int] | frozenset[int], ballot: set[int]
    ) -> Numeric:
        return sum(costs[p] for p in (project_set & ballot))

    # Define algorithms as list of {json_name: str, function: callable}
    algorithms = [
        {
            "json_name": "greedy[cost]",
            "function": lambda: greedy_utilitarian_welfare(
                instance, profile, sat_class=Cost_Sat, analytics=False
            ),
        },
        {
            "json_name": "greedy[card]",
            "function": lambda: greedy_utilitarian_welfare(
                instance, profile, sat_class=Cardinality_Sat, analytics=False
            ),
        },
        {
            "json_name": "MES[card]",
            "function": lambda: method_of_equal_shares(
                instance, profile, sat_class=Cardinality_Sat, analytics=False
            ),
        },
    ]

    # Create outcomes directory if it doesn't exist
    os.makedirs("outcomes", exist_ok=True)

    # Compute results for each algorithm
    result = {"metadata": metadata, "results": {}}

    for algo in algorithms:
        algo_name = algo["json_name"]

        # Time the algorithm execution
        start = time.time()
        outcome = algo["function"]()
        algo_time = time.time() - start

        # Test with cost utility function
        start = time.time()
        violation_cost = check_ejr(instance, profile, outcome, cost_utility_func)
        time_cost = time.time() - start

        # Test with card utility function
        start = time.time()
        violation_card = check_ejr(instance, profile, outcome, card_utility_func)
        time_card = time.time() - start

        result["results"][algo_name] = {
            "algorithm_time": algo_time,
            "cost": format_ejr_result(violation_cost, time_cost),
            "card": format_ejr_result(violation_card, time_card),
        }

        print(f"{algo_name} algorithm time: {algo_time:.4f}s")
        print(
            f"{algo_name}[cost] time: {time_cost:.4f}s, p-sets checked: {violation_cost.p_sets_checked}"
        )
        print(
            f"{algo_name}[card] time: {time_card:.4f}s, p-sets checked: {violation_card.p_sets_checked}"
        )

    # Save to JSON file
    output_filename = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join("outcomes", output_filename)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to {output_path}")


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
    filename = "Poland_Warszawa_2022.pb"
    print(f"\n--- {filename} ---")
    try:
        test_ejr_algorithms(filename)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    run_one()
