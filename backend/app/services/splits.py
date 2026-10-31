"""Frozen test split. Once a sample is in `test` it stays there, and a sample that was trained on never moves to `test`."""
import re
from collections import defaultdict

import numpy as np

from app.core import config as C

SIGNER_INDEPENDENT = "signer-independent: all samples of held-out signer(s) form the test set"
RANDOM_CLIP = "random clip split, stratified by class (NOT signer-independent)"


def assign_splits(samples: list[dict], seed: int = C.SEED) -> tuple[dict[int, str], str | None]:
    """samples: dicts with id, signer_id, sign_class_id, split. Returns ({id: new_split} for changed samples, strategy).

    Strategy is None when the test set was already frozen by an earlier run (caller keeps the earlier strategy).
    New clips from a held-out signer stay `unassigned`, so a signer-independent test stays signer-independent.
    """
    rng = np.random.default_rng(seed)
    new = [s for s in samples if s["split"] == "unassigned"]
    trained_signers = {s["signer_id"] for s in samples if s["split"] == "train"}
    changes: dict[int, str] = {}
    strategy = None
    if not any(s["split"] == "test" for s in samples):
        # only signers never trained on can be held out, and only new (never trained) clips can become test
        candidates = sorted({s["signer_id"] for s in new} - trained_signers)
        if len({s["signer_id"] for s in samples}) >= C.MIN_SIGNERS_FOR_SIGNER_SPLIT and candidates:
            # hold out the candidate covering the most classes, so the test set tests as many signs as possible
            coverage = {sg: len({s["sign_class_id"] for s in new if s["signer_id"] == sg}) for sg in candidates}
            held_out = int(rng.choice([sg for sg in candidates if coverage[sg] == max(coverage.values())]))
            changes |= {s["id"]: "test" for s in new if s["signer_id"] == held_out}
            strategy = SIGNER_INDEPENDENT
        else:
            by_class = defaultdict(list)
            for s in new:
                by_class[s["sign_class_id"]].append(s["id"])
            for ids in by_class.values():
                if len(ids) >= 2:  # a class with one sample stays in train so it can be learned at all
                    k = max(1, round(len(ids) * C.TEST_FRACTION))
                    changes |= {int(i): "test" for i in rng.choice(sorted(ids), k, replace=False)}
            strategy = RANDOM_CLIP
    test_signers = {s["signer_id"] for s in samples if changes.get(s["id"], s["split"]) == "test"}
    signer_independent = (strategy == SIGNER_INDEPENDENT if strategy else not test_signers & trained_signers)
    for s in new:
        if s["id"] not in changes and not (signer_independent and s["signer_id"] in test_signers):
            changes[s["id"]] = "train"
    return changes, strategy


SESSION_GROUPED = ("session-grouped split: whole recording sessions (inferred from camera file numbers) held out per sign; "
                   "signer identity unknown, so NOT confirmed signer-independent")


def session_groups(samples: list[dict], gap: int = 2) -> dict[int, int]:
    """INCLUDE clips of one sign come in runs of consecutive camera numbers (MVI_0029..MVI_0032 = one sitting).
    Returns {sample id: group index}; a jump of more than `gap` starts a new group. Unnumbered clips get their own group."""
    num = {}
    for s in samples:
        m = re.search(r"(\d+)", s.get("external_sample_id") or "")
        num[s["id"]] = int(m.group(1)) if m else None
    groups, g, last = {}, -1, None
    for sid in sorted((i for i in num if num[i] is not None), key=lambda i: (num[i], i)):
        if last is None or num[sid] - last > gap:
            g += 1
        groups[sid], last = g, num[sid]
    for sid in (i for i in num if num[i] is None):
        g += 1
        groups[sid] = g
    return groups


def assign_grouped_splits(samples: list[dict], seed: int = C.SEED) -> tuple[dict[int, str], str | None]:
    """External datasets: per sign, hold out whole session groups as frozen `test` and `val`, the rest `train`.
    Once a test set exists it stays frozen; new clips only ever go to `train`. Signs with too few groups stay all-train."""
    if any(s["split"] == "test" for s in samples):
        return {s["id"]: "train" for s in samples if s["split"] == "unassigned"}, None
    rng = np.random.default_rng(seed)
    changes: dict[int, str] = {}
    by_class = defaultdict(list)
    for s in samples:
        by_class[s["sign_class_id"]].append(s)
    held = C.EXTERNAL_TEST_GROUPS_PER_SIGN + C.EXTERNAL_VAL_GROUPS_PER_SIGN
    for cls in sorted(by_class):
        rows = by_class[cls]
        groups = session_groups(rows)
        ids = sorted(set(groups.values()))
        order = [int(i) for i in rng.permutation(ids)] if len(ids) > held else []
        test_g = set(order[:C.EXTERNAL_TEST_GROUPS_PER_SIGN])
        val_g = set(order[C.EXTERNAL_TEST_GROUPS_PER_SIGN:held])
        for s in rows:
            changes[s["id"]] = "test" if groups[s["id"]] in test_g else "val" if groups[s["id"]] in val_g else "train"
    return changes, SESSION_GROUPED
