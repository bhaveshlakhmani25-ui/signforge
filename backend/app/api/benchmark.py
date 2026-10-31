import json

from fastapi import APIRouter, HTTPException

from app.core import config as C

router = APIRouter(prefix="/api/benchmark")

STRATEGY_KEYS = {"ranker": "ranker", "balanced_round_robin": "balanced", "balanced": "balanced", "random": "random"}


def normalise(raw: dict) -> dict:
    """Both benchmark layouts in circulation -> the one the Evidence page reads.
    A: CLAUDE.md 3.8.3 (strategies.{ranker,balanced_round_robin,random}.steps/macro_f1_mean/macro_f1_std).
    B: redesign brief / schema_version 1 (curves.{name}.mean/std, samples_added, before_after)."""
    if "curves" in raw:
        if not raw.get("samples_added") or any(len(c["mean"]) != len(raw["samples_added"]) for c in raw["curves"].values()):
            raise ValueError("every curve needs one mean/std value per samples_added step")
        return raw
    if "strategies" not in raw:
        raise ValueError("expected 'strategies' or 'curves'")
    curves, steps, metric = {}, None, None
    for name, s in raw["strategies"].items():
        metric = metric or ("macro_f1" if "macro_f1_mean" in s else "accuracy")
        mean, std = s[f"{metric}_mean"], s[f"{metric}_std"]
        if steps is None:
            steps = s["steps"]
        if s["steps"] != steps or len(mean) != len(steps) or len(std) != len(steps):
            raise ValueError(f"strategy '{name}' does not share the same steps as the others")
        curves[STRATEGY_KEYS.get(name, name)] = {"mean": mean, "std": std}
    # raw["summary"] is deliberately not passed on: the page computes its verdict from the numbers.
    return {
        "schema_version": 1, "generated_at": raw.get("timestamp", ""), "is_demo": bool(raw.get("is_demo", False)),
        "dataset": {"name": raw.get("dataset", "not stated"), "n_signs": raw.get("n_classes"),
                    "split": raw.get("split", "not stated"), "source": raw.get("source", "not stated")},
        "protocol": raw.get("protocol", "not stated"), "metric": metric, "seeds": raw.get("seeds", []),
        "samples_added": steps, "frozen_test_samples": raw.get("frozen_test_samples"), "curves": curves,
        "before_after": raw.get("before_after"), "transfer": raw.get("transfer"), "notes": raw.get("notes"),
    }


@router.get("")
def get_benchmark():
    if not C.BENCHMARK_PATH.exists():
        raise HTTPException(404, "Not evaluated yet: no benchmark file has been produced.")
    try:
        return normalise(json.loads(C.BENCHMARK_PATH.read_text()))
    except (ValueError, KeyError, TypeError) as e:  # JSONDecodeError is a ValueError
        raise HTTPException(422, f"The benchmark file is not in a known format: {e}")
