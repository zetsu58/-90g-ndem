"""Safety gate for creative experiments: no automatic escalation on weak evidence."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ExperimentDecision:
    enabled: bool
    reason: str
    exploit_percent: int = 80

def experiment_decision(summary: list[dict], *, minimum_per_arm: int = 10,
                        max_exploit_drop: float = 0.10) -> ExperimentDecision:
    arms={str(r.get("mode")):r for r in summary}
    exploit=arms.get("exploit"); explore=arms.get("explore")
    if not exploit or not explore:
        return ExperimentDecision(True,"insufficient_comparison")
    if min(int(exploit.get("videos") or 0),int(explore.get("videos") or 0)) < minimum_per_arm:
        return ExperimentDecision(True,"insufficient_sample")
    a=exploit.get("avg_score"); b=explore.get("avg_score")
    if a is None or b is None or float(b) <= 0:
        return ExperimentDecision(True,"insufficient_performance")
    if float(a) < float(b)*(1.0-max_exploit_drop):
        return ExperimentDecision(False,"exploit_underperforming",0)
    return ExperimentDecision(True,"within_guardrail",80)
