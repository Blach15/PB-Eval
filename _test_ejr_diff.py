from ejr import (
    find_ejr_1_violation_witness,
    find_ejr_x_violation_witness,
    find_ejr_violation_witness,
)
from pabutools.election import Project

# Crafted example where EJR_1 and EJR_X SHOULD differ:
# Projects: A (idx=0, cost=10), B (idx=1, cost=1), C (idx=2, cost=5)
# Budget: 11, n=11 voters
# All voters approve {A=0, B=1, C=2}
# Winning set: {C=2} -> winning_util=5 for each voter
#
# T = {A, B}, cohesion: cost*n/budget = 11*11/11 = 11 voters needed -> need all 11
# utility(T) = 11, winning_util = 5
#
# EJR unsat:   5 < 11 -> True  (violation expected)
# EJR_1 unsat: 5 + max(cost(A),cost(B)) = 5 + 10 = 15 >= 11 -> SATISFIED (no violation)
# EJR_X unsat: 5 + min(cost(A),cost(B)) = 5 + 1  = 6  < 11  -> UNSATISFIED (violation!)

costs = [1, 3, 8, 9, 10]  # A=10, B=1, C=5
budget = 12
# n_voters = 3
approvals = [set({0, 2, 3}), set({0, 1, 3, 4}), set({0, 3})]
winning_set = {1}  # only C funded

projects = [Project(str(i), costs[i]) for i in range(len(costs))]


def cost_util(project_set, ballot):
    return sum(costs[p] for p in project_set if p in ballot)


r = find_ejr_violation_witness(
    approvals, winning_set, costs, projects, budget, cost_util, verbose=False
)
print("EJR violation:", len(r.witness) > 0)


r1 = find_ejr_1_violation_witness(
    approvals, winning_set, costs, projects, budget, cost_util, verbose=False
)
print("EJR_1 violation:", len(r1.witness) > 0)
for w in r1.witness:
    print("  ", w)
rx = find_ejr_x_violation_witness(
    approvals, winning_set, costs, projects, budget, cost_util, verbose=False
)
print("EJR_X violation:", len(rx.witness) > 0)
for w in rx.witness:
    print("  ", w)

print()
print("Expected: EJR=True, EJR_1=False, EJR_X=True")
