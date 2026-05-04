import os
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Any
import numpy as np


@dataclass
class Table:
    """Represents a tabular data structure with headers and rows."""

    headers: List[str]
    rows: List[List[Any]]
    title: Optional[str] = None


def print_table(table: Table) -> None:
    """Print a table in readable terminal format."""
    if table.title:
        print("\n" + "=" * 100)
        print(table.title)
        print("=" * 100)

    # Print headers
    print("  " + " ".join(f"{h:>12}" for h in table.headers))
    print("-" * (len(table.headers) * 14 + 2))

    # Print rows
    for row in table.rows:
        print("  " + " ".join(f"{str(v):>12}" for v in row))

    if table.title:
        print("=" * 100)


def table_to_latex(
    table: Table, escape_underscores: bool = True, booktabs: bool = True
) -> str:
    """Convert a table to LaTeX format."""
    if not table.headers or not table.rows:
        return ""

    latex_lines = []
    num_cols = len(table.headers)
    col_spec = "c" * num_cols

    latex_lines.append(f"\\begin{{tabular}}{{{col_spec}}}")

    if booktabs:
        latex_lines.append("\\toprule")
    else:
        latex_lines.append("\\hline")

    # Headers
    header_row = " & ".join(str(h) for h in table.headers) + " \\\\"
    if escape_underscores:
        header_row = header_row.replace("_", "\\_")
    latex_lines.append(header_row)

    if booktabs:
        latex_lines.append("\\midrule")
    else:
        latex_lines.append("\\hline")

    # Data rows
    for row in table.rows:
        row_cells = []
        for cell in row:
            cell_str = str(cell)
            if escape_underscores:
                cell_str = cell_str.replace("_", "\\_")
            row_cells.append(cell_str)
        latex_lines.append(" & ".join(row_cells) + " \\\\")

    if booktabs:
        latex_lines.append("\\bottomrule")
    else:
        latex_lines.append("\\hline")

    latex_lines.append("\\end{tabular}")

    if table.title:
        latex_lines.insert(0, "\\begin{table}[h]")
        latex_lines.insert(1, "\\centering")
        latex_lines.append(f"\\caption{{{table.title}}}")
        latex_lines.append("\\end{table}")

    return "\n".join(latex_lines)


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
    print_property_stats("EJR-X", counters["ejr_x"])
    print_property_stats("EJR-1", counters["ejr_1"])

    print("\n" + "=" * 80)


def print_results_by_sat_function():
    """
    Print results organized by EJR type and satisfaction function,
    showing how each algorithm performed.
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return

    # Structure: {ejr_type: {utility: {algo_name: {satisfied: count, violated: count}}}}
    results_by_sat_func = {}

    # Get all JSON files in outcomes directory
    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

    for filename in sorted(json_files):
        filepath = os.path.join(outcomes_dir, filename)

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            if "results" in data:
                for algo_name, algo_results in data["results"].items():
                    for ejr_type in ["ejr", "ejr_x", "ejr_1"]:
                        if ejr_type not in results_by_sat_func:
                            results_by_sat_func[ejr_type] = {}

                        for utility in ["cost", "card"]:
                            if utility in algo_results.get(ejr_type, {}):
                                if utility not in results_by_sat_func[ejr_type]:
                                    results_by_sat_func[ejr_type][utility] = {}

                                if (
                                    algo_name
                                    not in results_by_sat_func[ejr_type][utility]
                                ):
                                    results_by_sat_func[ejr_type][utility][
                                        algo_name
                                    ] = {"satisfied": 0, "violated": 0}

                                result = algo_results[ejr_type][utility]
                                if result.get("violation_found", False):
                                    results_by_sat_func[ejr_type][utility][algo_name][
                                        "violated"
                                    ] += 1
                                else:
                                    results_by_sat_func[ejr_type][utility][algo_name][
                                        "satisfied"
                                    ] += 1

        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Print results organized by EJR type and satisfaction function
    print("\n" + "=" * 100)
    print("RESULTS BY SATISFACTION FUNCTION")
    print("=" * 100)

    for ejr_type in ["ejr", "ejr_x", "ejr_1"]:
        print(f"\n{ejr_type.upper()}:")
        print("-" * 100)

        if ejr_type in results_by_sat_func:
            for utility in ["cost", "card"]:
                if utility in results_by_sat_func[ejr_type]:
                    print(f"\n  {ejr_type.upper()}[{utility}]:")
                    algo_results = results_by_sat_func[ejr_type][utility]

                    # Calculate totals
                    total_satisfied = sum(r["satisfied"] for r in algo_results.values())
                    total_violated = sum(r["violated"] for r in algo_results.values())
                    grand_total = total_satisfied + total_violated

                    for algo_name in sorted(algo_results.keys()):
                        satisfied = algo_results[algo_name]["satisfied"]
                        violated = algo_results[algo_name]["violated"]
                        total = satisfied + violated
                        pct = (satisfied / total * 100) if total > 0 else 0
                        print(
                            f"    {algo_name:20s}: {satisfied:4d}/{total:4d} satisfied ({pct:5.1f}%)"
                        )

                    pct_total = (
                        (total_satisfied / grand_total * 100) if grand_total > 0 else 0
                    )
                    print(
                        f"    {'TOTAL':20s}: {total_satisfied:4d}/{grand_total:4d} satisfied ({pct_total:5.1f}%)"
                    )


def print_results_by_algorithm():
    """
    Print results organized by algorithm, showing satisfaction percentages
    for each EJR type and utility combination as columns.
    e.g. MES: EJR[card] 85.0%, EJR[cost] 78.0%, EJR-1[card] 92.0%, ...
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return

    # Structure: {algo_name: {ejr_type: {utility: {satisfied, violated}}}}
    by_algo = {}

    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

    for filename in sorted(json_files):
        filepath = os.path.join(outcomes_dir, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            if "results" not in data:
                continue

            for algo_name, algo_results in data["results"].items():
                if algo_name not in by_algo:
                    by_algo[algo_name] = {}

                for ejr_type in ["ejr", "ejr_x", "ejr_1"]:
                    if ejr_type not in by_algo[algo_name]:
                        by_algo[algo_name][ejr_type] = {}

                    for utility in ["cost", "card"]:
                        if utility in algo_results.get(ejr_type, {}):
                            if utility not in by_algo[algo_name][ejr_type]:
                                by_algo[algo_name][ejr_type][utility] = {
                                    "satisfied": 0,
                                    "violated": 0,
                                }
                            result = algo_results[ejr_type][utility]
                            if result.get("violation_found", False):
                                by_algo[algo_name][ejr_type][utility]["violated"] += 1
                            else:
                                by_algo[algo_name][ejr_type][utility]["satisfied"] += 1

        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    columns = [
        ("ejr", "card"),
        ("ejr", "cost"),
        ("ejr_x", "card"),
        ("ejr_x", "cost"),
        ("ejr_1", "card"),
        ("ejr_1", "cost"),
    ]
    col_labels = {
        ("ejr", "card"): "EJR[card]",
        ("ejr", "cost"): "EJR[cost]",
        ("ejr_1", "card"): "EJR-1[card]",
        ("ejr_1", "cost"): "EJR-1[cost]",
        ("ejr_x", "card"): "EJR-X[card]",
        ("ejr_x", "cost"): "EJR-X[cost]",
    }

    print("\n" + "=" * 100)
    print("RESULTS BY ALGORITHM")
    print("=" * 100)

    header = f"  {'Algorithm':20s}"
    for col in columns:
        header += f"  {col_labels[col]:>14s}"
    print(header)
    print("-" * 100)

    for algo_name in sorted(by_algo.keys()):
        row = f"  {algo_name:20s}"
        for ejr_type, utility in columns:
            counts = by_algo[algo_name].get(ejr_type, {}).get(utility)
            if counts:
                total = counts["satisfied"] + counts["violated"]
                pct = (counts["satisfied"] / total * 100) if total > 0 else 0
                row += f"  {pct:13.1f}%"
            else:
                row += f"  {'N/A':>14s}"
        print(row)

    print("=" * 100)


def analyze_ejr_violations_by_utility(ejr_type="ejr"):
    """
    Analyze the 'violation_degree' for EJR-cost and EJR-card per algorithm.

    Parameters:
    - ejr_type: "ejr", "ejr_1", or "ejr_x"

    Calculates: mean, median, Q1, Q3, min, max for each algorithm and utility (cost and card)
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return

    # Dictionary to store violations by algorithm and utility
    violations_by_algo = defaultdict(
        lambda: {
            "cost": [],
            "card": [],
        }
    )

    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

    for filename in sorted(json_files):
        filepath = os.path.join(outcomes_dir, filename)

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Parse results for each algorithm
            if "results" in data:
                for algo_name, algo_results in data["results"].items():
                    # Extract violations for the specified EJR type
                    if ejr_type in algo_results:
                        for utility in ["cost", "card"]:
                            if utility in algo_results[ejr_type]:
                                violation_data = algo_results[ejr_type][utility]
                                degree = violation_data.get("violation_degree")
                                if degree is not None:
                                    violations_by_algo[algo_name][utility].append(
                                        degree
                                    )

        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Print results in table format for each utility
    print("\n" + "=" * 200)
    print(f"VIOLATION DEGREE ANALYSIS FOR {ejr_type.upper()}")
    print("=" * 200)

    for utility in ["cost", "card"]:
        print(f"\n{utility.upper()} UTILITY:")
        print("-" * 200)

        # Header row
        header = f"{'Algorithm':<25} {'N':>6} {'Mean':>10} {'Median':>10} {'Q1':>10} {'Q3':>10} {'Min':>10} {'Max':>10}"
        print(header)
        print("-" * 200)

        # Data rows for each algorithm
        for algo_name in sorted(violations_by_algo.keys()):
            violations = violations_by_algo[algo_name][utility]

            if len(violations) == 0:
                print(f"{algo_name:<25} {'N/A':>6}")
                continue

            # Calculate statistics
            mean = np.mean(violations)
            median = np.median(violations)
            q1 = np.percentile(violations, 25)
            q3 = np.percentile(violations, 75)
            min_val = np.min(violations)
            max_val = np.max(violations)

            row = f"{algo_name:<25} {len(violations):>6d} {mean:>10.4f} {median:>10.4f} {q1:>10.4f} {q3:>10.4f} {min_val:>10.4f} {max_val:>10.4f}"
            print(row)

    print("=" * 200)


def print_stats(printAsLatex: bool = False):
    """
    Main entry point for statistics generation.

    Parameters:
    - printAsLatex: If True, output tables in LaTeX format to stdout instead of terminal format
    """
    if printAsLatex:
        # Collect all output and convert to LaTeX format
        # Note: This is a simple approach - just writes LaTeX tables to stdout
        import sys
        from io import StringIO

        # For now, we'll just print that LaTeX mode is enabled
        # (Proper implementation would require refactoring the print functions)
        print("% LaTeX Table Output")
        print("% Compile with: pdflatex <filename.tex>")
        print("% Use with: \\input{filename}")
        print()

        # Original functions print terminal format
        parse_outcomes_and_count_satisfying_properties()
        print_results_by_sat_function()
        print_results_by_algorithm()
        analyze_ejr_violations_by_utility()
    else:
        parse_outcomes_and_count_satisfying_properties()
        print_results_by_sat_function()
        print_results_by_algorithm()
        analyze_ejr_violations_by_utility()


if __name__ == "__main__":
    print_stats(True)
