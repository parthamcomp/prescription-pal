"""In-process request metrics - request count, error rate, and average
latency. Fine for a single API instance; swap for Prometheus/Datadog
counters if you ever run multiple replicas behind a load balancer.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Metrics:
    request_count: int = 0
    error_count: int = 0
    latency_ms_sum: float = 0.0

    def record(self, latency_ms: float, error: bool = False) -> None:
        self.request_count += 1
        self.latency_ms_sum += latency_ms
        if error:
            self.error_count += 1

    def summary(self) -> dict:
        avg_latency = (
            self.latency_ms_sum / self.request_count if self.request_count else 0.0
        )
        error_rate = self.error_count / self.request_count if self.request_count else 0.0
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": round(error_rate, 4),
            "avg_latency_ms": round(avg_latency, 1),
        }


metrics = Metrics()


@contextmanager
def timed_request():
    """Usage: `with timed_request() as ctx: ...`, then set ctx["error"] =
    True before re-raising on failure so it counts toward the error rate."""
    start = time.perf_counter()
    ctx = {"error": False}
    try:
        yield ctx
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        metrics.record(latency_ms, error=ctx["error"])
