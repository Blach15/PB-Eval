import io
import os
import json
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, List, Optional, Any, TextIO, TypeVar
import numpy as np
import sys

_T = TypeVar("_T")

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")

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

_UTIL_LABELS: dict[str, str] = {
    "card": "$\\mu^{\\#}$",
    "cost": "$\\mu^c$",
}

_EJR_LABELS: dict[str, str] = {
    "ejr": "EJR",
    "ejr_alpha": "EJR-$\\phi$",
    "ejr_x": "EJR-x",
    "ejr_1": "EJR-1",
}

_ALGO_LABELS: dict[str, str] = {
    "Greedy[card]": f"\\text{{Greedy[{_UTIL_LABELS['card']}]}}",
    "Greedy[cost]": f"\\text{{Greedy[{_UTIL_LABELS['cost']}]}}",
    "MES[card]": f"\\text{{MES[{_UTIL_LABELS['card']}]}}",
    "MES[cost]": f"\\text{{MES[{_UTIL_LABELS['cost']}]}}",
    "Phragmen": "\\text{Seq-Phragmén}",
}
_ALGO_LABELS.update(
    {
        "MES[card]_Greedy[card]]": f"${_ALGO_LABELS['MES[card]']}_"
        + "\\text{"
        + f"{_UTIL_LABELS['card']}"
        + "}$",
        "MES[cost]_Greedy[cost]]": f"${_ALGO_LABELS['MES[cost]']}_"
        + "\\text{"
        + f"{_UTIL_LABELS['cost']}"
        + "}$",
        "Phragmen_Greedy[card]]": f"${_ALGO_LABELS['Phragmen']}_"
        + "\\text{"
        + f"{_UTIL_LABELS['card']}"
        + "}$",
        "Phragmen_Greedy[cost]]": f"${_ALGO_LABELS['Phragmen']}_"
        + "\\text{"
        + f"{_UTIL_LABELS['cost']}"
        + "}$",
    }
)


_ALGO_ORDER: list[str] = [
    "Greedy[card]",
    "Greedy[cost]",
    "MES[card]",
    "MES[cost]",
    "Phragmen",
    "MES[card]_Greedy[card]]",
    "MES[cost]_Greedy[cost]]",
    "Phragmen_Greedy[card]]",
    "Phragmen_Greedy[cost]]",
]

_ALGO_COLORS: dict[str, str] = {
    "Greedy[card]": "red",
    "Greedy[cost]": "blue",
    "MES[card]": "green",
    "MES[cost]": "black",
    "Phragmen": "orange",
    "MES[card]_Greedy[card]]": "teal",
    "MES[cost]_Greedy[cost]]": "brown",
    "Phragmen_Greedy[card]]": "olive",
    "Phragmen_Greedy[cost]]": "gray",
}

_EJR_COLORS: dict[str, str] = {
    "ejr": "red",
    "ejr_alpha": "teal",
    "ejr_x": "green",
    "ejr_1": "blue",
}


def get_algo_color(algo_name: str) -> str:
    """Return the canonical color for an algorithm. Raises KeyError if unmapped."""
    if algo_name not in _ALGO_COLORS:
        raise KeyError(
            f"No color configured for algorithm {algo_name!r}. Add it to _ALGO_COLORS."
        )
    return _ALGO_COLORS[algo_name]


def get_ejr_color(ejr_type: str) -> str:
    """Return the canonical color for an EJR type. Raises KeyError if unmapped."""
    if ejr_type not in _EJR_COLORS:
        raise KeyError(
            f"No color configured for EJR type {ejr_type!r}. Add it to _EJR_COLORS."
        )
    return _EJR_COLORS[ejr_type]


def algo_sort_key(algo_name: str) -> tuple:
    """Sort key that respects _ALGO_ORDER; unknown names sort last alphabetically."""
    try:
        return (0, _ALGO_ORDER.index(algo_name), "")
    except ValueError:
        return (1, 0, algo_name)


def get_algo_label(algo_name: str) -> str:
    """Get the display label for an algorithm name.

    Returns the mapped label from _ALGO_LABELS if it exists,
    otherwise returns the algorithm name unchanged.
    """
    return _ALGO_LABELS.get(algo_name, algo_name)


def escape_latex(s: str) -> str:
    """Escape special LaTeX characters in a string."""
    return s


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

    def __init__(self, outcomes_dir: str = os.path.join(_DATA_DIR, "outcomes")) -> None:
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
            for algo, recs in sorted(
                grouped.items(), key=lambda kv: algo_sort_key(kv[0])
            )
            if (result := fn(algo, recs)) is not None
        ]

    @staticmethod
    def moving_average(coords: List[tuple]) -> List[tuple]:
        """Cumulative moving average over sorted (x, y) pairs.

        Points are sorted by x. For each distinct x value, the y-value is
        the mean of *all* y values seen so far (up to and including that x).
        """
        if not coords:
            return []
        sorted_coords = sorted(coords, key=lambda p: p[0])
        result = []
        cumsum = 0.0
        count = 0
        i = 0
        while i < len(sorted_coords):
            x = sorted_coords[i][0]
            j = i
            while j < len(sorted_coords) and sorted_coords[j][0] == x:
                cumsum += sorted_coords[j][1]
                count += 1
                j += 1
            result.append((x, cumsum / count))
            i = j
        return result


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

    def print_latex(
        self, file: Optional[TextIO] = None, label: Optional[str] = None
    ) -> None:
        """Print table in LaTeX format."""
        file = file or sys.stdout
        num_cols = len(self.headers)
        col_spec = "c" * num_cols

        print(f"\n\n% {self.title}" if self.title else "% Table", file=file)
        print("\\begin{table}[H]", file=file)
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
        if label:
            print(f"\\label{{tab:{label}}}", file=file)
        print("\\end{table}", file=file)


@dataclass
class PlotLine:
    """Represents a single plot line in a graph."""

    color: str
    coordinates: List[tuple]  # List of (x, y) tuples
    legend_entry: Optional[str] = None
    mark: Optional[str] = None
    mark_size: Optional[float] = None
    only_marks: bool = False
    style: Optional[str] = None  # e.g., "dashed", "dotted", etc.

    def to_latex(self) -> str:
        """Convert plot line to LaTeX format."""
        coords_str = "".join(f"({x},{y})" for x, y in self.coordinates)
        only_marks_str = "only marks, " if self.only_marks else ""
        mark_str = f", mark={self.mark}" if self.mark is not None else ""
        mark_size_str = (
            f", mark size={self.mark_size}pt" if self.mark_size is not None else ""
        )
        style_str = f", {self.style}" if self.style is not None else ""
        legend_str = (
            f"\\addlegendentry{{{escape_latex(self.legend_entry)}}}"
            if self.legend_entry is not None
            else ""
        )
        return f"\\addplot[{only_marks_str}color={self.color}{mark_str}{mark_size_str}{style_str}]coordinates {{ {coords_str}}};{legend_str}"


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

    def print_latex(
        self, file: Optional[TextIO] = None, include_title: bool = True
    ) -> None:
        """Print graph in LaTeX TikZ format."""
        file = file or sys.stdout
        print(f"\n\n% {self.title}" if self.title else "% Graph", file=file)
        print("\\begin{tikzpicture}", file=file)

        # Build axis options
        axis_options = [
            *(
                [f"title={{{escape_latex(self.title)}}}"]
                if include_title and self.title
                else []
            ),
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
    name: Optional[str] = None

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

            print(f"    \\caption{{{escape_latex(graph.title)}}}", file=file)
            if self.name:
                print(f"    \\label{{fig:{self.name}_graph_{i}}}", file=file)

            if lone_last or i % 2 == 1:
                print("\\end{subfigure}", file=file)
            else:
                print("\\end{subfigure}%", file=file)

        short = escape_latex(self.title)
        print(f"\\caption[{short}]{{{escape_latex(self.caption)}}}", file=file)
        if self.name:
            print(f"\\label{{fig:{self.name}}}", file=file)
        print("\\end{figure}", file=file)

    @staticmethod
    def _print_graph(
        graph: "Graph",
        file: TextIO,
        height: Optional[str] = None,
        width: Optional[str] = None,
    ) -> None:
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
            *([f"width={width}"] if width is not None else []),
            *([f"height={height}"] if height is not None else []),
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
            if pl.legend_entry is not None:
                print(
                    f"    \\addlegendentry{{{escape_latex(pl.legend_entry)}}}",
                    file=file,
                )
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
            rows.append([key, satisfied, violated, f"{pct:.1f}\\%"])

        total_satisfied = sum(v["satisfied"] for v in counters[prop_key].values())
        total_violated = sum(v["violated"] for v in counters[prop_key].values())
        total_all = total_satisfied + total_violated
        total_pct = (total_satisfied / total_all * 100) if total_all > 0 else 0
        rows.append(["TOTAL", total_satisfied, total_violated, f"{total_pct:.1f}\\%"])

        table = Table(
            headers=["Algorithm", "Satisfied", "Violated", "Satisfaction \\%"],
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

                    for algo_name in sorted(algo_results.keys(), key=algo_sort_key):
                        satisfied = algo_results[algo_name]["satisfied"]
                        violated = algo_results[algo_name]["violated"]
                        total = satisfied + violated
                        pct = (satisfied / total * 100) if total > 0 else 0
                        rows.append(
                            [
                                get_algo_label(algo_name),
                                satisfied,
                                total,
                                f"{pct:.1f}\\%",
                            ]
                        )

                    total_satisfied = sum(r["satisfied"] for r in algo_results.values())
                    total_violated = sum(r["violated"] for r in algo_results.values())
                    grand_total = total_satisfied + total_violated
                    pct_total = (
                        (total_satisfied / grand_total * 100) if grand_total > 0 else 0
                    )
                    rows.append(
                        ["TOTAL", total_satisfied, grand_total, f"{pct_total:.1f}\\%"]
                    )

                    table = Table(
                        headers=["Algorithm", "Satisfied", "Total", "Satisfaction \\%"],
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

    _excluded = {("ejr_x", "card"), ("ejr_1", "card")}
    columns = [
        (et, u)
        for et in ejr_types
        for u in ["card", "cost"]
        if (et, u) not in _excluded
    ]
    col_labels = {
        (et, u): f"{_UTIL_LABELS.get(u, u)}-{_EJR_LABELS.get(et, et.upper())}"
        for et in ejr_types
        for u in ["card", "cost"]
    }

    rows = []
    for algo_name in sorted(by_algo.keys(), key=algo_sort_key):
        row = [get_algo_label(algo_name)]
        for ejr_type, utility in columns:
            counts = by_algo[algo_name].get(ejr_type, {}).get(utility)
            if counts:
                total = counts["satisfied"] + counts["violated"]
                pct = (counts["satisfied"] / total * 100) if total > 0 else 0
                row.append(f"{pct:.1f}\\%")
            else:
                row.append("N/A")
        rows.append(row)

    headers = ["Algorithm"] + [col_labels[col] for col in columns]
    table = Table(headers=headers, rows=rows, title="Results by Algorithm")

    return [table]


def analyze_utility_comparison() -> Table:
    """
    Compare utility (cost efficiency) and budget usage across algorithms.

    For each election, computes:
    - Card: algo_stats[card][util_mean] / Greedy[card]'s algo_stats[card][util_mean]
    - Cost: algo_stats[cost][util_mean] / Greedy[cost]'s algo_stats[cost][util_mean]
    - Budget Usage: winning_set_cost / budget_limit

    Then aggregates across elections by taking the mean per algorithm.

    Returns a Table with columns: Algorithm, Card (relative), Cost (relative), Budget Usage.
    """
    parser = OutcomeParser()

    # Structure: {filename: {algo_name: {utility: util_mean}}}
    election_data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    # Collect util_mean per election, algorithm, and utility
    for rec in parser.records:
        for utility in ["card", "cost"]:
            # algo_stats has structure like {"card": {"util_mean": X}, "cost": {...}}
            util_mean = rec.algo_stats.get(utility, {}).get("util_mean")
            if util_mean is not None:
                election_data[rec.filename][rec.algo_name][utility] = util_mean

    # Structure: {algo_name: {utility: [relative_scores_per_election, ...]}}
    relative_scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"card": [], "cost": []}
    )

    # Structure: {algo_name: [budget_usage_ratios, ...]}
    budget_usage: dict[str, list[float]] = defaultdict(list)

    # Compute relative scores per election
    for filename, algo_utils in election_data.items():
        # Use capitalized names: Greedy[card], Greedy[cost]
        greedy_card_util = algo_utils.get("Greedy[card]", {}).get("card")
        greedy_cost_util = algo_utils.get("Greedy[cost]", {}).get("cost")

        if greedy_card_util is not None or greedy_cost_util is not None:
            for algo_name, utilities in algo_utils.items():
                card_util = utilities.get("card")
                cost_util = utilities.get("cost")

                if card_util is not None and greedy_card_util is not None:
                    relative_scores[algo_name]["card"].append(
                        card_util / greedy_card_util
                    )
                if cost_util is not None and greedy_cost_util is not None:
                    relative_scores[algo_name]["cost"].append(
                        cost_util / greedy_cost_util
                    )

    # Structure: {algo_name: [algorithm_times, ...]}
    algo_times: dict[str, list[float]] = defaultdict(list)

    # Collect budget usage and running time per election
    for rec in parser.records:
        budget_limit = rec.metadata.get("budget_limit")
        winning_set_cost = rec.algo_stats.get("winning_set_cost")

        if (
            budget_limit is not None
            and winning_set_cost is not None
            and budget_limit > 0
        ):
            usage_ratio = winning_set_cost / budget_limit
            budget_usage[rec.algo_name].append(usage_ratio)

        t = rec.algorithm_time
        if t is not None:
            algo_times[rec.algo_name].append(t)

    # Build table rows
    rows = []
    for algo_name in sorted(relative_scores.keys(), key=algo_sort_key):
        card_rels = relative_scores[algo_name]["card"]
        cost_rels = relative_scores[algo_name]["cost"]
        usage_ratios = budget_usage.get(algo_name, [])
        times = algo_times.get(algo_name, [])

        card_mean = f"{round(100*np.mean(card_rels), 1)}" if card_rels else "N/A"
        cost_mean = f"{round(100*np.mean(cost_rels), 1)}" if cost_rels else "N/A"
        budget_mean = (
            f"{round(100*np.mean(usage_ratios), 1)}" if usage_ratios else "N/A"
        )
        time_mean = f"{np.mean(times):.4f}" if times else "N/A"

        rows.append([get_algo_label(algo_name), card_mean, cost_mean, budget_mean, time_mean])

    return Table(
        headers=[
            "Algorithm",
            "$\\mu^{\\#}_{\\text{rel.}} (\\%)$",
            "$\\mu^{c}_{\\text{rel.}} (\\%)$",
            "Budget Usage (\\%)",
            "Avg Running Time (s)",
        ],
        rows=rows,
        title="Average Utility Comparison and Budget Usage by Algorithm",
    )


def analyze_ejr_violations_by_utility(ejr_type="ejr_alpha") -> List[Table]:
    """
    Analyze the 'violation_degree' (1 - satisfaction_degree) for EJR-cost and EJR-card per algorithm.

    Parameters:
    - ejr_type: "ejr", "ejr_1", or "ejr_x"

    Returns a list of Table objects, one for each utility (cost and card).
    """
    parser = OutcomeParser()

    violations_by_algo: dict = defaultdict(lambda: {"cost": [], "card": []})

    for rec in parser.records:
        for utility in ["cost", "card"]:
            if utility in rec.results.get(ejr_type, {}):
                raw = rec.results[ejr_type][utility].get("satisfaction_degree")
                if raw is not None:
                    violations_by_algo[rec.algo_name][utility].append(1 - raw)

    tables = []
    for utility in ["cost", "card"]:
        rows = []
        for algo_name in sorted(violations_by_algo.keys(), key=algo_sort_key):
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
                    get_algo_label(algo_name),
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
                headers=["Algorithm", "$\\#_{V}$", "Mean", "Median", "Q1", "Q3", "Min", "Max"],
                rows=rows,
                title=f"Violation Degree Analysis for {_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS.get(ejr_type, ejr_type.upper())}",
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
        title=f"Vote Length vs T-Cohesive Sets Checked ({_UTIL_LABELS['card']}-{_EJR_LABELS['ejr']})",
        xlabel="Vote Length",
        ylabel="T-Cohesive Sets Checked",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )

    return graph


def graph_exclusion_ratio_distribution() -> List[Graph]:
    """
    For each algorithm, collect the exclusion_ratio (no_util_voters / number_of_voters)
    across all elections. Then compute a CDF: for each x in [0.00, 0.01, ..., 1.00],
    compute the percentage of elections where exclusion_ratio <= x.

    Returns a list containing one Graph with one line per algorithm showing the CDF of exclusion ratios.
    """
    parser = OutcomeParser()

    # Structure: {algo_name: [exclusion_ratio_per_election, ...]}
    data_by_algo: dict[str, list[float]] = defaultdict(list)

    for rec in parser.records:
        n_voters = rec.metadata.get("number_of_voters")
        no_util_voters = rec.algo_stats.get("no_util_voters")

        if n_voters is not None and no_util_voters is not None and n_voters > 0:
            exclusion_ratio = no_util_voters / n_voters
            data_by_algo[rec.algo_name].append(exclusion_ratio)

    x_points = [round(i * 0.01, 2) for i in range(1, 101)]  # 0.01 to 1.00

    plot_lines = []
    for i, algo_name in enumerate(sorted(data_by_algo.keys(), key=algo_sort_key)):
        exclusion_ratios = data_by_algo[algo_name]
        n = len(exclusion_ratios)
        if n == 0:
            continue
        coordinates = [
            (x, round(sum(1 for v in exclusion_ratios if v >= x) / n * 100, 2))
            for x in x_points
        ]
        plot_lines.append(
            PlotLine(
                color=get_algo_color(algo_name),
                coordinates=coordinates,
                legend_entry=get_algo_label(algo_name),
            )
        )

    if not plot_lines:
        return []

    return [
        Graph(
            title="Exclusion Ratio Distribution",
            xlabel="Exclusion Ratio (Voters with no utility)",
            ylabel="Elections with Exclusion Ratio $\\geq x$ \\%",
            plot_lines=plot_lines,
            ymajorgrids=True,
            grid_style="dashed",
            xmode="linear",
            ymode="linear",
            legend_pos="outer north east",
        )
    ]


def graph_min_violation_degree_distribution_pr() -> List[Graph]:
    """
    For each utility (cost, card), and for each algorithm, collect the
    violation_degree (1 - satisfaction_degree) for EJR per election (using 0 when None).  Then, for
    x in [0.00, 0.01, ..., 1.00], compute the percentage of elections where
    the violation degree is >= x (complementary CDF).

    Returns a list of two Graph objects: one for EJR[cost], one for EJR[card].
    """
    parser = OutcomeParser()

    # {utility: {algo_name: [violation_degree_per_election, ...]}}
    data_by_utility: dict[str, dict[str, list[float]]] = {
        "cost": defaultdict(list),
        "card": defaultdict(list),
    }

    for rec in parser.records:
        for utility in ["cost", "card"]:
            ejr_util = rec.results.get("ejr_alpha", {}).get(utility)
            if ejr_util is not None:
                raw = ejr_util.get("satisfaction_degree")
                data_by_utility[utility][rec.algo_name].append(
                    (1 - raw) if raw is not None else 0
                )

    x_points = [round(i * 0.01, 2) for i in range(0, 100)]  # 0.00 to 0.99

    graphs = []
    for utility in ["cost", "card"]:
        algo_violations = data_by_utility[utility]
        if not algo_violations:
            continue

        plot_lines = []
        for i, algo_name in enumerate(
            sorted(algo_violations.keys(), key=algo_sort_key)
        ):
            violations = algo_violations[algo_name]
            n = len(violations)
            if n == 0:
                continue
            coordinates = [
                (x, round(sum(1 for v in violations if v <= x) / n * 100, 2))
                for x in x_points
            ]
            plot_lines.append(
                PlotLine(
                    color=get_algo_color(algo_name),
                    coordinates=coordinates,
                    legend_entry=get_algo_label(algo_name),
                )
            )

        graphs.append(
            Graph(
                title=f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} Violation Degree Distribution",
                xlabel="Violation Degree ($\\phi$)",
                ylabel="Elections with Violation Degree $\\le \\phi$",
                plot_lines=plot_lines,
                ymajorgrids=True,
                grid_style="dashed",
                xmode="linear",
                ymode="linear",
                legend_pos="outer north east",
            )
        )

    return graphs


def graph_unsat_voter_fraction_distribution_pr() -> List[Graph]:
    """
    For each utility (cost, card), and for each algorithm, collect the
    number_of_unsat_voters / number_of_voters ratio for EJR per election
    (using 0 when number_of_unsat_voters is None).  Then, for
    x in [0.01, 0.02, ..., 1.00], compute the percentage of elections where
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

    x_points = [round(i * 0.01, 2) for i in range(0, 100)]  # 0.00 to 0.99

    graphs = []
    for utility in ["cost", "card"]:
        algo_data = data_by_utility[utility]
        if not algo_data:
            continue

        plot_lines = []
        for i, algo_name in enumerate(sorted(algo_data.keys(), key=algo_sort_key)):
            fractions = algo_data[algo_name]
            n = len(fractions)
            if n == 0:
                continue
            coordinates = [
                (x, round(sum(1 for v in fractions if v <= x) / n * 100, 2))
                for x in x_points
            ]
            plot_lines.append(
                PlotLine(
                    color=get_algo_color(algo_name),
                    coordinates=coordinates,
                    legend_entry=get_algo_label(algo_name),
                )
            )

        graphs.append(
            Graph(
                title=f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} Unsatisfied Voter Fraction Distribution",
                xlabel="Fraction of Unsatisfied Voters ($r$)",
                ylabel="Elections with Fraction $\\le r$",
                plot_lines=plot_lines,
                ymajorgrids=True,
                grid_style="dashed",
                xmode="linear",
                ymode="linear",
                legend_pos="outer north east",
            )
        )

    return graphs


def graph_vote_length_vs_violation_degree_ejr() -> List[SubfigureGrid]:
    """
    For each utility (cost, card), create a SubfigureGrid figure containing
    one subfigure per algorithm. Each subfigure plots vote_length (x-axis)
    vs violation_degree (1 - satisfaction_degree) (y-axis), using 0 when satisfaction_degree is None.
    The legend is omitted; the algorithm name appears in the graph title.

    Returns a list of two SubfigureGrid objects: one for EJR[cost], one for EJR[card].
    """
    parser = OutcomeParser()

    # {algo_name: {utility: [(vote_length, violation_degree), ...]}}
    data_by_algo: dict[str, dict[str, list[tuple]]] = defaultdict(
        lambda: {"cost": [], "card": []}
    )

    for rec in parser.records:
        vote_length = rec.metadata.get("vote_length")
        if vote_length is None:
            continue
        for utility in ["cost", "card"]:
            ejr_util = rec.results.get("ejr_alpha", {}).get(utility)
            if ejr_util is not None:
                raw = ejr_util.get("satisfaction_degree")
                data_by_algo[rec.algo_name][utility].append(
                    (vote_length, (1 - raw) if raw is not None else 0)
                )

    figures = []
    for utility in ["cost", "card"]:
        graphs = []
        for algo_name in sorted(data_by_algo.keys(), key=algo_sort_key):
            coords = sorted(data_by_algo[algo_name][utility], key=lambda p: p[0])
            if not coords:
                continue

            # Group by rounded vote_length and compute mean satisfaction degree
            grouped_coords = OutcomeParser.moving_average(coords)

            graphs.append(
                Graph(
                    title=get_algo_label(algo_name),
                    xlabel="Vote Length",
                    ylabel="Violation Degree ($\\phi$)",
                    plot_lines=[
                        PlotLine(
                            color="black",
                            mark="*",
                            mark_size=1,
                            coordinates=coords,
                            only_marks=True,
                        ),
                        PlotLine(
                            color="red",
                            mark=None,
                            coordinates=grouped_coords,
                            legend_entry=f"{get_algo_label(algo_name)} (mean)",
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
                    title=f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} Violation Degree vs Vote Length",
                    caption=(
                        f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} violation degree ($\\phi = 1 - $ satisfaction degree) as a function of vote length, "
                        f"shown per algorithm. A value of 1 indicates a full violation."
                    ),
                    graphs=graphs,
                )
            )

    return figures


def _graph_ejr_check_time(
    x_fn: Callable[["ElectionRecord", str, str], Optional[float]],
    x_label: str,
    title_suffix: str,
    config: str = "All_without_early",
) -> Optional[Graph]:
    """Shared implementation for EJR running-time graphs.

    Returns a single Graph with one line per EJR type.  Each line's y-values
    are the cumulative moving average of running time across all algorithms
    and both utilities (cost + card), sorted by x.
    """
    ejr_types = CONFIGS[config]
    parser = OutcomeParser()

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
        coords = OutcomeParser.moving_average(data[ejr_type])
        if coords:
            plot_lines.append(
                PlotLine(
                    color=get_ejr_color(ejr_type),
                    coordinates=coords,
                    legend_entry=_EJR_LABELS.get(ejr_type, ejr_type.upper()),
                )
            )

    if not plot_lines:
        return None
    return Graph(
        title=f"{_EJR_LABELS['ejr']} Running Time vs {title_suffix}",
        xlabel=x_label,
        ylabel="Moving Average Running Time (s)",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )


def graph_algorithm_time_vs_projects(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR running time vs number_of_projects."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("number_of_projects"),
        x_label="Number of Projects",
        title_suffix="Number of Projects",
        config=config,
    )


def graph_algorithm_time_vs_projects_ejr_compare() -> Optional[Graph]:
    """EJR running time vs number_of_projects, comparing EJR and EJR-exit-early only."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("number_of_projects"),
        x_label="Number of Projects",
        title_suffix="Number of Projects (EJR vs EJR-exit-early)",
        config="EJR_compare",
    )


def graph_algorithm_time_vs_p_sets_checked(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR running time vs p_sets_checked."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, et, u: rec.results.get(et, {})
        .get(u, {})
        .get("p_sets_checked"),
        x_label="T-Cohesive Sets Checked",
        title_suffix="T-Cohesive Sets Checked",
        config=config,
    )


def graph_algorithm_time_vs_vote_length(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR running time vs vote_length."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("vote_length"),
        x_label="Vote Length",
        title_suffix="Vote Length",
        config=config,
    )


def graph_algorithm_time_vs_number_of_voters(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR running time vs number_of_voters."""
    return _graph_ejr_check_time(
        x_fn=lambda rec, _et, _u: rec.metadata.get("number_of_voters"),
        x_label="Number of Voters",
        title_suffix="Number of Voters",
        config=config,
    )


def graph_algorithm_time_vs_vote_length_times_avg_cost(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR running time vs vote_length * average_project_cost."""

    def x_fn(rec: "ElectionRecord", _et: str, _u: str) -> Optional[float]:
        vl = rec.metadata.get("vote_length")
        apc = rec.metadata.get("average_project_cost")
        if vl is None or apc is None:
            return None
        return vl * apc

    return _graph_ejr_check_time(
        x_fn=x_fn,
        x_label="Vote Length $\\times$ Avg Project Cost",
        title_suffix="Vote Length $\\times$ Avg Project Cost",
        config=config,
    )


def graph_algorithm_time_vs_budget_per_avg_cost(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR running time vs budget / average_project_cost."""

    def x_fn(rec: "ElectionRecord", _et: str, _u: str) -> Optional[float]:
        budget = rec.metadata.get("budget_limit")
        apc = rec.metadata.get("average_project_cost")
        if budget is None or apc is None or apc == 0:
            return None
        return budget / apc

    return _graph_ejr_check_time(
        x_fn=x_fn,
        x_label="Budget / Avg Project Cost",
        title_suffix="Budget / Avg Project Cost",
        config=config,
    )


def graph_algorithm_time_vs_complexity_product(
    config: str = "ejr",
) -> Optional[Graph]:
    """EJR running time vs p_sets_checked * number_of_projects * number_of_voters * layers_checked.

    Scatter plot (no moving average), one colour per EJR type, pooled across
    all algorithms and utilities.
    """
    ejr_types = ["ejr"] #CONFIGS[config]
    parser = OutcomeParser()

    # {ejr_type: {filename: {"xs": [...], "ys": [...]}}}
    raw: dict[str, dict[str, dict]] = {et: defaultdict(lambda: {"xs": [], "ys": []}) for et in ejr_types}

    for rec in parser.records:
        voters = rec.metadata.get("number_of_voters")
        projects = rec.metadata.get("number_of_projects")
        if voters is None:
            continue
        for ejr_type in ejr_types:
            for utility in ["cost", "card"]:
                result = rec.results.get(ejr_type, {}).get(utility, {})
                t = result.get("time")
                p_sets = result.get("p_sets_checked")
                layers = result.get("layers_checked")
                if t is None or p_sets is None or layers is None or projects is None:
                    continue
                x = p_sets #* (voters * layers)  # complexity product
                y = t / (  voters * projects)  # time normalized by complexity product)
                raw[ejr_type][rec.filename]["xs"].append(x)
                raw[ejr_type][rec.filename]["ys"].append(y)

    # One averaged point per election per ejr_type
    data: dict[str, list[tuple]] = {et: [] for et in ejr_types}
    for ejr_type in ejr_types:
        for vals in raw[ejr_type].values():
            xs, ys = vals["xs"], vals["ys"]
            if xs:
                data[ejr_type].append((sum(xs) / len(xs), sum(ys) / len(ys)))

    plot_lines = []
    for ejr_type in ejr_types:
        points = data[ejr_type]
        if not points:
            continue
        plot_lines.append(
            PlotLine(
                color=get_ejr_color(ejr_type),
                coordinates=points,
                legend_entry=_EJR_LABELS.get(ejr_type, ejr_type.upper()),
                mark="*",
                mark_size=1,
                only_marks=True,
            )
        )

    if not plot_lines:
        raise ValueError("No data points found for EJR running time vs complexity product graph.")
    return Graph(
        title=f"{_EJR_LABELS['ejr']} Running Time vs $p\\text{{-sets}}$",
        xlabel="$p\\text{-sets}$",
        ylabel="Running Time (s) / ($n \\times m$)",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )


def graph_p_sets_per_layer(
    filename: str = "Poland_Warszawa_2018_Bialoleka_obszar_3.json",
) -> Optional[Graph]:
    """Plot p_sets checked per layer for a single election file.

    One line per (ejr_type, utility) combination found in the file.
    X-axis: layer number, Y-axis: p_sets checked in that layer.
    """
    filepath = os.path.join(_DATA_DIR, "outcomes", filename)
    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Could not load {filename}: {e}")
        return None

    plot_lines = []
    seen: set[tuple] = set()  # deduplicate identical series
    idx = 0

    for algo_name, algo_results in data.get("results", {}).items():
        for ejr_type in ["ejr", "ejr_alpha", "ejr_x", "ejr_1"]:
            for utility in ["cost", "card"]:
                raw = (
                    algo_results.get(ejr_type, {})
                    .get(utility, {})
                    .get("p_sets_in_layer")
                )
                if not raw:
                    continue
                coords = tuple(sorted((int(k), v) for k, v in raw.items()))
                if coords in seen:
                    continue
                seen.add(coords)
                label = f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS.get(ejr_type, ejr_type)}"
                plot_lines.append(
                    PlotLine(
                        color=get_ejr_color(ejr_type),
                        coordinates=list(coords),
                        legend_entry=label,
                        mark="*",
                        mark_size=1.5,
                    )
                )
                idx += 1

    if not plot_lines:
        return None
    return Graph(
        title=f"P-Sets per Layer — {filename}",
        xlabel="$|T|$ (Layer)",
        ylabel="T-Cohesive Sets Checked",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )


def graph_vote_length_vs_largest_t_checked(
    config: str = "All_without_early",
) -> Optional[Graph]:
    """EJR largest |T| checked vs vote_length, with moving average, one line per EJR type."""
    ejr_types = CONFIGS[config]
    parser = OutcomeParser()

    # For scatter: one point per election per ejr_type = max layers_checked across all algorithms & utilities
    # For moving average: all (vote_length, layers_checked) pairs pooled
    scatter_max: dict[str, dict[str, tuple]] = {
        et: {} for et in ejr_types
    }  # et -> filename -> (vl, max_layers)
    data: dict[str, list[tuple]] = {et: [] for et in ejr_types}

    for rec in parser.records:
        vote_length = rec.metadata.get("vote_length")
        if vote_length is None:
            continue
        for ejr_type in ejr_types:
            for utility in ["cost", "card"]:
                layers = (
                    rec.results.get(ejr_type, {}).get(utility, {}).get("layers_checked")
                )
                if layers is not None:
                    data[ejr_type].append((vote_length, layers))
                    prev = scatter_max[ejr_type].get(rec.filename)
                    if prev is None or layers > prev[1]:
                        scatter_max[ejr_type][rec.filename] = (vote_length, layers)

    plot_lines = []
    for i, ejr_type in enumerate(ejr_types):
        raw = data[ejr_type]
        avg_coords = OutcomeParser.moving_average(raw)
        if not avg_coords:
            continue
        label = _EJR_LABELS.get(ejr_type, ejr_type.upper())
        color = get_ejr_color(ejr_type)
        # Raw scatter points: one per election (max layers_checked)
        scatter = list(scatter_max[ejr_type].values())
        plot_lines.append(
            PlotLine(
                color=color,
                mark="*",
                mark_size=1,
                style="fill opacity=0.2, draw opacity=0.2",
                coordinates=scatter,
                legend_entry=f"{label} (points)",
                only_marks=True,
            )
        )
        # Moving average line
        plot_lines.append(
            PlotLine(
                color=color,
                coordinates=avg_coords,
                legend_entry=f"{label} (mean)",
            )
        )

    if not plot_lines:
        return None
    return Graph(
        title="Largest $|T|$ Checked vs Vote Length",
        xlabel="Vote Length",
        ylabel="Largest $|T|$ Checked",
        plot_lines=plot_lines,
        ymajorgrids=True,
        grid_style="dashed",
        xmode="linear",
        ymode="linear",
        legend_pos="outer north east",
    )


def analyze_ejr_violation_mutual_information() -> List[SubfigureGrid]:
    """
    For each utility (cost, card), return a SubfigureGrid with one subfigure
    per feature.  Each subfigure plots one line per voting rule showing the
    moving average of EJR violation % (y-axis) as a function of the feature
    value (x-axis).
    """
    parser = OutcomeParser()

    feature_names = [
        "budget_limit",
        "number_of_voters",
        "vote_length",
        "number_of_projects",
        "average_project_cost",
        "budget_per_avg_cost",
        "vote_length_times_avg_cost",
    ]

    # {utility: {algo_name: {feat: [(feat_val, violated_pct), ...]}}}
    data: dict[str, dict[str, dict[str, list[tuple]]]] = {
        "cost": defaultdict(lambda: defaultdict(list)),
        "card": defaultdict(lambda: defaultdict(list)),
    }

    for rec in parser.records:
        meta = rec.metadata
        budget = meta.get("budget_limit")
        apc = meta.get("average_project_cost")
        vl = meta.get("vote_length")
        raw_features = {
            "budget_limit": budget,
            "number_of_voters": meta.get("number_of_voters"),
            "vote_length": vl,
            "number_of_projects": meta.get("number_of_projects"),
            "average_project_cost": apc,
            "budget_per_avg_cost": (
                (budget / apc) if budget is not None and apc else None
            ),
            "vote_length_times_avg_cost": (
                (vl * apc) if vl is not None and apc is not None else None
            ),
        }
        for utility in ["cost", "card"]:
            ejr_result = rec.results.get("ejr", {}).get(utility)
            if ejr_result is None:
                continue
            violated_pct = 100.0 if ejr_result.get("violation_found", False) else 0.0
            for feat in feature_names:
                feat_val = raw_features.get(feat)
                if feat_val is not None:
                    data[utility][rec.algo_name][feat].append((feat_val, violated_pct))

    figures = []
    for utility in ["cost", "card"]:
        algo_data = data[utility]
        graphs = []
        for feat in feature_names:
            plot_lines = []
            for i, algo_name in enumerate(sorted(algo_data.keys(), key=algo_sort_key)):
                coords = algo_data[algo_name][feat]
                if not coords:
                    continue
                avg_coords = OutcomeParser.moving_average(coords)
                if avg_coords:
                    plot_lines.append(
                        PlotLine(
                            color=get_algo_color(algo_name),
                            coordinates=avg_coords,
                            legend_entry=get_algo_label(algo_name),
                        )
                    )

            if plot_lines:
                graphs.append(
                    Graph(
                        title=feat.replace("_", " "),
                        xlabel=feat.replace("_", " "),
                        ylabel="Violation \\%",
                        plot_lines=plot_lines,
                        ymajorgrids=True,
                        grid_style="dashed",
                        xmode="linear",
                        ymode="linear",
                        legend_pos="outer north east",
                        ymin=0,
                        ymax=100,
                    )
                )

        if graphs:
            figures.append(
                SubfigureGrid(
                    title=f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} Violation Rate vs Features",
                    caption=(
                        f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} violation rate (\\%) as a function of election features, "
                        f"shown per voting rule as a moving average."
                    ),
                    graphs=graphs,
                )
            )

    return figures


def graph_ejr_violation_budget_vs_voters() -> List[Graph]:
    """
    For each election and each utility (cost, card), determine if EJR is
    violated by ANY voting rule (any algorithm).  Plot elections as scatter
    points: green = satisfied in every rule, red = violated in at least one.
    X-axis: budget, Y-axis: number of voters.

    Returns a list of two Graph objects: one for EJR[cost], one for EJR[card].
    """
    parser = OutcomeParser()

    # {utility: {filename: {violated, budget, voters}}}
    election_data: dict[str, dict[str, dict]] = {
        "cost": {},
        "card": {},
    }

    for rec in parser.records:
        budget = rec.metadata.get("budget_limit")
        voters = rec.metadata.get("number_of_voters")
        if budget is None or voters is None:
            continue
        if budget > 10000000:
            continue  # Exclude extreme outliers for better visualization
        for utility in ["cost", "card"]:
            if rec.filename not in election_data[utility]:
                election_data[utility][rec.filename] = {
                    "violated": False,
                    "budget": budget,
                    "voters": voters,
                }
            ejr_result = rec.results.get("ejr", {}).get(utility)
            if ejr_result and ejr_result.get("violation_found", False):
                election_data[utility][rec.filename]["violated"] = True

    graphs = []
    for utility in ["cost", "card"]:
        by_election = election_data[utility]
        if not by_election:
            continue

        satisfied = [
            (d["budget"], d["voters"])
            for d in by_election.values()
            if not d["violated"]
        ]
        violated = [
            (d["budget"], d["voters"]) for d in by_election.values() if d["violated"]
        ]

        plot_lines = []
        if satisfied:
            plot_lines.append(
                PlotLine(
                    color="green",
                    coordinates=satisfied,
                    legend_entry="Satisfied (all rules)",
                    mark="*",
                    mark_size=1.5,
                    only_marks=True,
                )
            )
        if violated:
            plot_lines.append(
                PlotLine(
                    color="red",
                    coordinates=violated,
                    legend_entry="Violated (some rule)",
                    mark="*",
                    mark_size=1.5,
                    only_marks=True,
                )
            )

        if plot_lines:
            graphs.append(
                Graph(
                    title=f"{_UTIL_LABELS.get(utility, utility)}-{_EJR_LABELS['ejr']} Violations: Budget vs Number of Voters",
                    xlabel="Budget",
                    ylabel="Number of Voters",
                    plot_lines=plot_lines,
                    ymajorgrids=True,
                    grid_style="dashed",
                    xmode="linear",
                    ymode="linear",
                    legend_pos="outer north east",
                )
            )

    return graphs


_LATEX_PREAMBLE = """\\documentclass[tikz,border=0pt]{standalone}
\\usepackage{tikz}
\\usepackage{booktabs}
\\usepackage{pgfplots}
\\usepackage{amsmath}
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
        [
            "pdflatex",
            "-interaction=nonstopmode",
            "-cnf-line=extra_mem_bot=50000000",
            "-cnf-line=extra_mem_top=10000000",
            f"{name}.tex",
        ],
        cwd=pdf_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if os.path.exists(pdf_path):
        for ext in (".aux", ".log"): # , ".tex"
            p = os.path.join(pdf_dir, f"{name}{ext}")
            if os.path.exists(p):
                os.remove(p)
        print(f"  -> 06_tex/pdf/{name}.pdf")
        return True
    else:
        for ext in (".aux"):
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
    num_rows = (n + 1) // 2
    # Set axis width close to the rendered size (0.49\textwidth ≈ 8cm minus ~1cm
    # for ylabel+tick labels), so \includegraphics[width=\linewidth] scales
    # at roughly 1× and font sizes stay at document size.
    # Height is left to pgfplots default (natural aspect ratio).
    graph_width = "7cm"
    graph_height = None
    graph_names = []

    for j, graph in enumerate(grid.graphs):
        graph_name = f"{name}_graph_{j}"
        buf = io.StringIO()
        SubfigureGrid._print_graph(graph, buf, height=graph_height, width=graph_width)
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


def print_winning_set_size_stats() -> None:
    """Print winning_set_size statistics across all elections.

    For each election file, finds the max winning_set_size across all algorithms.
    Then prints the overall max and average of those per-election maxima.
    """
    outcomes_dir = os.path.join(_DATA_DIR, "outcomes")
    if not os.path.exists(outcomes_dir):
        print(f"Outcomes directory {outcomes_dir} not found")
        return

    per_election_maxima: list[float] = []
    for filename in sorted(f for f in os.listdir(outcomes_dir) if f.endswith(".json")):
        filepath = os.path.join(outcomes_dir, filename)
        try:
            with open(filepath) as f:
                data = json.load(f)
            sizes = [
                algo_results.get("algo_stats", {}).get("winning_set_size")
                for algo_results in data.get("results", {}).values()
            ]
            sizes = [s for s in sizes if s is not None]
            if sizes:
                per_election_maxima.append(max(sizes))
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    if not per_election_maxima:
        print("No winning_set_size data found.")
        return

    overall_max = max(per_election_maxima)
    overall_avg = sum(per_election_maxima) / len(per_election_maxima)
    print(f"Elections with data : {len(per_election_maxima)}")
    print(f"Max of per-election maxima  : {overall_max}")
    print(f"Avg of per-election maxima  : {overall_avg:.4f}")


def print_stats(config: str = "All_without_early") -> None:
    """Main entry point for statistics generation.

    For each output item:
    - Tables and Graphs: compiled to a standalone PDF in tex/pdf/, then a .tex
      snippet with \\includegraphics is written to tex/.
    - SubfigureGrids: each constituent graph is compiled to its own PDF in
      tex/pdf/, and a .tex snippet assembling them into a figure with subfigures
      is written to tex/.
    """
    tex_dir = os.path.join(_DATA_DIR, "06_tex")
    pdf_dir = os.path.join(tex_dir, "pdf")
    pdf_include_prefix = "06_tex/pdf"
    if os.path.exists(tex_dir):
        shutil.rmtree(tex_dir)
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(pdf_dir)

    functions = [
        ("print_results_by_algorithm", print_results_by_algorithm(config)),  # GOAT
        ("analyze_utility_comparison", [analyze_utility_comparison()]),
        (
            "analyze_ejr_violations_by_utility",
            analyze_ejr_violations_by_utility(),
        ),  # a qq table
        (
            "graph_vote_length_vs_p_sets_ejr_card",
            [graph_vote_length_vs_p_sets_ejr_card()],
        ),
        (
            "graph_min_violation_degree_distribution_pr",
            graph_min_violation_degree_distribution_pr(),
        ),
        (
            "graph_exclusion_ratio_distribution",
            graph_exclusion_ratio_distribution(),
        ),
        (
            "graph_unsat_voter_fraction_distribution_pr",
            graph_unsat_voter_fraction_distribution_pr(),
        ),
        (
            "graph_vote_length_vs_violation_degree_ejr",
            graph_vote_length_vs_violation_degree_ejr(),
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
            "graph_p_sets_per_layer",
            [graph_p_sets_per_layer()],
        ),
        (
            "graph_vote_length_vs_largest_t_checked",
            [graph_vote_length_vs_largest_t_checked(config)],
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
            "graph_algorithm_time_vs_projects_ejr_compare",
            [graph_algorithm_time_vs_projects_ejr_compare()],
        ),
        (
            "graph_algorithm_time_vs_budget_per_avg_cost",
            [graph_algorithm_time_vs_budget_per_avg_cost(config)],
        ),
        (
            "graph_algorithm_time_vs_complexity_product",
            [graph_algorithm_time_vs_complexity_product()],
        ),
        (
            "analyze_ejr_violation_mutual_information",
            analyze_ejr_violation_mutual_information(),
        ),
        (
            "graph_ejr_violation_budget_vs_voters",
            graph_ejr_violation_budget_vs_voters(),
        ),
    ]

    for func_name, items in functions:
        items = [x for x in items if x is not None]
        for i, item in enumerate(items):
            name = func_name if len(items) == 1 else f"{func_name}_{i}"
            tex_out_path = os.path.join(tex_dir, f"{name}.tex")

            if isinstance(item, SubfigureGrid):
                item.name = name
                _compile_subfigure_grid(
                    item, name, tex_out_path, pdf_dir, pdf_include_prefix
                )
            elif isinstance(item, Table):
                with open(tex_out_path, "w") as f:
                    item.print_latex(file=f, label=name)
            else:
                buf = io.StringIO()
                item.print_latex(file=buf, include_title=False)
                print(f"Compiling {name}...")
                _compile_snippet_to_pdf(buf.getvalue(), name, pdf_dir)
                with open(tex_out_path, "w") as f:
                    if isinstance(item, Graph) and item.title:
                        f.write(f"% {item.title}\n")
                    f.write(f"\\includegraphics{{{pdf_include_prefix}/{name}.pdf}}\n")


if __name__ == "__main__":
    # print_winning_set_size_stats()
    print_stats()
