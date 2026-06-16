import yaml


class Config:

    def __init__(self, file):
        with open(file) as f:
            self.data = yaml.safe_load(f)

    def get(self, *keys):
        value = self.data

        for key in keys:
            value = value[key]

        return value
