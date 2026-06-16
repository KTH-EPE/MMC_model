class ConfigDCGridComponents:

    def __init__(self, components):

        self.R = components["R"]
        self.L = components["L"]
        self.C = components.get("C")

    def set_dc_network(
            self,
            R=None,
            L=None,
            C=None
    ):

        if R:
            self.R.parameters(R=R)

        if L:
            self.L.parameters(L=L)

        if C:
            self.C.parameters(C=C)
