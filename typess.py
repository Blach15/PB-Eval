class EJRViolationWitness:
    def __init__(self, p_set: set[int] | frozenset[int], voters: set[int]):
        self.p_set = p_set
        self.voters = voters

    def __str__(self):
        return f"p_set_size: {len(self.p_set)}, p_set: {self.p_set}, support_count: {len(self.voters)}"


class EJRViolationResult:
    def __init__(
        self,
        witness: EJRViolationWitness | None,
        p_sets_checked: int,
    ):
        self.witness = witness
        self.p_sets_checked = p_sets_checked
