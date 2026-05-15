import os
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Any, TextIO
import numpy as np
import sys


def escape_latex(s: str) -> str:
    """Escape special LaTeX characters in a string."""
    return s.replace("%", "\\%").replace("_", "\\_")


@dataclass
class Table:
    """Represents a tabular data structure with headers and rows."""

    headers: List[str]
    rows: List[List[Any]]
    title: Optional[str] = None

    def print_raw(self, file: Optional[TextIO] = None) -> None:
        """Print table in readable terminal format."""
        file = file or sys.stdout
        if self.title:
            print("\n" + "=" * 100, file=file)
            print(self.title, file=file)
            print("=" * 100, file=file)

        # Print headers
        print("  " + " ".join(f"{h:>12}" for h in self.headers), file=file)
        print("-" * (len(self.headers) * 14 + 2), file=file)

        # Print rows
        for row in self.rows:
            print("  " + " ".join(f"{str(v):>12}" for v in row), file=file)

        if self.title:
            print("=" * 100, file=file)

    def print_latex(self, file: Optional[TextIO] = None) -> None:
        """Print table in LaTeX format."""
        file = file or sys.stdout
        num_cols = len(self.headers)
        col_spec = "c" * num_cols

        print(f"\n\n% {self.title}" if self.title else "% Table", file=file)
        print("\\begin{table}[h]", file=file)
        print("\\centering", file=file)
        print(f"\\begin{{tabular}}{{{col_spec}}}", file=file)
        print("\\toprule", file=file)

        header_row = " & ".join(escape_latex(str(h)) for h in self.headers) + " \\\\"
        print(header_row, file=file)

        print("\\midrule", file=file)

        # Data rows - escape % as \% and _ as \_
        for row in self.rows:
            row_cells = [escape_latex(str(cell)) for cell in row]
            print(" & ".join(row_cells) + " \\\\", file=file)

        print("\\bottomrule", file=file)
        print("\\end{tabular}", file=file)
        if self.title:
            print(f"\\caption{{{escape_latex(self.title)}}}", file=file)
        print("\\end{table}", file=file)


@dataclass
class PlotLine:
    """Represents a single plot line in a graph."""

    color: str
    coordinates: List[tuple]  # List of (x, y) tuples
    legend_entry: str
    mark: Optional[str] = None

    def to_latex(self) -> str:
        """Convert plot line to LaTeX format."""
        coords_str = "".join(f"({x},{y})" for x, y in self.coordinates)
        return f"\\addplot[color={self.color}{', mark=' + self.mark if self.mark is not None else ''}]coordinates {{ {coords_str}}};\\addlegendentry{{{escape_latex(self.legend_entry)}}}"


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
    xdir: Optional[str] = None

    def print_raw(self, file: Optional[TextIO] = None) -> None:
        """Print raw format (does nothing for graphs)."""
        pass

    def print_latex(self, file: Optional[TextIO] = None) -> None:
        """Print graph in LaTeX TikZ format."""
        file = file or sys.stdout
        print(f"\n\n% {self.title}" if self.title else "% Graph", file=file)
        print("\\begin{tikzpicture}", file=file)

        # Build axis options
        axis_options = [
            f"title={{{escape_latex(self.title)}}}",
            f"xlabel={{{escape_latex(self.xlabel)}}}",
            f"ylabel={{{escape_latex(self.ylabel)}}}",
            f"ymajorgrids={str(self.ymajorgrids).lower()}",
            f"grid style={self.grid_style}",
            # f"xmode={self.xmode}",
            # f"log basis x={self.log_basis_x}",
            # f"ymode={self.ymode}",
            # f"log basis y={self.log_basis_y}",
            f"legend pos = {self.legend_pos}",
            *([f"x dir={self.xdir}"] if self.xdir is not None else []),
        ]

        print("\\begin{axis}[" + ", ".join(axis_options) + "]", file=file)

        # Add all plot lines
        for plot_line in self.plot_lines:
            print(plot_line.to_latex(), file=file)

        print("\\end{axis}", file=file)
        print("\\end{tikzpicture}", file=file)


def print_table(
    table: Table | Graph, as_latex: bool = False, file: Optional[TextIO] = None
) -> None:
    """Print a table using either raw or LaTeX format."""
    if as_latex:
        table.print_latex(file=file)
    else:
        table.print_raw(file=file)


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


def graph_vote_length_vs_p_sets_ejr_card() -> Graph:
    """
    Create a graph showing the relationship between vote_length (x-axis) and
    p_sets visited for EJR[card] (y-axis), with one plot line per algorithm.

    Returns:
    - A Graph object that can be printed in LaTeX or raw format
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return None

    # Structure: {algorithm_name: [(vote_length, p_sets_checked), ...]}
    algorithm_data = defaultdict(list)

    # Get all JSON files in outcomes directory
    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

    for filename in sorted(json_files):
        filepath = os.path.join(outcomes_dir, filename)

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Extract vote_length from metadata
            vote_length = data.get("metadata", {}).get("vote_length")
            if vote_length is None:
                continue

            # Extract p_sets_checked for each algorithm's EJR[card]
            if "results" in data:
                for algo_name, algo_results in data["results"].items():
                    # Get EJR card utility results
                    if "ejr" in algo_results and "card" in algo_results["ejr"]:
                        p_sets_checked = algo_results["ejr"]["card"].get(
                            "p_sets_checked"
                        )
                        if p_sets_checked is not None:
                            algorithm_data[algo_name].append(
                                (vote_length, p_sets_checked)
                            )

        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Sort data by vote_length for each algorithm
    for algo_name in algorithm_data:
        algorithm_data[algo_name].sort(key=lambda x: x[0])

    # Define colors and marks for different algorithms
    colors = {
        "greedy[cost]": "red",
        "greedy[card]": "blue",
        "fjr[cost]": "green",
        "fjr[card]": "purple",
        "sequential_phragmen[cost]": "orange",
        "sequential_phragmen[card]": "brown",
        "method_of_equal_shares[cost]": "pink",
        "method_of_equal_shares[card]": "gray",
    }
    marks = {
        "greedy[cost]": "*",
        "greedy[card]": "o",
        "fjr[cost]": "square",
        "fjr[card]": "triangle",
        "sequential_phragmen[cost]": "diamond",
        "sequential_phragmen[card]": "pentagon",
        "method_of_equal_shares[cost]": "star",
        "method_of_equal_shares[card]": "asterisk",
    }

    # Create plot lines - only for MES[card]
    plot_lines = []
    if "MES[card]" in algorithm_data:
        coordinates = algorithm_data["MES[card]"]
        if coordinates:  # Only add if there's data
            color = colors.get("MES[card]", "black")
            mark = marks.get("MES[card]", "o")
            plot_line = PlotLine(
                color=color,
                mark=mark,
                coordinates=coordinates,
                legend_entry="MES[card]",
            )
            plot_lines.append(plot_line)

    # Create and return the graph
    graph = Graph(
        title="Vote Length vs P-Sets Visited (EJR[card])",
        xlabel="Vote Length",
        ylabel="P-Sets Checked",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )

    return graph


def graph_min_violation_degree_distribution_pr() -> List[Graph]:
    """
    For each utility (cost, card), and for each algorithm, collect the
    violation_degree for EJR per election (using 1 when None).  Then, for
    x in [0.00, 0.01, ..., 1.00], compute the percentage of elections where
    the violation degree is strictly greater than x (complementary CDF).

    Returns a list of two Graph objects: one for EJR[cost], one for EJR[card].
    """
    outcomes_dir = "./outcomes"

    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return []

    # {utility: {algo_name: [violation_degree_per_election, ...]}}
    data_by_utility: dict[str, dict[str, list[float]]] = {
        "cost": defaultdict(list),
        "card": defaultdict(list),
    }

    json_files = [f for f in os.listdir(outcomes_dir) if f.endswith(".json")]

    for filename in sorted(json_files):
        filepath = os.path.join(outcomes_dir, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            if "results" not in data:
                continue

            for algo_name, algo_results in data["results"].items():
                for utility in ["cost", "card"]:
                    ejr_util = algo_results.get("ejr", {}).get(utility)
                    if ejr_util is not None:
                        deg = ejr_util.get("violation_degree")
                        data_by_utility[utility][algo_name].append(
                            deg if deg is not None else 1
                        )

        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    x_points = [round(i * 0.01, 2) for i in range(101)]  # 0.00 to 1.00
    colors = ["red", "blue", "green", "purple", "orange", "brown", "teal", "gray"]

    graphs = []
    for utility in ["cost", "card"]:
        algo_violations = data_by_utility[utility]
        if not algo_violations:
            continue

        plot_lines = []
        for i, algo_name in enumerate(sorted(algo_violations.keys())):
            violations = algo_violations[algo_name]
            n = len(violations)
            if n == 0:
                continue
            coordinates = [
                (x, round(sum(1 for v in violations if v >= x) / n * 100, 2))
                for x in x_points
            ]
            plot_lines.append(
                PlotLine(
                    color=colors[i % len(colors)],
                    coordinates=coordinates,
                    legend_entry=algo_name,
                )
            )

        graphs.append(
            Graph(
                title=f"EJR[{utility}] Violation Degree Distribution",
                xlabel="Violation Degree ($a$)",
                ylabel="Elections with Violation $\\ge a$",
                plot_lines=plot_lines,
                ymajorgrids=True,
                grid_style="dashed",
                xmode="linear",
                ymode="linear",
                legend_pos="outer north east",
                xdir="reverse",
            )
        )

    return graphs


def print_stats(printAsLatex: bool = False, output_file: Optional[str] = None):
    """
    Main entry point for statistics generation.

    Parameters:
    - printAsLatex: If True, output LaTeX tables
    - output_file: If provided, write output to this file instead of stdout
    """
    all_tables = []

    # Collect all tables from analysis functions
    all_tables.extend(parse_outcomes_and_count_satisfying_properties())
    all_tables.extend(print_results_by_sat_function())
    all_tables.extend(print_results_by_algorithm())
    all_tables.extend(analyze_ejr_violations_by_utility())
    all_tables.append(graph_vote_length_vs_p_sets_ejr_card())
    all_tables.extend(graph_min_violation_degree_distribution_pr())

    # Open output file if specified
    output_fp = None
    if output_file:
        output_fp = open(output_file, "w")

    try:
        # Print all tables
        for table in all_tables:
            print_table(table, as_latex=printAsLatex, file=output_fp)
    finally:
        if output_fp:
            output_fp.close()


if __name__ == "__main__":
    print_stats(True, output_file="test_results.tex")
