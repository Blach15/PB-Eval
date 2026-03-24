from pabutools.election import Project, Instance, ApprovalBallot, ApprovalProfile, Cost_Sat
from pabutools.rules import greedy_utilitarian_welfare, sequential_phragmen, method_of_equal_shares
from pabutools.visualisation import GreedyWelfareVisualiser

p1 = Project("p1", 1) 
p2 = Project("p2", 1)
p3 = Project("p3", 3)

instance = Instance()
instance.add(p1)
instance.update([p2, p3])

instance.budget_limit = 3

b1 = ApprovalBallot([p1, p2])
b1.add(p2)
b2 = ApprovalBallot({p1, p2, p3})
b3 = ApprovalBallot({p3})

profile = ApprovalProfile([b1, b2])
profile.append(b3)

outcome1 = greedy_utilitarian_welfare(instance, profile, sat_class=Cost_Sat)

print("Greedy Utilitarian Welfare Outcome:", outcome1)

visualiser = GreedyWelfareVisualiser(profile, instance, outcome1)

visualiser.render("./t/", name="test")





