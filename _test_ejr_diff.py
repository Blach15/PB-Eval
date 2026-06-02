from ejr import (
    find_ejr_1_violation_witness,
    find_ejr_x_violation_witness,
    find_ejr_violation_witness,
)
from pabutools.election import Project

# Crafted example where EJR_1 and EJR_X SHOULD differ:

costs = [4, 4, 4, 5, 1]  # A=10, B=1, C=5
budget = 12
# n_voters = 3
approvals = [set({0, 3, 4}), set({1, 3, 4}), set({2, 3, 4})]
winning_set = {0,1,2}  # only C funded

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
    print(
        "  Projects:",
        w.p_set,
        "Costs:",
        [costs[p] for p in w.p_set],
        "Voters:",
        w.voters,
    )
rx = find_ejr_x_violation_witness(
    approvals, winning_set, costs, projects, budget, cost_util, verbose=False
)
print("EJR_X violation:", len(rx.witness) > 0)
for w in rx.witness:
    print(
        "  Projects:",
        w.p_set,
        "Costs:",
        [costs[p] for p in w.p_set],
        "Voters:",
        w.voters,
    )

print()
print("Expected: EJR=True, EJR_1=False, EJR_X=True")
