import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pabutools.election import (
    Cardinality_Sat,
    Instance,
    Profile,
    Cost_Sat,
    parse_pabulib,
)
from pabutools.rules import (
    completion_by_rule_combination,
    greedy_utilitarian_welfare,
    sequential_phragmen,
    method_of_equal_shares,
)
import time
import json

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


def parsefile(filename: str, verbose: bool = True):
    path = os.path.join(_DATA_DIR, "elections", filename)
    instance, profile = parse_pabulib(path)

    projects = sorted(instance, key=lambda p: str(p))
    costs = [p.cost for p in projects]
    approvals = [set(ballot) for ballot in profile]

    average_project_cost = sum(costs) / len(projects)
    projects_to_voters_ratio = len(costs) / len(approvals)
    vote_length = sum(len(ballot) for ballot in approvals) / len(approvals)
    vote_length_to_projects_ratio = vote_length / len(projects)

    meta = instance.meta or {}
    metadata = {
        "number_of_voters": float(len(approvals)),
        "number_of_projects": float(len(projects)),
        "budget_limit": float(instance.budget_limit),
        "vote_length": float(vote_length),
        "average_project_cost": float(average_project_cost),
        "projects_to_voters_ratio": float(projects_to_voters_ratio),
        "vote_length_to_projects_ratio": float(vote_length_to_projects_ratio),
        "min_length": meta.get("min_length", None),
        "max_length": meta.get("max_length", None),
        "max_sum_cost": meta.get("max_sum_cost", None),
        "vote_type": meta.get("vote_type", None),
        "rule": meta.get("rule", None),
        "country": meta.get("country", None),
        "unit": meta.get("unit", None),
        "currency": meta.get("currency", None),
    }
    if verbose:
        print(f"Metadata for {filename}: {metadata}")

    return instance, profile, metadata


def compute_winning_sets(filename: str, verbose: bool = True) -> str:
    """
    Runs all allocation algorithms for the given election file and stores the
    resulting winning sets to election_outcomes/{election_name}.json.

    Returns the path of the written file.
    """
    instance, profile, metadata = parsefile(filename, verbose=verbose)

    algorithms = [
        {
            "json_name": "Greedy[cost]",
            "function": lambda: greedy_utilitarian_welfare(
                instance, profile, sat_class=Cost_Sat
            ),
        },
        {
            "json_name": "Greedy[card]",
            "function": lambda: greedy_utilitarian_welfare(
                instance, profile, sat_class=Cardinality_Sat
            ),
        },
        {
            "json_name": "MES[cost]",
            "function": lambda: method_of_equal_shares(
                instance, profile, sat_class=Cost_Sat
            ),
        },
        {
            "json_name": "MES[card]",
            "function": lambda: method_of_equal_shares(
                instance, profile, sat_class=Cardinality_Sat
            ),
        },
        {
            "json_name": "Phragmen",
            "function": lambda: sequential_phragmen(instance, profile),  # type: ignore - pabulib wrong type
        },
        {
            "json_name": "MES[cost]_Greedy[cost]]",
            "function": lambda: completion_by_rule_combination(
                instance,
                profile,
                [method_of_equal_shares, greedy_utilitarian_welfare],
                [{"sat_class": Cost_Sat}, {"sat_class": Cost_Sat}],
            ),
        },
        {
            "json_name": "MES[card]_Greedy[card]]",
            "function": lambda: completion_by_rule_combination(
                instance,
                profile,
                [method_of_equal_shares, greedy_utilitarian_welfare],
                [{"sat_class": Cardinality_Sat}, {"sat_class": Cardinality_Sat}],
            ),
        },
        {
            "json_name": "Phragmen_Greedy[card]]",
            "function": lambda: completion_by_rule_combination(
                instance,
                profile,
                [sequential_phragmen, greedy_utilitarian_welfare],
                [{}, {"sat_class": Cardinality_Sat}],
            ),
        },
        {
            "json_name": "Phragmen_Greedy[cost]]",
            "function": lambda: completion_by_rule_combination(
                instance,
                profile,
                [sequential_phragmen, greedy_utilitarian_welfare],
                [{}, {"sat_class": Cost_Sat}],
            ),
        },
    ]

    winning_sets: dict = {}
    for algo in algorithms:
        algo_name = algo["json_name"]
        start = time.time()
        outcome = algo["function"]()
        elapsed = time.time() - start

        project_names = [str(p) for p in outcome]

        if verbose:
            print(
                f"  {algo_name}: {len(project_names)} projects selected in {elapsed:.4f}s"
            )

        winning_sets[algo_name] = {
            "projects": project_names,
            "time": elapsed,
        }

    os.makedirs(os.path.join(_DATA_DIR, "election_outcomes"), exist_ok=True)
    output_filename = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join(_DATA_DIR, "election_outcomes", output_filename)

    with open(output_path, "w") as f:
        json.dump({"metadata": metadata, "winning_sets": winning_sets}, f, indent=2)

    if verbose:
        print(f"Winning sets saved to {output_path}")

    return output_path


def run_all(verbose: bool = False):
    elections_dir = os.path.join(_DATA_DIR, "elections")
    files = sorted(f for f in os.listdir(elections_dir) if f.endswith(".pb"))

    for filename in files:
        print(f"\n--- {filename} ---")
        try:
            compute_winning_sets(filename, verbose=verbose)
        except Exception as e:
            print(f"Error processing {filename}: {e}")


def run_one(verbose: bool = True):
    filename = "Poland_Warszawa_2022.pb"
    print(f"\n--- {filename} ---")
    try:
        compute_winning_sets(filename, verbose=verbose)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    run_all()
