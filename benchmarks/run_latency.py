#!/usr/bin/env python3
"""Latency benchmark harness — mock mode works without Ollama."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass


@dataclass
class LatencySample:
    run: int
    latency_ms: float


def mock_generate() -> float:
    time.sleep(0.01)
    return 10.0


def ollama_generate(model: str) -> float:
    from slm.models.base import human_message
    from slm.models.ollama import create_ollama_model

    llm = create_ollama_model(model)
    started = time.perf_counter()
    llm.generate([human_message("Reply with exactly: ok")])
    return (time.perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description="SLM latency benchmark")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    samples: list[LatencySample] = []
    for i in range(args.runs):
        if args.mock:
            ms = mock_generate()
        else:
            ms = ollama_generate(args.model)
        samples.append(LatencySample(run=i + 1, latency_ms=ms))

    latencies = [s.latency_ms for s in samples]
    report = {
        "mode": "mock" if args.mock else "ollama",
        "runs": args.runs,
        "p50_ms": statistics.median(latencies),
        "mean_ms": statistics.mean(latencies),
        "samples": [asdict(s) for s in samples],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
