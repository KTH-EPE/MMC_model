from itertools import product


class ParameterSweep:

    def __init__(
            self,
            parameters
    ):
        self.parameters = parameters

    def combinations(self):
        keys = self.parameters.keys()

        values = self.parameters.values()

        for combination in product(*values):
            yield dict(
                zip(keys, combination)
            )
