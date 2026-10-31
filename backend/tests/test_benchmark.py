import json

from fastapi.testclient import TestClient

from app.core import config as C
from app.main import app

client = TestClient(app)

CLAUDE_MD_LAYOUT = {  # CLAUDE.md 3.8.3 example shape, with a "summary" the page must not repeat
    "benchmark_version": "v1", "timestamp": "2026-10-31T14:00:00Z", "dataset": "INCLUDE-subset", "n_classes": 10,
    "seeds": [42, 101, 2024], "frozen_test_samples": 30,
    "strategies": {
        "ranker": {"steps": [0, 5], "macro_f1_mean": [0.3, 0.5], "macro_f1_std": [0.03, 0.04]},
        "balanced_round_robin": {"steps": [0, 5], "macro_f1_mean": [0.3, 0.4], "macro_f1_std": [0.03, 0.03]},
        "random": {"steps": [0, 5], "macro_f1_mean": [0.3, 0.35], "macro_f1_std": [0.03, 0.05]},
    },
    "summary": "ranker wins",
}


def write(obj):
    C.BENCHMARK_PATH.write_text(obj if isinstance(obj, str) else json.dumps(obj))


def test_missing_file_is_not_evaluated_yet():
    C.BENCHMARK_PATH.unlink(missing_ok=True)
    assert client.get("/api/benchmark").status_code == 404


def test_claude_md_layout_is_normalised():
    write(CLAUDE_MD_LAYOUT)
    b = client.get("/api/benchmark").json()
    assert set(b["curves"]) == {"ranker", "balanced", "random"}
    assert b["samples_added"] == [0, 5] and b["metric"] == "macro_f1" and b["frozen_test_samples"] == 30
    assert b["curves"]["balanced"]["mean"] == [0.3, 0.4]
    assert "summary" not in b and b["is_demo"] is False


def test_curves_layout_passes_through():
    raw = {"schema_version": 1, "samples_added": [0, 10], "curves": {"ranker": {"mean": [0.2, 0.4], "std": [0, 0]}}}
    write(raw)
    assert client.get("/api/benchmark").json()["curves"] == raw["curves"]


def test_bad_files_are_rejected_not_shown():
    for bad in ("{not json", {"foo": 1},
                {**CLAUDE_MD_LAYOUT, "strategies": {**CLAUDE_MD_LAYOUT["strategies"],
                                                    "random": {"steps": [0, 9], "macro_f1_mean": [0, 0], "macro_f1_std": [0, 0]}}}):
        write(bad)
        assert client.get("/api/benchmark").status_code == 422
    C.BENCHMARK_PATH.unlink()
