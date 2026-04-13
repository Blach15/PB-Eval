class EJRViolationWitness:
    def __init__(self, p_set: set[int] | frozenset[int], voters: set[int]):
        self.p_set = p_set
        self.voters = voters
