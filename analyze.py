import os
import json
from collections import defaultdict


def parse_outcomes_and_count_satisfying_properties():
    """
    Parse all JSON files in the outcomes directory and count how many outcomes
    satisfy EJR, EJR-X, and EJR-1 (i.e., no violations found).
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return

    # Counters for each property across all outcomes, utilities, and algorithms
    counters = {
        "total_files": 0,
        "ejr": defaultdict(lambda: {"satisfied": 0, "violated": 0}),
        "ejr_1": defaultdict(lambda: {"satisfied": 0, "violated": 0}),
        "ejr_x": defaultdict(lambda: {"satisfied": 0, "violated": 0}),
    }

    # Get all JSON files in outcomes directory
    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

    print(f"Found {len(json_files)} outcome files\n")

    for filename in sorted(json_files):
        filepath = os.path.join(outcomes_dir, filename)

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            counters["total_files"] += 1

            # Parse results for each algorithm
            if "results" in data:
                for algo_name, algo_results in data["results"].items():
                    # Check EJR
                    for utility in ["cost", "card"]:
                        if utility in algo_results.get("ejr", {}):
                            ejr_result = algo_results["ejr"][utility]
                            key = f"{algo_name}[{utility}]"
                            if ejr_result.get("violation_found", False):
                                counters["ejr"][key]["violated"] += 1
                            else:
                                counters["ejr"][key]["satisfied"] += 1

                    # Check EJR-1
                    for utility in ["cost", "card"]:
                        if utility in algo_results.get("ejr_1", {}):
                            ejr1_result = algo_results["ejr_1"][utility]
                            key = f"{algo_name}[{utility}]"
                            if ejr1_result.get("violation_found", False):
                                counters["ejr_1"][key]["violated"] += 1
                            else:
                                counters["ejr_1"][key]["satisfied"] += 1

                    # Check EJR-X
                    for utility in ["cost", "card"]:
                        if utility in algo_results.get("ejr_x", {}):
                            ejrx_result = algo_results["ejr_x"][utility]
                            key = f"{algo_name}[{utility}]"
                            if ejrx_result.get("violation_found", False):
                                counters["ejr_x"][key]["violated"] += 1
                            else:
                                counters["ejr_x"][key]["satisfied"] += 1

        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Print results
    print("=" * 80)
    print("ANALYSIS OF OUTCOMES")
    print("=" * 80)
    print(f"\nTotal outcome files analyzed: {counters['total_files']}\n")

    def print_property_stats(prop_name, prop_data):
        print(f"\n{prop_name}:")
        print("-" * 80)
        total_satisfied = sum(v["satisfied"] for v in prop_data.values())
        total_violated = sum(v["violated"] for v in prop_data.values())

        for key in sorted(prop_data.keys()):
            satisfied = prop_data[key]["satisfied"]
            violated = prop_data[key]["violated"]
            total = satisfied + violated
            pct = (satisfied / total * 100) if total > 0 else 0
            print(
                f"  {key:25s}: {satisfied:4d} satisfied, {violated:4d} violated ({pct:5.1f}% satisfied)"
            )

        print(
            f"  {'TOTAL':25s}: {total_satisfied:4d} satisfied, {total_violated:4d} violated"
        )
        return total_satisfied, total_violated

    print_property_stats("EJR", counters["ejr"])
    print_property_stats("EJR-1", counters["ejr_1"])
    print_property_stats("EJR-X", counters["ejr_x"])

    print("\n" + "=" * 80)


def print_stats():
    """Main entry point for statistics generation."""
    parse_outcomes_and_count_satisfying_properties()


if __name__ == "__main__":
    print_stats()
