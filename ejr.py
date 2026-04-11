from pabutools.election import Project, Instance, ApprovalBallot, ApprovalProfile, Cost_Sat, parse_pabulib
from pabutools.rules import greedy_utilitarian_welfare, sequential_phragmen, method_of_equal_shares
import os

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
    costs = []
    for p in projects:
        project_names.append(str(p))
        costs.append(p.cost)

    approvals = []
    for ballot in profile:
        approved = set()
        for p in ballot:
            approved.add(proj_to_idx[p])
        approvals.append(approved)

    winners = {proj_to_idx[p] for p in outcome}
    budget = instance.budget_limit

    return project_names, costs, approvals, winners, budget

# Compute the number of winners approved by each ballot
def compute_winner_counts(approvals, winners):
    return [len(ballot & winners) for ballot in approvals]

# Compute the supporters of each project
def compute_supporters_by_project(num_projects, approvals):
    supporters = [set() for _ in range(num_projects)]
    for voter_idx, ballot in enumerate(approvals):
        for b in ballot:
            supporters[b].add(voter_idx)
    return supporters

def find_ejr_violation(project_costs, approvals, winners, budget, project_names=None, verbose=True):
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

    if len(approvals) == 0:
        return None

    winner_counts = compute_winner_counts(approvals, winners)
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
                print(f"  Skipping ell={ell}: not enough unsatisfied voters even for cheapest size-{ell} set.")
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

        # Precompute suffix cheapest costs for lower bound pruning
        sorted_remaining_costs = [project_costs[c] for c in candidate_ids]

        witness = _dfs_find_violation(
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
            sorted_remaining_costs=sorted_remaining_costs,
            verbose=verbose
        )

        if witness is not None:
            return witness

    return None

def _dfs_find_violation(
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
    sorted_remaining_costs,
    verbose=False):

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
            "support_size": support_count
        }

    remaining_needed = ell - depth
    remaining_available = len(candidate_ids) - start_idx

    # Prune 2: not enough projects left
    if remaining_available < remaining_needed:
        return None

    # Prune 3: even cheapest possible completion is too expensive
    remaining_costs = [costs[candidate_ids[j]] for j in range(start_idx, len(candidate_ids))]
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
        result = _dfs_find_violation(
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
            sorted_remaining_costs=sorted_remaining_costs,
            verbose=verbose
        )
        chosen.pop()

        if result is not None:
            return result

    return None

path = os.path.join("./elections/", "Hungary_Budapest_2024.pb")
instance, profile = parse_pabulib(path)
outcome_greedy = greedy_utilitarian_welfare(instance, profile, sat_class=Cost_Sat, analytics=False)

project_names, costs, approvals, winners, budget = convert_pabutools_election(instance, profile, outcome_greedy)


violation = find_ejr_violation(costs, approvals, winners, budget, project_names, verbose=True)
print(violation)
print (outcome_greedy)
