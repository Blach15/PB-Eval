import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pabutools.election import Project
from pabutools.utils import Numeric
from typing import Callable


def iterate_all_affordable_p_sets(
    approvals: list[set[int]],
    costs: list[Numeric],
    projects: list[Project],
    budget: Numeric,
    callback: Callable[[tuple[int, ...], set[int]], bool],
    pre_callback: Callable[[], None] = lambda: None,
    verbose: bool = False,
) -> dict[int, int]:
    project_supporters = get_project_supporters(approvals, projects)

    n = len(approvals)
    layers_checked: dict[int, int] = {}
    layer = 0

    current_lattice_layer_worklist: list[tuple[tuple[int, ...], set[int]]] = list()
    next_lattice_layer_worklist: list[tuple[tuple[int, ...], set[int]]] = list()

    for pIdx in range(len(projects)):
        p_set: tuple[int, ...] = (pIdx,)
        next_lattice_layer_worklist.append((p_set, project_supporters[pIdx]))

    while len(next_lattice_layer_worklist) > 0:
        layer += 1
        current_lattice_layer_worklist = next_lattice_layer_worklist
        surviving_lattice_layer_worklist: list[tuple[tuple[int, ...], set[int]]] = []
        p_sets_in_layer = 0

        for p_set, voter_intersection in current_lattice_layer_worklist:
            p_sets_in_layer += 1
            pre_callback()

            # Get cached voter_intersection or calculate if not in cache
            if voter_intersection is None:
                raise ValueError(f"Voter intersection for {p_set} not found in cache.")
            # check that is cohesive set
            if len(voter_intersection) / n * budget < sum(costs[p] for p in p_set):
                continue  # can't afford

            # allow exit early, to find 1 witness
            if callback(p_set, voter_intersection):
                layers_checked[layer] = p_sets_in_layer
                return layers_checked

            surviving_lattice_layer_worklist.append((p_set, voter_intersection))

        layers_checked[layer] = p_sets_in_layer

        if verbose and len(surviving_lattice_layer_worklist) != 0:
            print(
                f"Surviving layer size: {len(surviving_lattice_layer_worklist[0][0])}, {len(surviving_lattice_layer_worklist)}"
            )
        next_lattice_layer_worklist = list()

        # Apriori join: only join itemsets that share the first k-1 elements
        for i in range(len(surviving_lattice_layer_worklist)):
            for j in range(i + 1, len(surviving_lattice_layer_worklist)):
                itemset_i, voter_intersection_i = surviving_lattice_layer_worklist[i]
                itemset_j, voter_intersection_j = surviving_lattice_layer_worklist[j]

                # Check if they share the first k-1 elements (apriori property)
                if itemset_i[:-1] == itemset_j[:-1]:
                    # keep the new set sorted.
                    new_set = tuple(itemset_i + (itemset_j[-1],))

                    # Cache the voter_intersection as intersection of the two parent sets' intersections
                    new_voter_intersection = voter_intersection_i & voter_intersection_j
                    next_lattice_layer_worklist.append(
                        (new_set, new_voter_intersection)
                    )
                else:
                    # Since itemsets are sorted, if prefixes don't match, skip to next i
                    break

    return layers_checked


def get_project_supporters(approvals, projects) -> list[set[int]]:
    project_supporters = [set() for _ in range(len(projects))]
    for voter_idx, ballot in enumerate(approvals):
        for p in ballot:
            project_supporters[p].add(voter_idx)
    return project_supporters
