# SIGNFORGE Simulation Protocol

**Document Version:** 1.1.0  
**Author:** ML & Evaluation Engineering (Ruben Raju)  
**Status:** Aligned Specification (Step 1 Deliverable — Pre-Implementation)  
**Target Milestone:** Milestone 6 (Corpus Benchmark & Active Learning Validation)

---

## 1. Executive Summary & Objective

SIGNFORGE is a data-generation and model-adaptation workbench for low-resource sign languages—not a sign-language translator.

The core scientific and engineering claim being evaluated is:
> **A model-informed collection strategy improves downstream sign recognition accuracy and macro-F1 with fewer newly collected examples than random or balanced round-robin collection.**

This protocol specifies a strictly controlled, reproducible offline simulation to benchmark three collection strategies on a standardized Indian Sign Language (ISL) subset from the AI4Bharat INCLUDE dataset. The live SIGNFORGE application is a demo and collection layer; team recordings and synthetic demo data are not validated ISL evidence and are strictly excluded from scientific benchmark reporting.

---

## 2. Dataset & Split Specification

### 2.1 Primary Benchmark Dataset: INCLUDE Subset
- **Dataset:** AI4Bharat INCLUDE (Indian Sign Language Dataset).
- **Source Designation & Mismatch Note:**
  - In this protocol and the benchmark artifact, the source type is designated as `external_dataset` to guarantee strict isolation from `captured` (live demo) and `demo_fixture` (synthetic) samples.
  - *Contract Mismatch Note for Tashvi & Bhavesh:* The existing codebase (`backend/app/db/models.py` and `frontend/lib/api.ts`) defines sample sources as `"captured" | "public_dataset" | "demo_fixture"`. We propose that Tashvi and Bhavesh approve either adding `"external_dataset"` to the schema or mapping offline benchmark samples to `"public_dataset"` with a provenance tag (`provenance_note: "AI4Bharat INCLUDE external benchmark"`).
- **Target Vocabulary Size:** 10 to 20 sign classes selected based on minimum sample support.
  - *Eligibility threshold:* Each selected sign class must have sufficient non-test examples to support an initial labeled training pool, multiple acquisition rounds, and cross-validation folds.
  - If fewer than 10 signs meet the threshold, the simulation scope is reduced to the available valid signs and explicitly recorded in the benchmark output. Synthetic demo data is **never** substituted.

### 2.2 Signer Identity & Split Independence
- **Signer ID Audit:** Public INCLUDE metadata does not provide verified, per-clip individual signer identifiers.
- **Honesty Rule:** Because signer IDs cannot be independently verified, results from this benchmark **must not be claimed or reported as signer-independent**.
- **Official Test Split:**
  - The simulation **must use the official INCLUDE test split** as the frozen test set whenever official split files (e.g., `test.csv` / official benchmark fold partitions) are available for the selected subset.
  - *Proposed Fallback Deviation:* If official split metadata cannot be retrieved or mapped for the chosen subset, a deterministic class-stratified holdout split (20% of samples per class) is defined as a fallback. This fallback is explicitly labeled in the output as a **proposed deviation requiring Tashvi's signoff** and will not be adopted silently.
- **Split Naming:** Explicitly documented as `official_include_test_split` (or `proposed_stratified_fallback`), never `signer_independent`.

### 2.3 Frozen Evaluation Test Set
- **Strict Isolation:** The test set is frozen before any model training, validation fold generation, acquisition ranking, or hyperparameter selection takes place.
- **Leakage Prevention:**
  - Frozen test examples and their labels are permanently excluded from:
    1. Initial training pools ($\mathcal{D}_0$).
    2. Candidate acquisition pools ($\mathcal{U}$).
    3. Multi-fold cross-validation folds.
    4. Model uncertainty / validation-error proxy calculations.
    5. Ranker inputs, coverage metrics, and feature normalization statistics.
  - The frozen test set remains identical across all strategies, seeds, and acquisition rounds within the benchmark run.

---

## 3. Feature Contract & Preprocessing

The simulation uses the exact shared feature contract implemented in `backend/app/services/preprocessing.py`:
- **Landmark Topology:** `FEATURE_SCHEMA_VERSION = "mp-holistic-75-xyz-v1"` (OpenHands 75-point layout: 33 pose, 21 left hand, 21 right hand; face excluded).
- **Keypoint Subset:** OpenHands `minimal_27` subset indices `[0, 2, 5, 11, 12, 13, 14, 33, 37, 38, 41, 42, 45, 46, 49, 50, 53, 54, 58, 59, 62, 63, 66, 67, 70, 71, 74]`.
- **Coordinate Conventions:** Un-mirrored, normalized image coordinates, $x$ and $y$ channels only (shape: $T \times 27 \times 2$).
- **Temporal Alignment:** Uniform temporal resampling to `TARGET_FPS = 10` FPS, stretched/squashed to fixed `MODEL_FRAMES = 30` frames.
- **Spatial Normalization:** Clip-level shoulder centering and Euclidean shoulder distance scaling (`CenterAndScaleNormalize`).
- **Extractor Consistency:** No silent mixing of browser-extracted and Python-extracted landmarks. Any Python-extracted landmark pipeline must be validated against `tests/test_preprocessing_qc.py` before inclusion.

---

## 4. Acquisition Simulation Harness

### 4.1 Pool Construction
For each experimental seed, the eligible non-test data (from the official training/validation split) is partitioned into:
1. **Initial Labeled Pool ($\mathcal{D}_0$):**
   - A minimal starting dataset of exactly $N_0$ samples per sign (default: $N_0 = 2$ or $3$ samples per sign).
   - Serves as the seed training set for all three strategies before active collection starts.
2. **Unlabeled Candidate Pool ($\mathcal{U}_0$):**
   - The remaining eligible samples ($\mathcal{U}_0 = \mathcal{D}_{\text{train\_pool}} \setminus \mathcal{D}_0$).
   - Ground-truth labels are masked from the acquisition strategies until a sample is selected.
   - Candidate samples are ordered deterministically (e.g., by unique sample ID / file hash) so candidate resolution is reproducible.

### 4.2 Acquisition Budget & Fairness
- **Acquisition Budget:** $R$ sequential rounds (default: $R = 5$ rounds).
- **Batch Size ($B$):** Fixed number of samples acquired per round (default: $B = 10$ samples per round, or 1 per sign for a 10-class vocabulary).
- **Budget Equality:** In round $r \in \{1, \dots, R\}$, every strategy is permitted to acquire exactly $B$ samples. At the conclusion of round $r$, each strategy has trained on exactly $|\mathcal{D}_0| + r \times B$ samples.
- **Shared Starting State:** All strategies run on the **exact same initial labeled pool $\mathcal{D}_0$** and draw from the **exact same candidate pool $\mathcal{U}_0$** for a given seed.
- **Random Seeds:** 3 to 5 deterministic seeds (default: `[42, 43, 44, 45, 46]`).

### 4.3 Evaluated Strategies & Candidate Mapping

Each strategy operates at the acquisition step to select $B$ samples from $\mathcal{U}_{r-1}$:

#### Strategy 1: SIGNFORGE Ranker (`signforge`)
- **Shared Ranker Contract:** Imports and calls the shared ranker function (`backend/app/services/ranker.py`).
  - Inputs per candidate sign:
    - `sign`: canonical gloss string.
    - `coverage_gap`: normalized metric in $[0, 1]$ representing distance from target sample count.
    - `signer_gap`: normalized metric in $[0, 1]$ representing distance from target distinct signer count, or `null` / unavailable if trustworthy signer IDs are absent.
    - `uncertainty`: normalized validation-error proxy in $[0, 1]$, or `null` / unavailable if validation estimates are missing.
  - Expected output: ranked list of records shaped as:
    `{ "sign": str, "priority": float, "reason": str }`
- **Unresolved Ranker Weighting Decision for Tashvi:**
  - The combination weights and mathematical fallback when components are `null` (e.g. unverified signer IDs) require Tashvi's explicit approval.
  - The simulation harness will not invent or hardcode private weights; it will invoke the shared ranker using the team-approved weighting configuration.
- **Candidate Mapping Rule:** The strategy inspects the ranked sign list from highest to lowest priority. For the top-priority sign class $c^*$, it acquires the next available candidate sample for $c^*$ from $\mathcal{U}_{r-1}$ (following deterministic candidate ordering). If a class has exhausted its candidates in $\mathcal{U}_{r-1}$, the selector advances to the next ranked class until $B$ samples are acquired.

#### Strategy 2: Balanced Round-Robin (`round_robin`)
- **Selection Rule:** Inspects current class sample counts in $\mathcal{D}_{r-1}$.
- Iterates deterministically through the sign vocabulary in canonical alphabetical order, selecting the class with the fewest accumulated samples in $\mathcal{D}_{r-1}$.
- Acquires the next available candidate sample for that class from $\mathcal{U}_{r-1}$ using the same deterministic candidate order.
- Does not consult model performance or loss.

#### Strategy 3: Uniform Random Selection (`random`)
- **Selection Rule:** Uniformly samples $B$ examples without replacement from $\mathcal{U}_{r-1}$ using the active experimental seed.
- Sampling unit is the individual candidate clip.
- Does not balance classes or consult model signals.

---

## 5. Per-Sign Validation Signal: Validation-Error Proxy

### 5.1 Definitional Honesty
In accordance with `CLAUDE.md §1` and §3.8:
- The uncertainty signal derived from validation performance is explicitly designated as a **Validation-Error Proxy**.
- It must **not** be presented as Bayesian posterior entropy or calibrated prediction confidence.

### 5.2 Multi-Fold Cross-Validation Protocol
At each round $r$ (for the current labeled pool $\mathcal{D}_r$):
1. **Fold Partitioning:** Form $K$ stratified validation folds (default: $K = 3$ or $5$) strictly over $\mathcal{D}_r$.
   - The frozen test set is never touched.
   - If a class has fewer than $K$ samples, repeated stratified sub-sampling is used to ensure valid training folds.
2. **Fold Training:** For each fold $k \in \{1, \dots, K\}$:
   - Train the baseline GRU on $\mathcal{D}_r \setminus \text{Fold}_k$.
   - Evaluate predictions on $\text{Fold}_k$.
3. **Per-Sign Error Computation:**
   - For each class $c$ present in $\text{Fold}_k$:
     $$\text{Error}_k(c) = 1.0 - \text{Recall}_k(c) = 1.0 - \frac{\text{TP}_{k, c}}{\text{Support}_{k, c}}$$
   - If class $c$ has zero test instances in $\text{Fold}_k$, the fold is recorded as **missing support** for class $c$.
4. **Fold Aggregation & Missing Class Handling:**
   - Where class $c$ is present in at least one fold ($\mathcal{K}_c \neq \emptyset$):
     $$\text{Uncertainty}(c) = \frac{1}{|\mathcal{K}_c|} \sum_{k \in \mathcal{K}_c} \text{Error}_k(c)$$
   - **Missing Class Handling (No Usable Folds):** If $|\mathcal{K}_c| = 0$ (class $c$ had zero validation instances across all folds), $\text{Uncertainty}(c)$ is recorded as **unavailable (`null`)** with supporting sample count $= 0$ and usable fold count $= 0$.
   - It is **never** automatically assigned zero error or an arbitrary maximum value (such as 1.0) unless explicitly defined by the team ranker contract. When `uncertainty` is `null`, the ranker applies its approved missing-signal fallback.
5. **Scale:** The resulting score is naturally bounded in $[0, 1]$.

---

## 6. Model Training & Evaluation Execution

### 6.1 Baseline Model Configuration
- Architecture: `GRUClassifier(n_classes, hidden=64, n_features=54)` in `backend/app/services/baseline_model.py`.
- Optimization: Full-batch Adam, learning rate $1\times 10^{-3}$, weight decay $1\times 10^{-4}$, 80 epochs.
- Initialization: Fixed seed per run, randomly initialized weights (**strictly not pretrained**).

### 6.2 Evaluation on Frozen Test Set
At Round 0 (baseline) and after each acquisition round $r \in \{1, \dots, R\}$:
- Retrain the model on the full current labeled set $\mathcal{D}_r$.
- Generate predictions on the **Frozen Official Test Set**.
- Compute metrics using `classification_metrics()` in `backend/app/services/evaluation.py`:
  - **Top-1 Accuracy:** Trace of confusion matrix divided by total test samples.
  - **Macro-F1:** Unweighted mean of F1 scores across classes with non-zero test support.
  - **Per-Class Metrics:** Precision, recall, F1, and support for each sign class.
  - **Top-5 Accuracy:** Omitted by default because vocabulary size is 10–20 classes (where top-5 is uninformative). Reported only if explicitly requested for larger vocabulary benchmarks.

---

## 7. Execution Architecture & Deliverables

- **Execution Model:** Implemented as an offline benchmark script (`backend/scripts/run_benchmark.py`). It executes without running web dev servers or adding new FastAPI endpoints unless the team explicitly approves an API route.
- **Artifact Generation:** The script outputs:
  1. `data/benchmark_results.json` adhering strictly to `docs/BENCHMARK_SCHEMA.md`.
  2. A human-readable before/after summary table printed to stdout.
  3. Diagnostic logs detailing fold support, seed variability, and any scope reductions.
