import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from pabutools.election import Instance, Project, ApprovalBallot, ApprovalProfile
from pabutools.rules import sequential_phragmen
from src.main.ejr import find_ejr_violation_witness
from src.main.ejr_1 import find_ejr_1_violation_witness

# Example from the literature: n=24, k=12, C = {a, b, c1,...,c12}
# seq-Phragmén selects S = {c1,...,c12}, which violates EJR.
# Witness: N* = the 4 left voters (2x{a,b,c1}, 2x{a,b,c2}).
# Their intersection contains {a,b} (size 2), |N*|=4=n/k*2, yet no voter in N*
# approves >=2 projects in S.

# --- Project indices ---------------------------------------------------------
# 0=a, 1=b, 2=c1, 3=c2, 4=c3, ..., 13=c12
N_PROJECTS = 14  # a, b, c1..c12
costs = [1] * N_PROJECTS
budget = 12  # k = 12

projects = [Project(name, 1) for name in ["a", "b"] + [f"c{i}" for i in range(1, 13)]]
instance = Instance(projects, budget_limit=budget)

p = {proj.name: proj for proj in projects}

# --- Build approval ballots --------------------------------------------------
pb_ballots = []
for _ in range(2):
    pb_ballots.append(ApprovalBallot([p["a"], p["b"], p["c1"]]))
for _ in range(2):
    pb_ballots.append(ApprovalBallot([p["a"], p["b"], p["c2"]]))
for _ in range(6):
    pb_ballots.append(ApprovalBallot([p[f"c{i}"] for i in range(1, 13)]))
for _ in range(5):
    pb_ballots.append(ApprovalBallot([p[f"c{i}"] for i in range(2, 13)]))
for _ in range(9):
    pb_ballots.append(ApprovalBallot([p[f"c{i}"] for i in range(3, 13)]))

profile = ApprovalProfile(pb_ballots, instance=instance)

assert len(pb_ballots) == 24, f"Expected 24 voters, got {len(pb_ballots)}"

# --- Run seq-Phragmén --------------------------------------------------------
phragmen_result = sequential_phragmen(instance, profile)
phragmen_names = {str(proj) for proj in phragmen_result}

expected_winner_names = {f"c{i}" for i in range(1, 13)}
assert (
    phragmen_names == expected_winner_names
), f"seq-Phragmén should select {{c1,...,c12}}, got {phragmen_names}"
print("seq-Phragmén outcome:", sorted(phragmen_names))

# --- Convert to integer-index representation for the EJR checker -------------
name_to_idx = {proj.name: idx for idx, proj in enumerate(projects)}

approvals = [{name_to_idx[str(proj)] for proj in ballot} for ballot in pb_ballots]
winning_set = {name_to_idx[name] for name in phragmen_names}


def card_util(project_set, ballot):
    return sum(1 for proj in project_set if proj in ballot)


# --- Check EJR-1 violation -----------------------------------------------------
result = find_ejr_1_violation_witness(
    approvals, winning_set, costs, projects, budget, card_util, verbose=True
)

print("\nEJR-1 violation found:", len(result.witness) > 0)
for w in result.witness:
    proj_names = [projects[idx].name for idx in w.p_set]
    print(f"  T = {proj_names}, voters = {w.voters}")

assert len(result.witness) > 0, "Expected an EJR-1 violation but none was found"
print("\nTest passed: seq-Phragmén violates EJR-1 on this instance.")
