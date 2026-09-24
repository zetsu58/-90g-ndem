"""Runtime policy composed from experiment history and safety guardrails."""
from .experiment_store import ExperimentStore
from .experiment_safety import experiment_decision

def safe_exploit_percent(db_path: str, channel: str) -> int:
    try:
        with ExperimentStore(db_path) as store:
            decision=experiment_decision(store.summary(channel))
        return decision.exploit_percent if decision.enabled else 0
    except Exception:
        return 0
