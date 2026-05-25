class MetricResult(dict):
    @classmethod
    def make(cls, name, score, details=None):
        return cls(name=name, score=float(score), details=details or {})


class BaseMetric:
    name = "base"

    def compute(self, frames, config, context=None):
        raise NotImplementedError
