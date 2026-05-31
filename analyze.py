import io
import os
import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, List, Optional, Any, TextIO, TypeVar
import numpy as np
import sys

_T = TypeVar("_T")

# ---------------------------------------------------------------------------
# Analysis configs – determines which EJR-check types are included
# ---------------------------------------------------------------------------
ALL_EJR_TYPES: list[str] = ["ejr", "ejr_alpha", "ejr_x", "ejr_1"]
ALL_WITHOUT_EARLY_EJR_TYPES: list[str] = ["ejr", "ejr_x", "ejr_1"]

CONFIGS: dict[str, list[str]] = {
    "All": ALL_EJR_TYPES,
    "All_without_early": ALL_WITHOUT_EARLY_EJR_TYPES,
    "EJR_compare": ["ejr", "ejr_alpha"],
}

_EJR_LABELS: dict[str, str] = {
    "ejr": "EJR",
    "ejr_alpha": "EJR-$\\alpha$",
    "ejr_x": "EJR-X",
    "ejr_1": "EJR-1",
}


def escape_latex(s: str) -> str:
    """Escape special LaTeX characters in a string."""
    return s.replace("%", "\\%").replace("_", "\\_")


@dataclass
class ElectionRecord:
    """One algorithm's results within one election (one outcome JSON file)."""

    filename: str
    metadata: dict
    algo_name: str
    results: dict  # keys: "algo_stats" (algorithm_time, cost, card stats), "ejr", "ejr_x", "ejr_1", "ejr_alpha"

    @property
    def algo_stats(self) -> dict:
        return self.results.get("algo_stats", {})

    @property
    def algorithm_time(self) -> Optional[float]:
        return self.algo_stats.get("algorithm_time")


class OutcomeParser:
    """Unified parser for the outcome JSON files in the outcomes/ directory.

    Usage::

        parser = OutcomeParser()
        plot_lines = parser.plot_for_each_algo(
            lambda algo_name, records: PlotLine(...)
        )
    """

    def __init__(self, outcomes_dir: str = "./outcomes") -> None:
        self.records: List[ElectionRecord] = self._load(outcomes_dir)

    def _load(self, outcomes_dir: str) -> List[ElectionRecord]:
        records: List[ElectionRecord] = []
        if not os.path.exists(outcomes_dir):
            print(f"Outcomes directory {outcomes_dir} not found")
            return records
        for filename in sorted(
            f for f in os.listdir(outcomes_dir) if f.endswith(".json")
        ):
            filepath = os.path.join(outcomes_dir, filename)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                metadata = data.get("metadata", {})
                for algo_name, algo_results in data.get("results", {}).items():
                    records.append(
                        ElectionRecord(
                            filename=filename,
                            metadata=metadata,
                            algo_name=algo_name,
                            results=algo_results,
                        )
                    )
            except json.JSONDecodeError as e:
                print(f"Error parsing {filename}: {e}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")
        return records

    def plot_for_each_algo(
        self, fn: Callable[[str, List[ElectionRecord]], _T]
    ) -> List[_T]:
        """Call *fn(algo_name, records)* for every unique algorithm name.

        Records are grouped by ``algo_name`` (e.g. ``"mes[card]"``,
        ``"greedy[cost]"``, …) and *fn* is invoked once per group in
        alphabetical order.  The list of *fn*'s return values is returned,
        with ``None`` entries filtered out.
        """
        grouped: dict[str, List[ElectionRecord]] = defaultdict(list)
        for r in self.records:
            grouped[r.algo_name].append(r)
        return [
            result
            for algo, recs in sorted(grouped.items())
            if (result := fn(algo, recs)) is not None
        ]

    @staticmethod
    def bin_mean(coords: List[tuple], bucket_size: float) -> List[tuple]:
        """Average y-values of (x, y) pairs into x-buckets of width *bucket_size*.

        Each x is mapped to ``round(x / bucket_size) * bucket_size`` and the mean
        y within each bucket is returned as a sorted list of (x, mean_y) tuples.
        """
        bins: dict[float, list[float]] = defaultdict(list)
        for x, y in coords:
            key = round(x / bucket_size) * bucket_size
            bins[key].append(y)
        return sorted((k, float(np.mean(v))) for k, v in bins.items())

    @staticmethod
    def bin_median(coords: List[tuple], bucket_size: float) -> List[tuple]:
        """Median y-values of (x, y) pairs into x-buckets of width *bucket_size*.

        Each x is mapped to ``round(x / bucket_size) * bucket_size`` and the median
        y within each bucket is returned as a sorted list of (x, median_y) tuples.
        """
        bins: dict[float, list[float]] = defaultdict(list)
        for x, y in coords:
            key = round(x / bucket_size) * bucket_size
            bins[key].append(y)
        return sorted((k, float(np.median(v))) for k, v in bins.items())


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
    mark_size: Optional[float] = None
    only_marks: bool = False

    def to_latex(self) -> str:
        """Convert plot line to LaTeX format."""
        coords_str = "".join(f"({x},{y})" for x, y in self.coordinates)
        mark_str = f", mark={self.mark}" if self.mark is not None else ""
        mark_size_str = (
            f", mark size={self.mark_size}pt" if self.mark_size is not None else ""
        )
        return f"\\addplot[color={self.color}{mark_str}{mark_size_str}]coordinates {{ {coords_str}}};\\addlegendentry{{{escape_latex(self.legend_entry)}}}"


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
    ymin: Optional[float] = None
    ymax: Optional[float] = None
    only_marks: bool = False

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


@dataclass
class SubfigureGrid:
    """A LaTeX figure composed of subfigures arranged in a 2-column grid."""

    title: str
    caption: str
    graphs: List["Graph"]

    def print_raw(self, file: Optional[TextIO] = None) -> None:
        pass

    def print_latex(self, file: Optional[TextIO] = None) -> None:
        file = file or sys.stdout
        n = len(self.graphs)
        print(f"\n\n% {self.title}", file=file)
        print("\\begin{figure}[b]", file=file)
        print("\\centering", file=file)

        for i, graph in enumerate(self.graphs):
            lone_last = (i == n - 1) and (n % 2 == 1)
            if lone_last:
                print("\\begin{subfigure}{\\textwidth}", file=file)
                print("    \\raggedleft", file=file)
            else:
                print("\\begin{subfigure}{.5\\textwidth}", file=file)
                print("    \\centering", file=file)

            self._print_graph(graph, file)  # type: ignore[arg-type]

            if lone_last or i % 2 == 1:
                print("\\end{subfigure}", file=file)
            else:
                print("\\end{subfigure}%", file=file)

        short = escape_latex(self.title)
        print(f"\\caption[{short}]{{{escape_latex(self.caption)}}}", file=file)
        print("\\end{figure}", file=file)

    @staticmethod
    def _print_graph(graph: "Graph", file: TextIO) -> None:
        """Render a Graph as a tikzpicture with legend entries."""
        print("    \\begin{tikzpicture}", file=file)
        axis_options = [
            # f"title={{{escape_latex(graph.title)}}}", # no title, as is the caption
            f"xlabel={{{escape_latex(graph.xlabel)}}}",
            f"ylabel={{{escape_latex(graph.ylabel)}}}",
            f"ymajorgrids={str(graph.ymajorgrids).lower()}",
            f"grid style={graph.grid_style}",
            f"legend pos={graph.legend_pos}",
            *([f"ymin={graph.ymin}"] if graph.ymin is not None else []),
            *([f"ymax={graph.ymax}"] if graph.ymax is not None else []),
            *([f"x dir={graph.xdir}"] if graph.xdir is not None else []),
        ]
        print("    \\begin{axis}[" + ", ".join(axis_options) + "]", file=file)
        for pl in graph.plot_lines:
            coords_str = "".join(f"({x},{y})" for x, y in pl.coordinates)
            mark_opt = f", mark={pl.mark}" if pl.mark is not None else ""
            mark_size_opt = (
                f", mark size={pl.mark_size}pt" if pl.mark_size is not None else ""
            )
            only_marks_opt = "only marks, " if pl.only_marks else ""
            print(
                f"    \\addplot[{only_marks_opt}color={pl.color}{mark_opt}{mark_size_opt}]coordinates {{ {coords_str}}};",
                file=file,
            )
            print(f"    \\addlegendentry{{{escape_latex(pl.legend_entry)}}}", file=file)
        print("    \\end{axis}", file=file)
        print("    \\end{tikzpicture}", file=file)


def print_table(
    table: Table | Graph, as_latex: bool = False, file: Optional[TextIO] = None
) -> None:
    """Print a table using either raw or LaTeX format."""
    if as_latex:
        table.print_latex(file=file)
    else:
        table.print_raw(file=file)


def parse_outcomes_and_count_satisfying_properties(
    config: str = "All_without_early",
) -> List[Table]:
    """
    Parse all JSON files in the outcomes directory and count how many outcomes
    satisfy EJR, EJR-X, and EJR-1 (i.e., no violations found).

    Returns a list of Table objects, one for each property (EJR, EJR-X, EJR-1).
    """
    ejr_types = CONFIGS[config]
    parser = OutcomeParser()

    counters: dict = {"total_files": 0}
    for et in ejr_types:
        counters[et] = defaultdict(lambda: {"satisfied": 0, "violated": 0})

    seen_files: set[str] = set()
    for rec in parser.records:
        if rec.filename not in seen_files:
            seen_files.add(rec.filename)
            counters["total_files"] += 1

        for ejr_type in ejr_types:
            for utility in ["cost", "card"]:
                if utility in rec.results.get(ejr_type, {}):
                    result = rec.results[ejr_type][utility]
                    key = f"{rec.algo_name}[{utility}]"
                    if result.get("violation_found", False):
                        counters[ejr_type][key]["violated"] += 1
                    else:
                        counters[ejr_type][key]["satisfied"] += 1

    tables = []
    for prop_key in ejr_types:
        prop_name = _EJR_LABELS.get(prop_key, prop_key.upper())
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


def print_results_by_sat_function(
    config: str = "All_without_early",
) -> List[Table]:
    """
    Return results organized by EJR type and satisfaction function,
    showing how each algorithm performed.

    Returns a list of Table objects.
    """
    ejr_types = CONFIGS[config]
    parser = OutcomeParser()

    # Structure: {ejr_type: {utility: {algo_name: {satisfied: count, violated: count}}}}
    results_by_sat_func: dict = {}

    for rec in parser.records:
        for ejr_type in ejr_types:
            results_by_sat_func.setdefault(ejr_type, {})
            for utility in ["cost", "card"]:
                if utility in rec.results.get(ejr_type, {}):
                    results_by_sat_func[ejr_type].setdefault(utility, {})
                    results_by_sat_func[ejr_type][utility].setdefault(
                        rec.algo_name, {"satisfied": 0, "violated": 0}
                    )
                    if rec.results[ejr_type][utility].get("violation_found", False):
                        results_by_sat_func[ejr_type][utility][rec.algo_name][
                            "violated"
                        ] += 1
                    else:
                        results_by_sat_func[ejr_type][utility][rec.algo_name][
                            "satisfied"
                        ] += 1

    tables = []
    for ejr_type in ejr_types:
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
                        title=f"{_EJR_LABELS.get(ejr_type, ejr_type.upper())}[{utility}]",
                    )
                    tables.append(table)

    return tables


def print_results_by_algorithm(
    config: str = "All_without_early",
) -> List[Table]:
    """
    Return results organized by algorithm, showing satisfaction percentages
    for each EJR type and utility combination as columns.

    Returns a list containing a single Table object.
    """
    ejr_types = CONFIGS[config]
    parser = OutcomeParser()

    # Structure: {algo_name: {ejr_type: {utility: {satisfied, violated}}}}
    by_algo: dict = {}

    for rec in parser.records:
        by_algo.setdefault(rec.algo_name, {})
        for ejr_type in ejr_types:
            by_algo[rec.algo_name].setdefault(ejr_type, {})
            for utility in ["cost", "card"]:
                if utility in rec.results.get(ejr_type, {}):
                    by_algo[rec.algo_name][ejr_type].setdefault(
                        utility, {"satisfied": 0, "violated": 0}
                    )
                    if rec.results[ejr_type][utility].get("violation_found", False):
                        by_algo[rec.algo_name][ejr_type][utility]["violated"] += 1
                    else:
                        by_algo[rec.algo_name][ejr_type][utility]["satisfied"] += 1

    columns = [(et, u) for et in ejr_types for u in ["card", "cost"]]
    col_labels = {
        (et, u): f"{_EJR_LABELS.get(et, et.upper())}[{u}]"
        for et in ejr_types
        for u in ["card", "cost"]
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
    Analyze the 'satisfaction_degree' for EJR-cost and EJR-card per algorithm.

    Parameters:
    - ejr_type: "ejr", "ejr_1", or "ejr_x"

    Returns a list of Table objects, one for each utility (cost and card).
    """
    parser = OutcomeParser()

    violations_by_algo: dict = defaultdict(lambda: {"cost": [], "card": []})

    for rec in parser.records:
        for utility in ["cost", "card"]:
            if utility in rec.results.get(ejr_type, {}):
                degree = rec.results[ejr_type][utility].get("satisfaction_degree")
                if degree is not None:
                    violations_by_algo[rec.algo_name][utility].append(degree)

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
                title=f"Satisfaction Degree Analysis for {ejr_type.upper()}[{utility}]",
            )
            tables.append(table)

    return tables


def graph_vote_length_vs_p_sets_ejr_card() -> Optional[Graph]:
    """
    Create a graph showing the relationship between vote_length (x-axis) and
    p_sets visited for EJR[card] (y-axis), with one plot line per algorithm.

    Returns:
    - A Graph object that can be printed in LaTeX or raw format
    """
    parser = OutcomeParser()

    # Structure: {algorithm_name: [(vote_length, p_sets_checked), ...]}
    algorithm_data: dict[str, list] = defaultdict(list)

    for rec in parser.records:
        vote_length = rec.metadata.get("vote_length")
        if vote_length is None:
            continue
        ejr_card = rec.results.get("ejr", {}).get("card")
        if ejr_card is not None:
            p_sets_checked = ejr_card.get("p_sets_checked")
            if p_sets_checked is not None:
                algorithm_data[rec.algo_name].append((vote_length, p_sets_checked))

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
                # mark=mark,
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


def graph_min_satisfaction_degree_distribution_pr() -> List[Graph]:
    """
    For each utility (cost, card), and for each algorithm, collect the
    satisfaction_degree for EJR per election (using 1 when None).  Then, for
    x in [0.00, 0.01, ..., 1.00], compute the percentage of elections where
    the satisfaction degree is strictly greater than x (complementary CDF).

    Returns a list of two Graph objects: one for EJR[cost], one for EJR[card].
    """
    parser = OutcomeParser()

    # {utility: {algo_name: [satisfaction_degree_per_election, ...]}}
    data_by_utility: dict[str, dict[str, list[float]]] = {
        "cost": defaultdict(list),
        "card": defaultdict(list),
    }

    for rec in parser.records:
        for utility in ["cost", "card"]:
            ejr_util = rec.results.get("ejr_alpha", {}).get(utility)
            if ejr_util is not None:
                deg = ejr_util.get("satisfaction_degree")
                data_by_utility[utility][rec.algo_name].append(
                    deg if deg is not None else 1
                )

    x_points = [round(i * 0.01, 2) for i in range(1, 101)]  # 0.01 to 1.00
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
                title=f"EJR[{utility}] Satisfaction Degree Distribution",
                xlabel="Satisfaction Degree ($a$)",
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


def graph_unsat_voter_fraction_distribution_pr() -> List[Graph]:
    """
    For each utility (cost, card), and for each algorithm, collect the
    number_of_unsat_voters / number_of_voters ratio for EJR per election
    (using 0 when number_of_unsat_voters is None).  Then, for
    x in [0.00, 0.01, ..., 1.00], compute the percentage of elections where
    the ratio is >= x (complementary CDF).

    Returns a list of two Graph objects: one for EJR[cost], one for EJR[card].
    """
    parser = OutcomeParser()

    # {utility: {algo_name: [unsat_fraction_per_election, ...]}}
    data_by_utility: dict[str, dict[str, list[float]]] = {
        "cost": defaultdict(list),
        "card": defaultdict(list),
    }

    for rec in parser.records:
        n_voters = rec.metadata.get("number_of_voters")
        if not n_voters:
            continue
        for utility in ["cost", "card"]:
            ejr_util = rec.results.get("ejr_alpha", {}).get(utility)
            if ejr_util is not None:
                unsat = ejr_util.get("number_of_unsat_voters")
                fraction = (unsat / n_voters) if unsat is not None else 0.0
                data_by_utility[utility][rec.algo_name].append(fraction)

    x_points = [round(i * 0.01, 2) for i in range(0, 101)]  # 0.00 to 1.00
    colors = ["red", "blue", "green", "purple", "orange", "brown", "teal", "gray"]

    graphs = []
    for utility in ["cost", "card"]:
        algo_data = data_by_utility[utility]
        if not algo_data:
            continue

        plot_lines = []
        for i, algo_name in enumerate(sorted(algo_data.keys())):
            fractions = algo_data[algo_name]
            n = len(fractions)
            if n == 0:
                continue
            coordinates = [
                (x, round(sum(1 for v in fractions if v >= x) / n * 100, 2))
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
                title=f"EJR[{utility}] Unsatisfied Voter Fraction Distribution",
                xlabel="Fraction of Unsatisfied Voters ($r$)",
                ylabel="Elections with Fraction $\\ge r$ (\\%)",
                plot_lines=plot_lines,
                ymajorgrids=True,
                grid_style="dashed",
                xmode="linear",
                ymode="linear",
                legend_pos="outer north east",
            )
        )

    return graphs


def graph_vote_length_vs_satisfaction_degree_ejr() -> List[SubfigureGrid]:
    """
    For each utility (cost, card), create a SubfigureGrid figure containing
    one subfigure per algorithm. Each subfigure plots vote_length (x-axis)
    vs satisfaction_degree (y-axis), using 1 when satisfaction_degree is None.
    The legend is omitted; the algorithm name appears in the graph title.

    Returns a list of two SubfigureGrid objects: one for EJR[cost], one for EJR[card].
    """
    parser = OutcomeParser()

    # {algo_name: {utility: [(vote_length, satisfaction_degree), ...]}}
    data_by_algo: dict[str, dict[str, list[tuple]]] = defaultdict(
        lambda: {"cost": [], "card": []}
    )

    for rec in parser.records:
        vote_length = rec.metadata.get("vote_length")
        if vote_length is None:
            continue
        for utility in ["cost", "card"]:
            ejr_util = rec.results.get("ejr", {}).get(utility)
            if ejr_util is not None:
                deg = ejr_util.get("satisfaction_degree")
                data_by_algo[rec.algo_name][utility].append(
                    (vote_length, deg if deg is not None else 1)
                )

    figures = []
    for utility in ["cost", "card"]:
        graphs = []
        for algo_name in sorted(data_by_algo.keys()):
            coords = sorted(data_by_algo[algo_name][utility], key=lambda p: p[0])
            if not coords:
                continue

            # Group by rounded vote_length and compute mean satisfaction degree
            grouped: dict[int, list[float]] = defaultdict(list)
            for vl, deg in coords:
                grouped[round(vl)].append(deg)
            grouped_coords = sorted((k, float(np.mean(v))) for k, v in grouped.items())

            graphs.append(
                Graph(
                    title=algo_name,
                    xlabel="Vote Length",
                    ylabel="Satisfaction Degree ($a$)",
                    plot_lines=[
                        PlotLine(
                            color="black",
                            mark="*",
                            mark_size=1,
                            coordinates=coords,
                            legend_entry=algo_name,
                            only_marks=True,
                        ),
                        PlotLine(
                            color="red",
                            mark=None,
                            coordinates=grouped_coords,
                            legend_entry=f"{algo_name} (mean)",
                        ),
                    ],
                    ymajorgrids=True,
                    grid_style="dashed",
                    xmode="linear",
                    ymode="linear",
                    legend_pos="outer north east",
                    ymin=0,
                    ymax=1,
                )
            )

        if graphs:
            figures.append(
                SubfigureGrid(
                    title=f"EJR[{utility}] Satisfaction Degree vs Vote Length",
                    caption=(
                        f"EJR[{utility}] satisfaction degree as a function of vote length, "
                        f"shown per algorithm. A value of 1 indicates a full violation."
                    ),
                    graphs=graphs,
                )
            )

    return figures


def _graph_ejr_check_time(
    x_fn: Callable[["ElectionRecord", str, str], Optional[float]],
    x_label: str,
    bucket_size: float,
    title_suffix: str,
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """Shared implementation for EJR running-time graphs.

    Returns a single Graph with one line per EJR type.  Each line's y-values
    are the mean/median running time across all algorithms and both utilities
    (cost + card), bucketed by *bucket_size*.

    aggregation: "mean" or "median"
    """
    ejr_types = CONFIGS[config]
    parser = OutcomeParser()
    colors = ["red", "blue", "green", "purple", "orange", "brown", "teal", "gray"]
    bin_fn = (
        OutcomeParser.bin_median if aggregation == "median" else OutcomeParser.bin_mean
    )
    agg_label = aggregation.capitalize()

    # Collect all (x, t) pairs per ejr_type, pooled across algorithms & utilities
    data: dict[str, list[tuple]] = {et: [] for et in ejr_types}

    for rec in parser.records:
        for ejr_type in ejr_types:
            for utility in ["cost", "card"]:
                x = x_fn(rec, ejr_type, utility)
                t = rec.results.get(ejr_type, {}).get(utility, {}).get("time")
                if x is not None and t is not None:
                    data[ejr_type].append((x, t))

    plot_lines = []
    for i, ejr_type in enumerate(ejr_types):
        coords = bin_fn(data[ejr_type], bucket_size=bucket_size)
        if coords:
            plot_lines.append(
                PlotLine(
                    color=colors[i % len(colors)],
                    coordinates=coords,
                    legend_entry=_EJR_LABELS.get(ejr_type, ejr_type.upper()),
                )
            )

    if not plot_lines:
        return None
    return Graph(
        title=f"EJR Running Time vs {title_suffix} (bucket size={bucket_size})",
        xlabel=x_label,
        ylabel=f"{agg_label} Running Time (s)",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )


def graph_algorithm_time_vs_projects(
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs number_of_projects (bucket size 10)."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("number_of_projects"),
        x_label="Number of Projects",
        bucket_size=10,
        title_suffix="Number of Projects",
        config=config,
        aggregation=aggregation,
    )


def graph_algorithm_time_vs_projects_ejr_compare(
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs number_of_projects, comparing EJR and EJR-exit-early only (bucket size 10)."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("number_of_projects"),
        x_label="Number of Projects",
        bucket_size=10,
        title_suffix="Number of Projects (EJR vs EJR-exit-early)",
        config="EJR_compare",
        aggregation=aggregation,
    )


def graph_algorithm_time_vs_p_sets_checked(
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs p_sets_checked (bucket size 5)."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, et, u: rec.results.get(et, {})
        .get(u, {})
        .get("p_sets_checked"),
        x_label="P-Sets Checked",
        bucket_size=5,
        title_suffix="P-Sets Checked",
        config=config,
        aggregation=aggregation,
    )


def graph_algorithm_time_vs_vote_length(
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs vote_length (bucket size 1)."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("vote_length"),
        x_label="Vote Length",
        bucket_size=1,
        title_suffix="Vote Length",
        config=config,
        aggregation=aggregation,
    )


def graph_algorithm_time_vs_number_of_voters(
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs number_of_voters (bucket size 50)."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("number_of_voters"),
        x_label="Number of Voters",
        bucket_size=50,
        title_suffix="Number of Voters",
        config=config,
        aggregation=aggregation,
    )


def graph_algorithm_time_vs_vote_length_times_avg_cost(
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs vote_length * average_project_cost (bucket size 5)."""

    def x_fn(rec: "ElectionRecord", _et: str, _u: str) -> Optional[float]:
        vl = rec.metadata.get("vote_length")
        apc = rec.metadata.get("average_project_cost")
        if vl is None or apc is None:
            return None
        return vl * apc

    return _graph_ejr_check_time(
        x_fn=x_fn,
        x_label="Vote Length $\\times$ Avg Project Cost",
        bucket_size=5,
        title_suffix="Vote Length $\\times$ Avg Project Cost",
        config=config,
        aggregation=aggregation,
    )


def graph_algorithm_time_vs_budget_per_avg_cost(
    config: str = "All_without_early",
    aggregation: str = "mean",
) -> Optional[Graph]:
    """EJR running time vs budget / average_project_cost (bucket size 5)."""

    def x_fn(rec: "ElectionRecord", _et: str, _u: str) -> Optional[float]:
        budget = rec.metadata.get("budget_limit")
        apc = rec.metadata.get("average_project_cost")
        if budget is None or apc is None or apc == 0:
            return None
        return budget / apc

    return _graph_ejr_check_time(
        x_fn=x_fn,
        x_label="Budget / Avg Project Cost",
        bucket_size=1,
        title_suffix="Budget / Avg Project Cost",
        config=config,
        aggregation=aggregation,
    )


_LATEX_PREAMBLE = """\\documentclass[tikz,border=0pt]{standalone}
\\usepackage{tikz}
\\usepackage{booktabs}
\\usepackage{pgfplots}
\\pgfplotsset{compat=1.18}
\\usepackage{subcaption}
\\usepackage{caption}
\\pagestyle{empty}
\\begin{document}
"""

_LATEX_POSTAMBLE = "\n\\end{document}\n"


def _compile_snippet_to_pdf(snippet: str, name: str, pdf_dir: str) -> bool:
    """Wrap snippet in a full LaTeX document and compile to PDF.

    Returns True if the PDF was produced, False otherwise.
    On failure the .log file is kept for debugging.
    """
    tex_path = os.path.join(pdf_dir, f"{name}.tex")
    pdf_path = os.path.join(pdf_dir, f"{name}.pdf")

    with open(tex_path, "w") as f:
        f.write(_LATEX_PREAMBLE)
        f.write(snippet)
        f.write(_LATEX_POSTAMBLE)

    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", f"{name}.tex"],
        cwd=pdf_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if os.path.exists(pdf_path):
        for ext in (".aux", ".tex", ".log"):
            p = os.path.join(pdf_dir, f"{name}{ext}")
            if os.path.exists(p):
                os.remove(p)
        print(f"  -> 06_tex/pdf/{name}.pdf")
        return True
    else:
        for ext in (".aux", ".tex"):
            p = os.path.join(pdf_dir, f"{name}{ext}")
            if os.path.exists(p):
                os.remove(p)
        print(f"  WARNING: {name} failed — see 06_tex/pdf/{name}.log")
        return False


def _compile_subfigure_grid(
    grid: "SubfigureGrid",
    name: str,
    tex_out_path: str,
    pdf_dir: str,
    pdf_include_prefix: str = "06_tex/pdf",
) -> None:
    """Compile each graph in a SubfigureGrid to its own PDF, then write a
    .tex file that assembles them into a figure using subfigures with
    \\includegraphics.
    """
    n = len(grid.graphs)
    graph_names = []

    for j, graph in enumerate(grid.graphs):
        graph_name = f"{name}_graph_{j}"
        buf = io.StringIO()
        SubfigureGrid._print_graph(graph, buf)
        print(f"Compiling {graph_name}...")
        _compile_snippet_to_pdf(buf.getvalue(), graph_name, pdf_dir)
        graph_names.append(graph_name)

    with open(tex_out_path, "w") as f:
        f.write(f"\n\n% {grid.title}\n")
        f.write("\\begin{figure}[H]\n")
        f.write("\\centering\n")
        for i, (graph, graph_name) in enumerate(zip(grid.graphs, graph_names)):
            f.write("\\begin{subfigure}{.49\\textwidth}\n")
            f.write("    \\centering\n")
            f.write(
                f"    \\includegraphics[width=\\linewidth]{{{pdf_include_prefix}/{graph_name}.pdf}}\n"
            )
            f.write(f"    \\caption{{{escape_latex(graph.title)}}}\n")
            f.write(f"    \\label{{fig:{graph_name}}}\n")
            f.write("\\end{subfigure}\n")
        short = escape_latex(grid.title)
        f.write(f"\\caption{{{short}}}\n")
        f.write(f"\\label{{fig:{name}}}\n")
        f.write("\\end{figure}\n\n")


def print_stats(config: str = "All_without_early") -> None:
    """Main entry point for statistics generation.

    For each output item:
    - Tables and Graphs: compiled to a standalone PDF in tex/pdf/, then a .tex
      snippet with \\includegraphics is written to tex/.
    - SubfigureGrids: each constituent graph is compiled to its own PDF in
      tex/pdf/, and a .tex snippet assembling them into a figure with subfigures
      is written to tex/.
    """
    tex_dir = "06_tex"
    pdf_dir = os.path.join(tex_dir, "pdf")
    pdf_include_prefix = "06_tex/pdf"
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    functions = [
        # (
        #     "parse_outcomes_and_count_satisfying_properties",
        #     parse_outcomes_and_count_satisfying_properties(config),
        # ),
        # ("print_results_by_sat_function", print_results_by_sat_function(config)),
        ("print_results_by_algorithm", print_results_by_algorithm(config)),  # GOAT
        (
            "analyze_ejr_violations_by_utility",
            analyze_ejr_violations_by_utility(),
        ),  # a qq table
        (
            "graph_vote_length_vs_p_sets_ejr_card",
            [graph_vote_length_vs_p_sets_ejr_card()],
        ),
        (
            "graph_min_satisfaction_degree_distribution_pr",
            graph_min_satisfaction_degree_distribution_pr(),
        ),
        (
            "graph_unsat_voter_fraction_distribution_pr",
            graph_unsat_voter_fraction_distribution_pr(),
        ),
        (
            "graph_vote_length_vs_satisfaction_degree_ejr",
            graph_vote_length_vs_satisfaction_degree_ejr(),
        ),
        (
            "graph_algorithm_time_vs_projects",
            [graph_algorithm_time_vs_projects(config)],
        ),
        (
            "graph_algorithm_time_vs_p_sets_checked",
            [graph_algorithm_time_vs_p_sets_checked(config)],
        ),
        (
            "graph_algorithm_time_vs_vote_length",
            [graph_algorithm_time_vs_vote_length(config)],
        ),
        (
            "graph_algorithm_time_vs_number_of_voters",
            [graph_algorithm_time_vs_number_of_voters(config)],
        ),
        (
            "graph_algorithm_time_vs_vote_length_times_avg_cost",
            [graph_algorithm_time_vs_vote_length_times_avg_cost(config)],
        ),
        (
            "graph_algorithm_time_vs_projects_ejr_compare_median",
            [graph_algorithm_time_vs_projects_ejr_compare(aggregation="median")],
        ),
        (
            "graph_algorithm_time_vs_projects_ejr_compare_mean",
            [graph_algorithm_time_vs_projects_ejr_compare(aggregation="mean")],
        ),
        (
            "graph_algorithm_time_vs_budget_per_avg_cost_mean",
            [graph_algorithm_time_vs_budget_per_avg_cost(config)],
        ),
        (
            "graph_algorithm_time_vs_budget_per_avg_cost_median",
            [graph_algorithm_time_vs_budget_per_avg_cost(config, aggregation="median")],
        ),
    ]

    for func_name, items in functions:
        items = [x for x in items if x is not None]
        for i, item in enumerate(items):
            name = func_name if len(items) == 1 else f"{func_name}_{i}"
            tex_out_path = os.path.join(tex_dir, f"{name}.tex")

            if isinstance(item, SubfigureGrid):
                _compile_subfigure_grid(
                    item, name, tex_out_path, pdf_dir, pdf_include_prefix
                )
            elif isinstance(item, Table):
                with open(tex_out_path, "w") as f:
                    item.print_latex(file=f)
            else:
                buf = io.StringIO()
                item.print_latex(file=buf)
                print(f"Compiling {name}...")
                _compile_snippet_to_pdf(buf.getvalue(), name, pdf_dir)
                with open(tex_out_path, "w") as f:
                    f.write(f"\\includegraphics{{{pdf_include_prefix}/{name}.pdf}}\n")


if __name__ == "__main__":
    print_stats()
