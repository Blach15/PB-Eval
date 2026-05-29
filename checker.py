from pabutools.election import parse_pabulib
from pabutools.utils import Numeric
from typing import Iterable
import os
import time
import json
from ejr import (
    find_ejr_violation_witness,
    find_ejr_1_violation_witness,
    find_ejr_x_violation_witness,
)
from typess import EJRViolationResult


def _parse_election(filename: str):
    path = os.path.join("./elections/", filename)
    instance, profile = parse_pabulib(path)
    return instance, profile


def _load_cache(filename: str) -> dict:
    cache_path = os.path.join(
        "election_outcomes", os.path.splitext(filename)[0] + ".json"
    )
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"No cached winning sets found at {cache_path}. "
            "Run compute_winning_sets.py first."
        )
    with open(cache_path) as f:
        return json.load(f)


def _build_ejr_inputs(instance, profile):
    projects = sorted(instance, key=lambda p: str(p))
    proj_name_to_idx: dict[str, int] = {str(p): idx for idx, p in enumerate(projects)}
    approvals = [set(proj_name_to_idx[str(p)] for p in ballot) for ballot in profile]
    costs = [p.cost for p in projects]
    budget = instance.budget_limit
    return approvals, costs, projects, budget, proj_name_to_idx


def _format_ejr_result(violation: EJRViolationResult, elapsed_time: float) -> dict:
    return {
        "time": elapsed_time,
        "p_sets_checked": violation.p_sets_checked,
        "violation_found": len(violation.witness) != 0,
        "amount_of_violation": len(violation.witness),
        "satisfaction_degree": (
            None
            if len(violation.witness) == 0
            else (
                float(
                    min(w.max_util for w in violation.witness if w.max_util is not None)
                )
                if any(w.max_util is not None for w in violation.witness)
                else None
            )
        ),
    }


def test_ejr_algorithms(filename: str, verbose: bool = True) -> None:
    """Load precomputed winning sets and run all EJR checks, saving to outcomes/."""
    cache = _load_cache(filename)
    metadata = cache.get("metadata", {})
    winning_sets_cache: dict = cache["winning_sets"]

    instance, profile = _parse_election(filename)
    approvals, costs, projects, budget, proj_name_to_idx = _build_ejr_inputs(
        instance, profile
    )

    def card_utility_func(project_set: Iterable[int], ballot: set[int]) -> Numeric:
        return len([a for a in project_set if a in ballot])

    def cost_utility_func(project_set: Iterable[int], ballot: set[int]) -> Numeric:
        return sum(costs[p] for p in project_set if p in ballot)

    result: dict = {"metadata": metadata, "results": {}}

    for algo_name, ws_data in winning_sets_cache.items():
        algo_time = ws_data.get("time", None)
        winning_set: set[int] = set(
            proj_name_to_idx[pname] for pname in ws_data["projects"]
        )

        if verbose:
            print(
                f"  [{algo_name}] winning set size: {len(winning_set)}, "
                f"algo time (cached): {algo_time:.4f}s"
            )

        # EJR[cost]
        start = time.time()
        v_ejr_cost = find_ejr_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            cost_utility_func,
            exit_early=True,
            verbose=False,
        )
        t_ejr_cost = time.time() - start
        if verbose:
            print(
                f"    EJR[cost]   {t_ejr_cost:.4f}s  p-sets: {v_ejr_cost.p_sets_checked}  violation: {len(v_ejr_cost.witness) != 0}"
            )

        # EJR[card]
        start = time.time()
        v_ejr_card = find_ejr_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            card_utility_func,
            exit_early=True,
            verbose=False,
        )
        t_ejr_card = time.time() - start
        if verbose:
            print(
                f"    EJR[card]   {t_ejr_card:.4f}s  p-sets: {v_ejr_card.p_sets_checked}  violation: {len(v_ejr_card.witness) != 0}"
            )

        # EJR-x[cost]
        start = time.time()
        v_ejrx_cost = find_ejr_x_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            cost_utility_func,
            verbose=False,
        )
        t_ejrx_cost = time.time() - start
        if verbose:
            print(
                f"    EJR-x[cost] {t_ejrx_cost:.4f}s  p-sets: {v_ejrx_cost.p_sets_checked}  violation: {len(v_ejrx_cost.witness) != 0}"
            )

        # EJR-x[card]
        start = time.time()
        v_ejrx_card = find_ejr_x_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            card_utility_func,
            verbose=False,
        )
        t_ejrx_card = time.time() - start
        if verbose:
            print(
                f"    EJR-x[card] {t_ejrx_card:.4f}s  p-sets: {v_ejrx_card.p_sets_checked}  violation: {len(v_ejrx_card.witness) != 0}"
            )

        # EJR-1[cost]
        start = time.time()
        v_ejr1_cost = find_ejr_1_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            cost_utility_func,
            verbose=False,
        )
        t_ejr1_cost = time.time() - start
        if verbose:
            print(
                f"    EJR-1[cost] {t_ejr1_cost:.4f}s  p-sets: {v_ejr1_cost.p_sets_checked}  violation: {len(v_ejr1_cost.witness) != 0}"
            )

        # EJR-1[card]
        start = time.time()
        v_ejr1_card = find_ejr_1_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            card_utility_func,
            verbose=False,
        )
        t_ejr1_card = time.time() - start
        if verbose:
            print(
                f"    EJR-1[card] {t_ejr1_card:.4f}s  p-sets: {v_ejr1_card.p_sets_checked}  violation: {len(v_ejr1_card.witness) != 0}"
            )

        # EJR-alpha[cost]
        start = time.time()
        v_ejr_alpha_cost = find_ejr_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            cost_utility_func,
            verbose=False,
        )
        t_ejr_alpha_cost = time.time() - start
        if verbose:
            print(
                f"    EJR-alpha[cost] {t_ejr_alpha_cost:.4f}s  p-sets: {v_ejr_alpha_cost.p_sets_checked}  violation: {len(v_ejr_alpha_cost.witness) != 0}"
            )

        # EJR-alpha[card]
        start = time.time()
        v_ejr_alpha_card = find_ejr_violation_witness(
            approvals,
            winning_set,
            costs,
            projects,
            budget,
            card_utility_func,
            verbose=False,
        )
        t_ejr_alpha_card = time.time() - start
        if verbose:
            print(
                f"    EJR-alpha[card] {t_ejr_alpha_card:.4f}s  p-sets: {v_ejr_alpha_card.p_sets_checked}  violation: {len(v_ejr_alpha_card.witness) != 0}"
            )

        result["results"][algo_name] = {
            "algorithm_time": algo_time,
            "ejr": {
                "cost": _format_ejr_result(v_ejr_cost, t_ejr_cost),
                "card": _format_ejr_result(v_ejr_card, t_ejr_card),
            },
            "ejr_x": {
                "cost": _format_ejr_result(v_ejrx_cost, t_ejrx_cost),
                "card": _format_ejr_result(v_ejrx_card, t_ejrx_card),
            },
            "ejr_1": {
                "cost": _format_ejr_result(v_ejr1_cost, t_ejr1_cost),
                "card": _format_ejr_result(v_ejr1_card, t_ejr1_card),
            },
            "ejr_alpha": {
                "cost": _format_ejr_result(v_ejr_alpha_cost, t_ejr_alpha_cost),
                "card": _format_ejr_result(v_ejr_alpha_card, t_ejr_alpha_card),
            },
        }

    os.makedirs("outcomes", exist_ok=True)
    output_filename = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join("outcomes", output_filename)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    if verbose:
        print(f"Results saved to {output_path}")


def run_all(verbose: bool = False):
    cache_dir = "./election_outcomes/"
    if not os.path.isdir(cache_dir):
        print(
            "No election_outcomes/ directory found. Run compute_winning_sets.py first."
        )
        return

    files = sorted(
        f.replace(".json", ".pb") for f in os.listdir(cache_dir) if f.endswith(".json")
    )

    for filename in files:
        output_filename = os.path.splitext(filename)[0] + ".json"
        result_path = os.path.join("outcomes", output_filename)

        if os.path.exists(result_path):
            print(f"\n--- {filename} --- (skipped, result exists)")
            continue

        print(f"\n--- {filename} ---")
        try:
            test_ejr_algorithms(filename, verbose=verbose)
        except Exception as e:
            print(f"Error: {e}")


def run_one(verbose: bool = True):
    filename = "France_Toulouse_2022_6_-_Saint-Cyprien.pb"
    # output_filename = os.path.splitext(filename)[0] + ".json"
    # result_path = os.path.join("outcomes", output_filename)

    # if os.path.exists(result_path):
    #     print(f"\n--- {filename} --- (result already exists)")
    #     return

    print(f"\n--- {filename} ---")
    try:
        test_ejr_algorithms(filename, verbose=verbose)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    run_all()
