from pabutools.election import (
    Cardinality_Sat,
    Instance,
    Profile,
    Cost_Sat,
    parse_pabulib,
)
from pabutools.rules import (
    greedy_utilitarian_welfare,
    sequential_phragmen,
    method_of_equal_shares,
)
import os
import time
import json


def parsefile(filename: str, verbose: bool = True):
    path = os.path.join("./elections/", filename)
    instance, profile = parse_pabulib(path)

    projects = sorted(instance, key=lambda p: str(p))
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
        "min_length": (instance.meta or {}).get("min_length", None),
        "max_length": (instance.meta or {}).get("max_length", None),
        "max_sum_cost": (instance.meta or {}).get("max_sum_cost", None),
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
            "json_name": "MES[cost]",
            "function": lambda: method_of_equal_shares(
                instance, profile, sat_class=Cost_Sat, analytics=False
            ),
        },
        {
            "json_name": "MES[card]",
            "function": lambda: method_of_equal_shares(
                instance, profile, sat_class=Cardinality_Sat, analytics=False
            ),
        },
        {
            "json_name": "seq_phragmen",
            "function": lambda: sequential_phragmen(instance, profile),
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

    os.makedirs("election_outcomes", exist_ok=True)
    output_filename = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join("election_outcomes", output_filename)

    with open(output_path, "w") as f:
        json.dump({"metadata": metadata, "winning_sets": winning_sets}, f, indent=2)

    if verbose:
        print(f"Winning sets saved to {output_path}")

    return output_path


def run_all(verbose: bool = False):
    elections_dir = "./elections/"
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
