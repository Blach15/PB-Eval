from pabutools.election import Project, Instance, ApprovalBallot, ApprovalProfile, Cost_Sat, parse_pabulib
from pabutools.rules import greedy_utilitarian_welfare, sequential_phragmen, method_of_equal_shares
from pabutools.visualisation import GreedyWelfareVisualiser, MESVisualiser
import os

def visualise_election(filename=str, sat_class=Cost_Sat, rule="greedy", verbose=False):
    path = os.path.join("./elections/", filename)
    if verbose:
        print(f"Parsing election instance from {path}...")
    instance, profile = parse_pabulib(path)
    if rule == "greedy":
        if verbose:
            print("Computing outcome using greedy utilitarian welfare...")
        outcome = greedy_utilitarian_welfare(instance, profile, sat_class=sat_class, analytics=True)
        visualiser = GreedyWelfareVisualiser(profile, instance, outcome)
        if verbose:
            print("Rendering visualisation...")
        visualiser.render("./output/", name=os.path.basename(path).split(".")[0] + "_greedy_utilitarian_welfare")
        if verbose:
            print("Visualisation complete.")
    elif rule == "mes":
        if verbose:
            print("Computing outcome using method of equal shares...")
        outcome = method_of_equal_shares(instance, profile, sat_class=sat_class, analytics=True)
        visualiser = MESVisualiser(profile, instance, outcome)
        if verbose:
            print("Rendering visualisation...")
        visualiser.render("./output/", name=os.path.basename(path).split(".")[0] + "_method_of_equal_shares")
        if verbose:
            print("Visualisation complete.")
    else:
        raise ValueError(f"Unknown rule: {rule}")

visualise_election("netherlands_amsterdam_252_.pb", sat_class=Cost_Sat, rule="greedy", verbose=True)
visualise_election("netherlands_amsterdam_252_.pb", sat_class=Cost_Sat, rule="mes", verbose=True)




