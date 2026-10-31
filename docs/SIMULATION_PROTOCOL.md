# SIGNFORGE Evaluation Protocol: Active Acquisition Simulation

**Document Version:** `1.2.0`  
**Author:** ML & Evaluation Engineering (Ruben Raju)  
**Status:** Approved Simulation Protocol (2-by-25 Acquisition Schedule & Approved Weights)  
**Target Dataset:** AI4Bharat INCLUDE (10-Class Standardized ISL Benchmark Subset)

---

## 1. Objective & Empirical Scope

This protocol specifies a strictly controlled, reproducible offline simulation to benchmark three collection strategies on a standardized Indian Sign Language (ISL) subset from the AI4Bharat INCLUDE dataset. The live SIGNFORGE application is a demo and collection layer; team recordings and synthetic demo data are not validated ISL evidence and are strictly excluded from scientific benchmark reporting.

The core question being evaluated is:
> **Does model-informed active collection improve recognition performance with fewer collected samples compared to balanced round-robin and uniform random collection?**

### 1.1 Exploratory Status & Transfer Feasibility
- **Exploratory Evaluation:** All metrics reported from this simulation are exploratory findings on a standardized 10-class INCLUDE subset. They demonstrate active collection efficiency in low-resource settings, not production-grade or generalized sign-language translation.
- **Transfer Tests (T1–T4) & Blocked Status:** Preliminary cross-lingual transfer tests (T1–T4) determined that transfer learning from pretrained WLASL checkpoints is **Blocked** because test T1 failed (`_pickle.UnpicklingError` / `ModuleNotFoundError: No module named 'pytorch_lightning'`). In accordance with the approved fallbacks, all benchmark models are initialized and trained strictly from scratch within ISL.

---

## 2. Dataset, Vocabulary, and Frozen Split Integrity

### 2.1 Primary Benchmark Dataset: INCLUDE Subset
- **Dataset:** AI4Bharat INCLUDE (Indian Sign Language Dataset).
- **Target Vocabulary (10 Signs):**  
  `["DOCTOR", "EMERGENCY", "FOOD", "HELLO", "HELP", "NO", "PAIN", "THANK-YOU", "WATER", "YES"]`
- **Data Source Type:** `external_dataset`. Benchmark data is kept isolated from demo fixtures.

### 2.2 Split Isolation & Signer Integrity
- **Signer ID Audit:** Public INCLUDE metadata does not provide verified, per-clip individual signer identifiers.
- **Independence Honesty Rule:** Because signer IDs are unverified, evaluation results must **never** be claimed or reported as "signer-independent".
- **Frozen Test Split:** The test set is strictly frozen prior to any ranking or training decisions. Test sample IDs and features are held in an immutable evaluation partition.
- **Split Naming:** Explicitly documented as `official_include_test_split` (or `proposed_stratified_fallback`), never `signer_independent`.
- **Absolute Test Isolation:** The frozen test set must never enter:
  1. Initial labeled training pool $\mathcal{D}_0$.
  2. Unlabeled candidate pool $\mathcal{U}_0$.
  3. Validation folds for uncertainty estimation.
  4. Model training, fitting, or hyperparameter selection.
  5. Ranker inputs, coverage metrics, and feature normalization statistics.

---

## 3. Feature Representation & Preprocessing Contract

All evaluated samples strictly follow the SIGNFORGE feature specification:
- **Feature Schema Version:** `mp-holistic-75-xyz-v1` (27 minimal OpenHands keypoints: 7 pose, 10 left hand, 10 right hand).
- **Temporal Alignment:** 30 frames resampled at 10.0 FPS.
- **Channels:** 2 channels ($x, y$ coordinates).
- **Spatial Normalization:** Clip-level shoulder centering and Euclidean shoulder distance scaling (`CenterAndScaleNormalize`).

---

## 4. Acquisition Simulation Harness

### 4.1 Pool Construction
For each experimental seed, the non-test data is partitioned into:
1. **Initial Labeled Pool ($\mathcal{D}_0$):** Exactly $N_0 = 2$ samples per sign (total 20 samples). Serves as the identical starting dataset for all three strategies before active collection starts.
2. **Unlabeled Candidate Pool ($\mathcal{U}_0$):** Remaining candidate clips ($\mathcal{U}_0 = \mathcal{D}_{\text{train\_pool}} \setminus \mathcal{D}_0$). Candidate clips are ordered deterministically by unique sample ID.

### 4.2 Approved Acquisition Protocol: 2-by-25 Schedule
- **Batch Size ($B$):** Exactly 2 samples acquired per round ($B = 2$).
- **Maximum Rounds ($R$):** Exactly 25 rounds ($R = 25$).
- **Total Acquisition Budget:** $25 \text{ rounds} \times 2 \text{ samples/round} = 50 \text{ newly acquired samples}$.
- **Final Training Budget:** $20 \text{ (initial)} + 50 \text{ (acquired)} = 70 \text{ samples}$.
- **Budget Equality:** In every round $r \in \{1, \dots, 25\}$, all three strategies acquire exactly 2 clips.
- **Shared Starting State:** All strategies run on the **exact same initial labeled pool $\mathcal{D}_0$** and draw from the **exact same candidate pool $\mathcal{U}_0$** for a given seed.
- **Random Seeds:** 3 deterministic seeds: `[42, 43, 44]`.

### 4.3 Approved Ranker Formula
The shared ranker combines three normalized signals in $[0, 1]$:
$$\text{Priority}(c) = \frac{w_{\text{unc}} \cdot \text{Uncertainty}(c) + w_{\text{cov}} \cdot \text{CoverageGap}(c) + w_{\text{sig}} \cdot \text{SignerGap}(c)}{\sum_{i \in \text{available}} w_i}$$

- **Approved Weights:**
  - Uncertainty: $w_{\text{unc}} = 0.50$
  - Coverage gap: $w_{\text{cov}} = 0.30$
  - Signer gap: $w_{\text{sig}} = 0.20$
- **Missing-Signal Renormalization:** When one or more signals are unavailable (`null` / `None`):
  - In INCLUDE without verified signer IDs, `signer_gap` is `null`. The remaining weights are renormalized:
    $$w_{\text{unc}} = \frac{0.50}{0.50 + 0.30} = 0.625, \quad w_{\text{cov}} = \frac{0.30}{0.50 + 0.30} = 0.375$$
  - When uncertainty is unmeasured, coverage gap and signer gap are renormalized.
  - Unavailable signals are never treated as 0 or 1; they are omitted and their absence is recorded in the ranker reason metadata.
  - If all signals are unavailable, the system defaults to priority 0.0 with deterministic alphabetical ordering.

### 4.4 Evaluated Strategies & Per-Round Selection

At each round $r \in \{1, \dots, 25\}$:

#### Strategy 1: SIGNFORGE Ranker (`signforge`)
- Recompute per-sign validation-error proxy on current labeled set $\mathcal{D}_{r-1}$ using 3-fold cross-validation.
- Call the shared ranker to compute priorities for all 10 sign classes using the approved weights and renormalization rule.
- Identify eligible classes that have at least one remaining candidate in $\mathcal{U}_{r-1}$.
- Select the **two highest-priority eligible signs**.
- For each selected sign, acquire one deterministic next candidate clip (sorted by ID) from $\mathcal{U}_{r-1}$.
- If fewer than 2 candidates can be acquired, record a warning and stop the run; do not silently substitute samples.

#### Strategy 2: Balanced Round-Robin (`round_robin`)
- Inspect current sample counts in $\mathcal{D}_{r-1}$.
- Identify eligible classes with candidates remaining in $\mathcal{U}_{r-1}$.
- Select the **two least-sampled eligible signs**, using deterministic alphabetical tie-breaking.
- For each selected sign, acquire one candidate clip (sorted by ID) from $\mathcal{U}_{r-1}$.

#### Strategy 3: Uniform Random Selection (`random`)
- Uniformly sample **two candidate clips** without replacement from $\mathcal{U}_{r-1}$ using active seed: `np.random.default_rng(seed * 1000 + r)`.

---

## 5. Model Training & Evaluation Execution

### 5.1 Model Configuration
- **Architecture:** `GRUClassifier(n_classes=10, hidden=64, n_features=54)`.
- **Optimization:** Full-batch Adam, learning rate $1\times 10^{-3}$, weight decay $1\times 10^{-4}$, 50 epochs.
- **Initialization:** Fixed seed per run, randomly initialized weights (**strictly from scratch, not pretrained**).

### 5.2 Evaluation on Frozen Test Set
At Round 0 (baseline) and after every acquisition round $r \in \{1, \dots, 25\}$:
- Freshly retrain the baseline model from scratch on the newly updated labeled pool $\mathcal{D}_r$.
- Generate predictions on the **Frozen Official Test Set** (40 samples).
- Compute metrics using `classification_metrics()`:
  - Top-1 Accuracy
  - Macro-F1 (unweighted mean across classes with test support)
  - Per-class precision, recall, F1, and support
  - Confusion matrix
