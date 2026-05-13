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

    def print_raw(self) -> None:
        """Print table in readable terminal format."""
        if self.title:
            print("\n" + "=" * 100)
            print(self.title)
            print("=" * 100)

        # Print headers
        print("  " + " ".join(f"{h:>12}" for h in self.headers))
        print("-" * (len(self.headers) * 14 + 2))

        # Print rows
        for row in self.rows:
            print("  " + " ".join(f"{str(v):>12}" for v in row))

        if self.title:
            print("=" * 100)

    def print_latex(self) -> None:
        """Print table in LaTeX format."""
        num_cols = len(self.headers)
        col_spec = "c" * num_cols

        print(f"\n\n% {self.title}" if self.title else "% Table")
        print("\\begin{table}[h]")
        print("\\centering")
        print(f"\\begin{{tabular}}{{{col_spec}}}")
        print("\\toprule")

        # Headers - escape % as \% and _ as \_
        def escape_latex(s: str) -> str:
            return s.replace("%", "\\%").replace("_", "\\_")

        header_row = " & ".join(escape_latex(str(h)) for h in self.headers) + " \\\\"
        print(header_row)

        print("\\midrule")

        # Data rows - escape % as \% and _ as \_
        for row in self.rows:
            row_cells = [escape_latex(str(cell)) for cell in row]
            print(" & ".join(row_cells) + " \\\\")

        print("\\bottomrule")
        print("\\end{tabular}")
        if self.title:
            print(f"\\caption{{{escape_latex(self.title)}}}")
        print("\\end{table}")


@dataclass
class PlotLine:
    """Represents a single plot line in a graph."""

    color: str
    mark: str
    coordinates: List[tuple]  # List of (x, y) tuples
    legend_entry: str

    def to_latex(self) -> str:
        """Convert plot line to LaTeX format."""
        coords_str = "".join(f"({x},{y})" for x, y in self.coordinates)
        return f"\\addplot[color={self.color}, mark={self.mark}]coordinates {{ {coords_str}}};\\addlegendentry{{{self.legend_entry}}}"


@dataclass
class Graph:
    """Represents a graph/plot with multiple lines."""

    title: str
    xlabel: str
    ylabel: str
    plot_lines: List[PlotLine]
    ymajorgrids: bool = True
    grid_style: str = "dashed"
    xmode: str = "log"
    log_basis_x: int = 2
    ymode: str = "log"
    log_basis_y: int = 2
    legend_pos: str = "outer north east"

    def print_raw(self) -> None:
        """Print raw format (does nothing for graphs)."""
        pass

    def print_latex(self) -> None:
        """Print graph in LaTeX TikZ format."""
        print("\\begin{tikzpicture}")

        # Build axis options
        axis_options = [
            f"title={{{self.title}}}",
            f"xlabel={{{self.xlabel}}}",
            f"ylabel={{{self.ylabel}}}",
            f"ymajorgrids={str(self.ymajorgrids).lower()}",
            f"grid style={self.grid_style}",
            # f"xmode={self.xmode}",
            # f"log basis x={self.log_basis_x}",
            # f"ymode={self.ymode}",
            # f"log basis y={self.log_basis_y}",
            f"legend pos = {self.legend_pos}",
        ]

        print("\\begin{axis}[" + ", ".join(axis_options) + "]")

        # Add all plot lines
        for plot_line in self.plot_lines:
            print(plot_line.to_latex())

        print("\\end{axis}")
        print("\\end{tikzpicture}")


def print_table(table: Table, as_latex: bool = False) -> None:
    """Print a table using either raw or LaTeX format."""
    if as_latex:
        table.print_latex()
    else:
        table.print_raw()


def parse_outcomes_and_count_satisfying_properties() -> List[Table]:
    """
    Parse all JSON files in the outcomes directory and count how many outcomes
    satisfy EJR, EJR-X, and EJR-1 (i.e., no violations found).

    Returns a list of Table objects, one for each property (EJR, EJR-X, EJR-1).
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return []

    # Counters for each property across all outcomes, utilities, and algorithms
    counters = {
        "total_files": 0,
        "ejr": defaultdict(lambda: {"satisfied": 0, "violated": 0}),
        "ejr_1": defaultdict(lambda: {"satisfied": 0, "violated": 0}),
        "ejr_x": defaultdict(lambda: {"satisfied": 0, "violated": 0}),
    }

    # Get all JSON files in outcomes directory
    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

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

    tables = []
    for prop_name, prop_key in [("EJR", "ejr"), ("EJR-X", "ejr_x"), ("EJR-1", "ejr_1")]:
        rows = []
        for key in sorted(counters[prop_key].keys()):
            satisfied = counters[prop_key][key]["satisfied"]
            violated = counters[prop_key][key]["violated"]
            total = satisfied + violated
            pct = (satisfied / total * 100) if total > 0 else 0
            rows.append([key, satisfied, violated, f"{pct:.1f}%"])

        total_satisfied = sum(v["satisfied"] for v in counters[prop_key].values())
        total_violated = sum(v["violated"] for v in counters[prop_key].values())
        total_all = total_satisfied + total_violated
        total_pct = (total_satisfied / total_all * 100) if total_all > 0 else 0
        rows.append(["TOTAL", total_satisfied, total_violated, f"{total_pct:.1f}%"])

        table = Table(
            headers=["Algorithm", "Satisfied", "Violated", "Satisfaction %"],
            rows=rows,
            title=f"Analysis of {prop_name}",
        )
        tables.append(table)

    return tables


def print_results_by_sat_function() -> List[Table]:
    """
    Return results organized by EJR type and satisfaction function,
    showing how each algorithm performed.

    Returns a list of Table objects.
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return []

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

    tables = []
    for ejr_type in ["ejr", "ejr_x", "ejr_1"]:
        if ejr_type in results_by_sat_func:
            for utility in ["cost", "card"]:
                if utility in results_by_sat_func[ejr_type]:
                    rows = []
                    algo_results = results_by_sat_func[ejr_type][utility]

                    for algo_name in sorted(algo_results.keys()):
                        satisfied = algo_results[algo_name]["satisfied"]
                        violated = algo_results[algo_name]["violated"]
                        total = satisfied + violated
                        pct = (satisfied / total * 100) if total > 0 else 0
                        rows.append([algo_name, satisfied, total, f"{pct:.1f}%"])

                    total_satisfied = sum(r["satisfied"] for r in algo_results.values())
                    total_violated = sum(r["violated"] for r in algo_results.values())
                    grand_total = total_satisfied + total_violated
                    pct_total = (
                        (total_satisfied / grand_total * 100) if grand_total > 0 else 0
                    )
                    rows.append(
                        ["TOTAL", total_satisfied, grand_total, f"{pct_total:.1f}%"]
                    )

                    table = Table(
                        headers=["Algorithm", "Satisfied", "Total", "Satisfaction %"],
                        rows=rows,
                        title=f"{ejr_type.upper()}[{utility}]",
                    )
                    tables.append(table)

    return tables


def print_results_by_algorithm() -> List[Table]:
    """
    Return results organized by algorithm, showing satisfaction percentages
    for each EJR type and utility combination as columns.

    Returns a list containing a single Table object.
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return []

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

    rows = []
    for algo_name in sorted(by_algo.keys()):
        row = [algo_name]
        for ejr_type, utility in columns:
            counts = by_algo[algo_name].get(ejr_type, {}).get(utility)
            if counts:
                total = counts["satisfied"] + counts["violated"]
                pct = (counts["satisfied"] / total * 100) if total > 0 else 0
                row.append(f"{pct:.1f}%")
            else:
                row.append("N/A")
        rows.append(row)

    headers = ["Algorithm"] + [col_labels[col] for col in columns]
    table = Table(headers=headers, rows=rows, title="Results by Algorithm")

    return [table]


def analyze_ejr_violations_by_utility(ejr_type="ejr") -> List[Table]:
    """
    Analyze the 'violation_degree' for EJR-cost and EJR-card per algorithm.

    Parameters:
    - ejr_type: "ejr", "ejr_1", or "ejr_x"

    Returns a list of Table objects, one for each utility (cost and card).
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return []

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

    tables = []
    for utility in ["cost", "card"]:
        rows = []
        for algo_name in sorted(violations_by_algo.keys()):
            violations = violations_by_algo[algo_name][utility]

            if len(violations) == 0:
                continue

            # Calculate statistics
            mean = np.mean(violations)
            median = np.median(violations)
            q1 = np.percentile(violations, 25)
            q3 = np.percentile(violations, 75)
            min_val = np.min(violations)
            max_val = np.max(violations)

            rows.append(
                [
                    algo_name,
                    len(violations),
                    f"{mean:.4f}",
                    f"{median:.4f}",
                    f"{q1:.4f}",
                    f"{q3:.4f}",
                    f"{min_val:.4f}",
                    f"{max_val:.4f}",
                ]
            )

        if rows:
            table = Table(
                headers=["Algorithm", "N", "Mean", "Median", "Q1", "Q3", "Min", "Max"],
                rows=rows,
                title=f"Violation Degree Analysis for {ejr_type.upper()}[{utility}]",
            )
            tables.append(table)

    return tables


def print_stats(printAsLatex: bool = False):
    """
    Main entry point for statistics generation.

    Parameters:
    - printAsLatex: If True, output LaTeX tables
    """
    all_tables = []

    # Collect all tables from analysis functions
    all_tables.extend(parse_outcomes_and_count_satisfying_properties())
    all_tables.extend(print_results_by_sat_function())
    all_tables.extend(print_results_by_algorithm())
    all_tables.extend(analyze_ejr_violations_by_utility())

    # Print all tables
    for table in all_tables:
        print_table(table, as_latex=printAsLatex)


if __name__ == "__main__":
    print_stats(True)
