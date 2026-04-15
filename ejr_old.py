from pabutools.election import (
    Cost_Sat,
    Cardinality_Sat,
    parse_pabulib,
)
from pabutools.rules import (
    greedy_utilitarian_welfare,
    sequential_phragmen,
    method_of_equal_shares,
)
import os
from typess import EJRViolationWitness, EJRViolationResult


def convert_pabutools_election(instance, profile, outcome):
    """
    Returns:
        project_names: list[str]
        costs: list[int]
        approvals: list[set[int]]
        winners: set[int]
        budget: int
    """
    projects = list(instance)
    # Convert from the Project objects to integer indices for our EJR checker
    proj_to_idx = {p: idx for idx, p in enumerate(projects)}

    project_names = []
    project_costs = []
    for p in projects:
        project_names.append(str(p))
        project_costs.append(p.cost)

    approvals = []
    for ballot in profile:
        approved = set()
        for p in ballot:
            approved.add(proj_to_idx[p])
        approvals.append(approved)

    winning_outcome = {proj_to_idx[p] for p in outcome}
    budget = instance.budget_limit

    return project_names, project_costs, approvals, winning_outcome, budget


# Compute the supporters of each project
def compute_supporters_by_project(num_projects, approvals):
    supporters = [set() for _ in range(num_projects)]
    for voter_idx, ballot in enumerate(approvals):
        for b in ballot:
            supporters[b].add(voter_idx)
    return supporters

def find_ejr_violation(
    instance, profile, outcome, util, verbose=False
) -> EJRViolationResult:
    if util == Cardinality_Sat:
        return find_ejr_violation_card(instance, profile, outcome, verbose)
    elif util == Cost_Sat:
        return find_ejr_violation_cost(instance, profile, outcome, verbose)
    else:
        raise ValueError(f"Unknown utility type: {util}")

def find_ejr_violation_card(
    instance, profile, outcome, verbose=True
) -> EJRViolationResult:
    """
    Exact EJR checker for the PB-style definition.

    Returns:
        None if no violation is found
        otherwise a dict with a witness:
            {
                "ell": int,
                "T": list[int],
                "T_names": list[str],
                "cost": numeric,
                "supporters": list[int],
                "support_size": int
            }
    """

    project_names, project_costs, approvals, winning_outcome, budget = convert_pabutools_election(instance, profile, outcome)

    if len(approvals) == 0:
        return EJRViolationResult(witness=None, p_sets_checked=0)

    # Precompute some data structures for efficiency
    winner_counts = [len(ballot & winning_outcome) for ballot in approvals]
    supporters_by_project = compute_supporters_by_project(len(project_costs), approvals)

    # Maximum ell worth checking:
    # no voter can demand more than the number of projects they approve
    max_ell = max((len(ballot) for ballot in approvals), default=0)

    # Global sorted costs for quick lower bounds
    all_costs_sorted = sorted(project_costs)

    for ell in range(1, max_ell + 1):
        if verbose:
            print(f"Checking ell = {ell}")

        unsat_voters = {i for i in range(len(approvals)) if winner_counts[i] < ell}
        unsat_count = len(unsat_voters)

        if unsat_count == 0:
            continue

        # Lower bound: even the cheapest ell-set must satisfy the threshold
        if len(all_costs_sorted) < ell:
            continue

        min_possible_cost = sum(all_costs_sorted[:ell])
        if budget * unsat_count < len(approvals) * min_possible_cost:
            if verbose:
                print(
                    f"  Skipping ell={ell}: not enough unsatisfied voters even for cheapest size-{ell} set."
                )
            continue

        # Candidate filtering: keep only projects with enough unsatisfied supporters
        candidate_data = []
        for c in range(len(project_costs)):
            supp = supporters_by_project[c] & unsat_voters
            supp_count = len(supp)

            # singleton necessary condition
            if budget * supp_count >= len(approvals) * project_costs[c]:
                candidate_data.append((c, supp, supp_count))

        if len(candidate_data) < ell:
            if verbose:
                print(f"  Skipping ell={ell}: fewer than {ell} viable projects.")
            continue

        # Sort projects to make search faster:
        # more support first, then cheaper cost
        candidate_data.sort(key=lambda x: (-x[2], project_costs[x[0]]))

        candidate_ids = [x[0] for x in candidate_data]
        support_map = {x[0]: x[1] for x in candidate_data}

        witness = _dfs_find_violation_card(
            ell=ell,
            start_idx=0,
            chosen=[],
            current_support=unsat_voters,
            current_cost=0,
            candidate_ids=candidate_ids,
            support_map=support_map,
            costs=project_costs,
            budget=budget,
            n=len(approvals),
            project_names=project_names,
            verbose=verbose,
        )

        if witness is not None:
            return EJRViolationResult(
                witness=EJRViolationWitness(set(witness["T"]), witness["supporters"]),
                p_sets_checked=0,
            )

    return EJRViolationResult(witness=None, p_sets_checked=0)


def _dfs_find_violation_card(
    ell,
    start_idx,
    chosen,
    current_support,
    current_cost,
    candidate_ids,
    support_map,
    costs,
    budget,
    n,
    project_names,
    verbose=False,
):

    depth = len(chosen)
    support_count = len(current_support)

    # Prune 1: current threshold already fails
    if budget * support_count < n * current_cost:
        return None

    # Success: exactly ell projects chosen
    if depth == ell:
        return {
            "ell": ell,
            "T": list(chosen),
            "T_names": [project_names[c] if project_names else str(c) for c in chosen],
            "cost": current_cost,
            "supporters": sorted(current_support),
            "support_size": support_count,
        }

    remaining_needed = ell - depth
    remaining_available = len(candidate_ids) - start_idx

    # Prune 2: not enough projects left
    if remaining_available < remaining_needed:
        return None

    # Prune 3: even cheapest possible completion is too expensive
    remaining_costs = [
        costs[candidate_ids[j]] for j in range(start_idx, len(candidate_ids))
    ]
    if len(remaining_costs) < remaining_needed:
        return None

    min_extra_cost = sum(sorted(remaining_costs)[:remaining_needed])
    if budget * support_count < n * (current_cost + min_extra_cost):
        return None

    for j in range(start_idx, len(candidate_ids)):
        c = candidate_ids[j]

        new_support = current_support & support_map[c]
        new_cost = current_cost + costs[c]

        # immediate feasibility check for the child
        if budget * len(new_support) < n * new_cost:
            continue

        chosen.append(c)
        result = _dfs_find_violation_card(
            ell=ell,
            start_idx=j + 1,
            chosen=chosen,
            current_support=new_support,
            current_cost=new_cost,
            candidate_ids=candidate_ids,
            support_map=support_map,
            costs=costs,
            budget=budget,
            n=n,
            project_names=project_names,
            verbose=verbose,
        )
        chosen.pop()

        if result is not None:
            return result

    return None

def find_ejr_violation_cost(
    instance, profile, outcome, verbose=True
) -> EJRViolationResult:
    """
    Cost-based analogue of EJR checking.

    A set T is a witness if there is a group of voters who:
    - all approve every project in T,
    - each receive funded approved utility < cost(T),
    - and are large enough to proportionally deserve T:
          budget * |S| >= n * cost(T)

    Returns:
        EJRViolationResult
    """
    project_names, project_costs, approvals, winning_outcome, budget = convert_pabutools_election(
        instance, profile, outcome
    )

    n = len(approvals)
    if n == 0:
        return EJRViolationResult(witness=None, p_sets_checked=0)

    m = len(project_costs)

    # For each voter, utility = total cost of approved funded projects
    winner_utils = [
        sum(project_costs[c] for c in ballot & winning_outcome)
        for ballot in approvals
    ]

    supporters_by_project = compute_supporters_by_project(m, approvals)

    # Candidate ordering heuristic: more support first, then cheaper cost
    candidate_ids = list(range(m))
    candidate_ids.sort(key=lambda c: (-len(supporters_by_project[c]), project_costs[c]))

    def dfs_cost(start_idx, chosen, current_approvers, current_cost):
        # Ignore empty T
        if current_cost > 0:
            # Voters who approve all of chosen and are underrepresented relative to cost(T)
            unsat_supporters = {
                i for i in current_approvers
                if winner_utils[i] < current_cost
            }
            unsat_count = len(unsat_supporters)

            # Success: found a cost-based witness
            if budget * unsat_count >= n * current_cost:
                return {
                    "T": list(chosen),
                    "T_names": [project_names[c] for c in chosen],
                    "cost": current_cost,
                    "supporters": sorted(unsat_supporters),
                    "support_size": unsat_count,
                }

            # Safe prune:
            # even if all current approvers were underrepresented,
            # there still would not be enough support
            if budget * len(current_approvers) < n * current_cost:
                return None

        for j in range(start_idx, len(candidate_ids)):
            c = candidate_ids[j]
            new_approvers = current_approvers & supporters_by_project[c]
            if not new_approvers:
                continue

            new_cost = current_cost + project_costs[c]

            chosen.append(c)
            result = dfs_cost(
                start_idx=j + 1,
                chosen=chosen,
                current_approvers=new_approvers,
                current_cost=new_cost,
            )
            chosen.pop()

            if result is not None:
                return result

        return None

    witness = dfs_cost(
        start_idx=0,
        chosen=[],
        current_approvers=set(range(n)),
        current_cost=0,
    )

    if witness is not None:
        return EJRViolationResult(
            witness=EJRViolationWitness(set(witness["T"]), witness["supporters"]),
            p_sets_checked=0,
        )

    return EJRViolationResult(witness=None, p_sets_checked=0)

def print_stats(costs, approvals):
    average_project_cost = sum(costs) / len(costs)
    print(f"Average project cost: {average_project_cost}")
    projects_to_voters_ratio = len(costs) / len(approvals)
    print(f"Projects to voters ratio: {projects_to_voters_ratio}")
    vote_length = sum(len(ballot) for ballot in approvals) / len(approvals)
    print(f"Vote length: {vote_length}")
    vote_length_to_projects_ratio = vote_length / len(costs)
    print(f"Vote length to projects ratio: {vote_length_to_projects_ratio}")

def run_election(filename, rule="greedy", util=Cardinality_Sat):
    path = os.path.join("./elections/", filename)
    instance, profile = parse_pabulib(path)
    if rule == "greedy":
        outcome = greedy_utilitarian_welfare(instance=instance, profile=profile, sat_class=util)
    elif rule == "mes":
        outcome = method_of_equal_shares(instance=instance, profile=profile, sat_class=util)
    else:
        raise ValueError(f"Unknown rule: {rule}")
    return instance, profile, outcome


if __name__ == "__main__":
    instance, profile, outcome = run_election(filename="Poland_Warszawa_2023.pb", rule="greedy", util=Cost_Sat)
    violation = find_ejr_violation(instance, profile, outcome, util=Cost_Sat, verbose=True)
    print(violation.witness)
