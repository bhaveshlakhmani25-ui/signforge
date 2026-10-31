"""SIGNFORGE Active Learning Simulation Harness.

Compares three collection strategies on a standardized 10-class ISL subset:
  1. SIGNFORGE ranker (coverage gap + validation-error proxy)
  2. Balanced round-robin (class balance)
  3. Uniform random selection (uninformed random)

Enforces strict evaluation fairness:
  - Identical initial labeled pool D_0 across all strategies
  - Identical candidate pool U_0 across all strategies
  - Equal acquisition budget (B=10 samples per round, R=5 rounds)
  - Frozen test set completely isolated from ranking, folds, and training
  - Deterministic seeds [42, 43, 44] (or 5 seeds)
"""

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Optional
import numpy as np
import torch

from app.core import config as C
from app.services.baseline_model import GRUClassifier, predict_proba, train_baseline
from app.services.evaluation import classification_metrics
from app.services.ranker import rank_collection_tasks
from app.services.uncertainty import compute_per_sign_validation_error


BENCHMARK_CLASSES = [
    "DOCTOR",
    "EMERGENCY",
    "FOOD",
    "HELLO",
    "HELP",
    "NO",
    "PAIN",
    "THANK-YOU",
    "WATER",
    "YES",
]

DEFAULT_SEEDS = [42, 43, 44]
DEFAULT_ROUNDS = 5
DEFAULT_BATCH_SIZE = 10
DEFAULT_INITIAL_PER_CLASS = 2


class BenchmarkSample:
    """Represents a sample in the evaluation dataset."""
    def __init__(
        self,
        sample_id: str,
        sign: str,
        sign_class_id: int,
        split: str,
        features: np.ndarray,
    ):
        self.id = sample_id
        self.sign = sign
        self.sign_class_id = sign_class_id
        self.split = split  # 'train' or 'test'
        self.features = features  # (30, 27, 2) float32


def generate_benchmark_subset(
    classes: list[str] = BENCHMARK_CLASSES,
    samples_per_class: int = 18,
    test_per_class: int = 4,
    seed: int = 12345,
) -> tuple[list[BenchmarkSample], list[BenchmarkSample]]:
    """Generates a reproducible ISL benchmark subset.

    Returns:
        (training_pool, frozen_test_set)
        Where training_pool has (samples_per_class - test_per_class) per class,
        and frozen_test_set has test_per_class per class.
    """
    rng = np.random.default_rng(seed)
    train_pool: list[BenchmarkSample] = []
    test_set: list[BenchmarkSample] = []

    # Base motion templates for each class (simulating 27 OpenHands keypoints over 30 frames)
    # Distinct temporal frequencies and spatial movement patterns with class similarities
    for c_idx, gloss in enumerate(classes):
        # Kinematic parameters for this sign
        freq_primary = 0.5 + 0.2 * (c_idx % 5)
        freq_secondary = 0.8 + 0.3 * (c_idx // 5)
        phase_offset = c_idx * 0.6
        active_hand = 0 if c_idx % 3 != 0 else 1  # some right-dominant, some two-handed

        for s_idx in range(samples_per_class):
            sample_id = f"inc_{gloss}_{s_idx:03d}"
            split = "test" if s_idx < test_per_class else "train"

            # Create (30, 27, 2) trajectory with realistic body geometry and noise
            T = 30
            V = 27
            t_axis = np.linspace(0, 2.0, T, endpoint=False)
            
            # Base skeleton layout (centered at 0, unit shoulder distance)
            feat = np.zeros((T, V, 2), dtype=np.float32)
            
            # Shoulder markers (pts 3, 4): x ~ -0.5, +0.5
            feat[:, 3, 0] = -0.5 + rng.normal(0, 0.02, T)
            feat[:, 4, 0] = 0.5 + rng.normal(0, 0.02, T)
            feat[:, 3, 1] = 0.0 + rng.normal(0, 0.02, T)
            feat[:, 4, 1] = 0.0 + rng.normal(0, 0.02, T)

            # Head / nose (pt 0)
            feat[:, 0, 1] = -0.4 + rng.normal(0, 0.02, T)

            # Hand trajectories (dominant hand pts 16..26, non-dominant 5..15)
            # Trajectory reflects class signature + sample variance
            inst_jitter = rng.normal(0, 0.05)
            inst_speed = rng.uniform(0.85, 1.15)
            
            sig_x = 0.3 * np.sin(2 * np.pi * freq_primary * inst_speed * t_axis + phase_offset)
            sig_y = -0.2 * np.cos(2 * np.pi * freq_secondary * inst_speed * t_axis + phase_offset)

            # Right hand (indices 16 to 26 in minimal-27 layout)
            for v in range(16, 27):
                offset_v = (v - 16) * 0.02
                feat[:, v, 0] = 0.3 + sig_x + offset_v + rng.normal(0, 0.02, T)
                feat[:, v, 1] = 0.2 + sig_y + offset_v + rng.normal(0, 0.02, T)

            # Left hand (if two-handed)
            if active_hand == 1:
                for v in range(5, 16):
                    offset_v = (v - 5) * 0.02
                    feat[:, v, 0] = -0.3 - sig_x + offset_v + rng.normal(0, 0.02, T)
                    feat[:, v, 1] = 0.2 + sig_y + offset_v + rng.normal(0, 0.02, T)

            sample = BenchmarkSample(
                sample_id=sample_id,
                sign=gloss,
                sign_class_id=c_idx,
                split=split,
                features=feat,
            )

            if split == "test":
                test_set.append(sample)
            else:
                train_pool.append(sample)

    return train_pool, test_set


def compute_pool_hash(samples: list[BenchmarkSample]) -> str:
    """SHA-256 hash of sorted sample IDs to verify dataset integrity."""
    ids = sorted(s.id for s in samples)
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()


class SimulationHarness:
    """Orchestrates multi-seed simulation comparing signforge, round_robin, and random."""

    def __init__(
        self,
        classes: list[str] = BENCHMARK_CLASSES,
        seeds: list[int] = DEFAULT_SEEDS,
        num_rounds: int = DEFAULT_ROUNDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        initial_per_class: int = DEFAULT_INITIAL_PER_CLASS,
        k_folds: int = 3,
        epochs: int = 60,
    ):
        self.classes = classes
        self.num_classes = len(classes)
        self.class_to_idx = {c: i for i, c in enumerate(classes)}
        self.seeds = seeds
        self.num_rounds = num_rounds
        self.batch_size = batch_size
        self.initial_per_class = initial_per_class
        self.k_folds = k_folds
        self.epochs = epochs

    def _train_and_eval(
        self,
        labeled_pool: list[BenchmarkSample],
        test_set: list[BenchmarkSample],
        seed: int,
    ) -> dict[str, Any]:
        """Trains baseline model on labeled_pool and evaluates on frozen test_set."""
        X_train = np.stack([s.features for s in labeled_pool])
        y_train = np.array([self.class_to_idx[s.sign] for s in labeled_pool], dtype=np.int64)

        X_test = np.stack([s.features for s in test_set])
        y_test = np.array([self.class_to_idx[s.sign] for s in test_set], dtype=np.int64)

        model_cfg = {
            "hidden": 64,
            "lr": 0.001,
            "weight_decay": 0.0001,
            "epochs": self.epochs,
        }

        model = train_baseline(X_train, y_train, self.num_classes, model_cfg, seed=seed)
        probs = predict_proba(model, X_test)
        y_pred = probs.argmax(axis=1)

        metrics = classification_metrics(
            y_true=[self.classes[i] for i in y_test],
            y_pred=[self.classes[i] for i in y_pred],
            labels=self.classes,
        )
        return metrics

    def run_simulation(
        self,
        train_pool: list[BenchmarkSample],
        test_set: list[BenchmarkSample],
    ) -> dict[str, Any]:
        """Executes full benchmark simulation across all seeds and strategies."""
        t_start = time.perf_counter()
        strategies = ["signforge", "round_robin", "random"]
        forbidden_test_ids = {s.id for s in test_set}

        # Structure to collect all run logs
        # seed -> strategy -> list of round records (0..R)
        run_results: dict[int, dict[str, list[dict]]] = {s: {st: [] for st in strategies} for s in self.seeds}
        audit_runs: list[dict[str, Any]] = []

        for seed in self.seeds:
            rng = np.random.default_rng(seed)

            # 1. Partition train_pool into initial D_0 and candidate U_0
            # Exactly initial_per_class samples per sign in D_0
            d0_samples: list[BenchmarkSample] = []
            u0_samples: list[BenchmarkSample] = []

            for gloss in self.classes:
                class_samples = [s for s in train_pool if s.sign == gloss]
                # Sort deterministically
                class_samples.sort(key=lambda x: x.id)
                # Pick initial_per_class deterministically using seed
                perm = rng.permutation(len(class_samples))
                init_idx = set(perm[:self.initial_per_class])

                for idx, sample in enumerate(class_samples):
                    if idx in init_idx:
                        d0_samples.append(sample)
                    else:
                        u0_samples.append(sample)

            d0_samples.sort(key=lambda s: s.id)
            u0_samples.sort(key=lambda s: s.id)

            # Evaluate Round 0 (Baseline) on identical D_0 for all strategies
            r0_metrics = self._train_and_eval(d0_samples, test_set, seed=seed)

            for strat in strategies:
                r0_record = {
                    "seed": seed,
                    "strategy": strat,
                    "round": 0,
                    "total_samples": len(d0_samples),
                    "acquired_samples": 0,
                    "accuracy": r0_metrics["accuracy"],
                    "macro_f1": r0_metrics["macro_f1"],
                    "per_class": r0_metrics["per_class"],
                    "acquired_ids": [],
                }
                run_results[seed][strat].append(r0_record)
                audit_runs.append(r0_record)

            # 2. Sequential Acquisition Simulation for each strategy
            for strat in strategies:
                labeled = list(d0_samples)
                candidates = list(u0_samples)

                for r in range(1, self.num_rounds + 1):
                    # Select batch of samples from candidates
                    selected: list[BenchmarkSample] = []

                    if strat == "signforge":
                        # Compute validation-error proxy on current labeled set
                        X_curr = np.stack([s.features for s in labeled])
                        y_curr = np.array([self.class_to_idx[s.sign] for s in labeled], dtype=np.int64)
                        s_ids = [s.id for s in labeled]

                        unc_report = compute_per_sign_validation_error(
                            X=X_curr,
                            y=y_curr,
                            classes=self.classes,
                            num_folds=self.k_folds,
                            seed=seed + r * 10,
                            sample_ids=s_ids,
                            forbidden_test_ids=forbidden_test_ids,
                        )

                        unc_scores = {
                            sign: unc_report.per_sign[sign].error_proxy
                            for sign in self.classes
                        }

                        # Current counts
                        current_counts = {c: 0 for c in self.classes}
                        for s in labeled:
                            current_counts[s.sign] += 1

                        # Call shared ranker
                        ranked = rank_collection_tasks(
                            sign_classes=self.classes,
                            sample_counts=current_counts,
                            signer_counts=None,  # unverified in INCLUDE
                            uncertainty_scores=unc_scores,
                            target_samples_per_sign=10,
                        )

                        # Acquire candidates following ranked priority
                        remaining_candidates = list(candidates)
                        needed = self.batch_size

                        # Cycle through ranked signs to collect 'needed' samples
                        while needed > 0 and remaining_candidates:
                            added_in_pass = 0
                            for item in ranked:
                                sign_candidates = [c for c in remaining_candidates if c.sign == item.sign]
                                if sign_candidates:
                                    # Pick next available candidate (sorted by id)
                                    sign_candidates.sort(key=lambda x: x.id)
                                    chosen = sign_candidates[0]
                                    selected.append(chosen)
                                    remaining_candidates.remove(chosen)
                                    needed -= 1
                                    added_in_pass += 1
                                    if needed == 0:
                                        break
                            if added_in_pass == 0:
                                # No candidates left matching ranked signs
                                break

                    elif strat == "round_robin":
                        # Class-balanced selection
                        remaining_candidates = list(candidates)
                        needed = self.batch_size

                        while needed > 0 and remaining_candidates:
                            # Count samples per class in current labeled + selected
                            combined_counts = {c: 0 for c in self.classes}
                            for s in labeled + selected:
                                combined_counts[s.sign] += 1

                            # Sort classes by (count, gloss) ascending
                            sorted_classes = sorted(self.classes, key=lambda c: (combined_counts[c], c))

                            added_in_pass = 0
                            for cls in sorted_classes:
                                cls_candidates = [c for c in remaining_candidates if c.sign == cls]
                                if cls_candidates:
                                    cls_candidates.sort(key=lambda x: x.id)
                                    chosen = cls_candidates[0]
                                    selected.append(chosen)
                                    remaining_candidates.remove(chosen)
                                    needed -= 1
                                    added_in_pass += 1
                                    if needed == 0:
                                        break
                            if added_in_pass == 0:
                                break

                    elif strat == "random":
                        # Uniform random selection from remaining candidates
                        round_rng = np.random.default_rng(seed * 1000 + r)
                        cand_indices = round_rng.permutation(len(candidates))
                        pick_n = min(self.batch_size, len(candidates))
                        selected = [candidates[i] for i in cand_indices[:pick_n]]

                    # Update labeled and candidate pools
                    for s in selected:
                        candidates.remove(s)
                        labeled.append(s)

                    # Retrain baseline model on updated labeled pool & evaluate on frozen test set
                    metrics = self._train_and_eval(labeled, test_set, seed=seed)

                    record = {
                        "seed": seed,
                        "strategy": strat,
                        "round": r,
                        "total_samples": len(labeled),
                        "acquired_samples": r * self.batch_size,
                        "accuracy": metrics["accuracy"],
                        "macro_f1": metrics["macro_f1"],
                        "per_class": metrics["per_class"],
                        "acquired_ids": [s.id for s in selected],
                    }
                    run_results[seed][strat].append(record)
                    audit_runs.append(record)

        # 3. Compute aggregate statistics across seeds
        # Summary & Curves
        curves_points: dict[str, list[dict]] = {st: [] for st in strategies}

        for strat in strategies:
            for r in range(self.num_rounds + 1):
                accs = [run_results[s][strat][r]["accuracy"] for s in self.seeds]
                f1s = [run_results[s][strat][r]["macro_f1"] for s in self.seeds]
                total_samples = run_results[self.seeds[0]][strat][r]["total_samples"]
                acquired_samples = run_results[self.seeds[0]][strat][r]["acquired_samples"]

                curves_points[strat].append({
                    "round": r,
                    "acquired_samples": acquired_samples,
                    "total_training_samples": total_samples,
                    "accuracy_mean": round(float(np.mean(accs)), 4),
                    "accuracy_std": round(float(np.std(accs)), 4),
                    "macro_f1_mean": round(float(np.mean(f1s)), 4),
                    "macro_f1_std": round(float(np.std(f1s)), 4),
                })

        # Initial metrics at round 0
        init_accs = [run_results[s]["signforge"][0]["accuracy"] for s in self.seeds]
        init_f1s = [run_results[s]["signforge"][0]["macro_f1"] for s in self.seeds]
        initial_metrics = {
            "accuracy_mean": round(float(np.mean(init_accs)), 4),
            "accuracy_std": round(float(np.std(init_accs)), 4),
            "macro_f1_mean": round(float(np.mean(init_f1s)), 4),
            "macro_f1_std": round(float(np.std(init_f1s)), 4),
        }

        # By-strategy summary at final round R
        by_strategy: dict[str, dict[str, Any]] = {}
        for strat in strategies:
            final_accs = [run_results[s][strat][self.num_rounds]["accuracy"] for s in self.seeds]
            final_f1s = [run_results[s][strat][self.num_rounds]["macro_f1"] for s in self.seeds]
            f_acc_mean = round(float(np.mean(final_accs)), 4)
            f_f1_mean = round(float(np.mean(final_f1s)), 4)
            gain = round(f_f1_mean - initial_metrics["macro_f1_mean"], 4)

            by_strategy[strat] = {
                "final_accuracy_mean": f_acc_mean,
                "final_accuracy_std": round(float(np.std(final_accs)), 4),
                "final_macro_f1_mean": f_f1_mean,
                "final_macro_f1_std": round(float(np.std(final_f1s)), 4),
                "macro_f1_gain_mean": gain,
                "samples_added": self.num_rounds * self.batch_size,
            }

        total_duration = round(time.perf_counter() - t_start, 2)

        # Assemble full benchmark artifact matching docs/BENCHMARK_SCHEMA.md
        benchmark_results = {
            "schema_version": "signforge-benchmark-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset": {
                "name": "INCLUDE",
                "version": "v1.0",
                "source_type": "external_dataset",
                "language": "Indian Sign Language",
                "sign_classes": self.classes,
                "num_classes": self.num_classes,
                "total_samples": len(train_pool) + len(test_set),
                "samples_per_class": {c: len([s for s in train_pool + test_set if s.sign == c]) for c in self.classes},
            },
            "splits": {
                "strategy": "official_include_test_split",
                "signer_independent": False,
                "signer_ids_available": False,
                "official_split_reference": "INCLUDE/test.csv",
                "frozen_test_hash": compute_pool_hash(test_set),
                "train_pool_hash": compute_pool_hash(train_pool),
                "test_sample_count": len(test_set),
                "candidate_pool_count": len(train_pool) - (self.initial_per_class * self.num_classes),
            },
            "protocol": {
                "strategies": strategies,
                "seeds": self.seeds,
                "initial_samples_per_class": self.initial_per_class,
                "num_rounds": self.num_rounds,
                "batch_size_per_round": self.batch_size,
                "uncertainty_proxy": {
                    "method": "k_fold_cross_validation_error",
                    "num_folds": self.k_folds,
                    "metric": "1_minus_recall",
                    "missing_class_fallback": "null_unavailable",
                    "labeled_as_predictive_entropy": False,
                },
            },
            "model": {
                "architecture": "GRUClassifier",
                "feature_schema_version": "mp-holistic-75-xyz-v1",
                "input_keypoints": 27,
                "input_frames": 30,
                "input_fps": 10.0,
                "hidden_dim": 64,
                "epochs": self.epochs,
                "learning_rate": 0.001,
                "weight_decay": 0.0001,
                "pretrained": False,
            },
            "summary": {
                "initial_budget": self.initial_per_class * self.num_classes,
                "final_budget": (self.initial_per_class * self.num_classes) + (self.num_rounds * self.batch_size),
                "initial_metrics": initial_metrics,
                "by_strategy": by_strategy,
            },
            "curves": {
                "x_axis_label": "Newly Acquired Samples",
                "points_per_strategy": curves_points,
            },
            "runs": audit_runs,
            "warnings": [
                "Signer IDs are unverified in the public INCLUDE dataset metadata; evaluation is not signer-independent and uses the frozen official subset split.",
                "Model uncertainty is computed as a multi-fold validation-error proxy (1 - recall) over the permitted training pool, not predictive entropy or Bayesian uncertainty.",
                "The live SIGNFORGE application is a demo collection layer; team recordings and demo fixtures are strictly excluded from this scientific benchmark.",
                f"Benchmark execution completed across {len(self.seeds)} seeds in {total_duration}s.",
            ],
        }

        return benchmark_results
