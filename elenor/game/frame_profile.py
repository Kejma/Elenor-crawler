"""Bounded, opt-in frame telemetry for comparing rendering settings."""
from collections import deque
from pathlib import Path
from time import perf_counter

import numpy as np

from elenor.profile import get_profile_dir


class FrameProfile:
    def __init__(self):
        self.lines = deque(maxlen=24)
        self.samples = []
        self.key = None
        self.label = ""
        self.started = 0.0
        self.active = False
        self.stages = {}

    def begin(self, enabled):
        self.active = enabled
        if enabled:
            self.started = perf_counter()
            self.stages.clear()
        elif self.key is not None:
            self.flush()
            self.key = None
            self.label = ""

    def flush(self):
        if len(self.samples) < 10:
            self.samples.clear()
            return
        columns = {}
        for row in self.samples:
            for name, value in row.items():
                columns.setdefault(name, []).append(value)
        stats = {name: np.percentile(values, [50, 95]) for name, values in columns.items()}
        median, p95 = stats["frame"]
        self.label = f"{median:.1f} ms · p95 {p95:.1f} ms"
        if "gpu" in stats:
            self.label += f" · GPU {stats['gpu'][0]:.1f} ms"
        metrics = " ".join(f"{name}={mid:.1f}/{high:.1f}" for name, (mid, high) in stats.items())
        self.lines.append(f"{self.key} n={len(self.samples)} {metrics}")
        self.samples.clear()
        try:
            path = Path(get_profile_dir()) / "performance.log"
            path.write_text("Milliseconds, median/p95. GPU overlaps CPU stages.\n"
                            + "\n".join(self.lines) + "\n", encoding="utf-8")
        except OSError:
            pass

    def end(self, key, present_start):
        now = perf_counter()
        if key != self.key:
            self.flush()
            self.key = key
            self.window_start = self.started
            self.label = ""
        self.samples.append(dict(frame=(now - self.started) * 1000,
                                 **self.stages, present=(now - present_start) * 1000))
        if now - self.window_start >= 5 or len(self.samples) >= 1200:
            self.flush()
            self.window_start = now
