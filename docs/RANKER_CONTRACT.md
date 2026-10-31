# Active Learning Ranker I/O Contract

**Agreed by:** Aakarshi Dwivedi, Tashvi Adhlakha, Bhavesh Lakhmani  
**Status:** Stamped & Locked  
**Target:** First-hour handoff between Pair 1 (Backend/ML) and Pair 2 (Frontend/UI)

---

## 1. Objective
The Ranker answers the defining product question of SIGNFORGE: **“What data should we collect next?”**

It balances three signals:
1. **Coverage Gap:** Classes with zero or few approved samples.
2. **Signer Diversity Gap:** Classes where all existing samples come from a single signer.
3. **Model Uncertainty:** Classes where the classifier shows high entropy or frequent confusions.

---

## 2. API Schema

### Endpoint: `GET /api/active-learning/queue`
* **Query Params:** `project_id: int`

### Response JSON Contract:
```typescript
interface RankedTask {
  sign_class_id: number;
  gloss: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  priority_score: number; // 0.0 to 1.0 (higher = more urgent)
  coverage_gap: number;   // normalized gap based on target samples per class
  signer_diversity_gap: number; // fraction of signers missing
  uncertainty_score: number | null; // model entropy, or null if no model run
  reason: string;         // human-readable justification for the collector
  suggested_signer: string; // e.g. "new signer" or "any"
}
```

### Example Payload:
```json
[
  {
    "sign_class_id": 4,
    "gloss": "EMERGENCY",
    "priority": "HIGH",
    "priority_score": 0.95,
    "coverage_gap": 1.0,
    "signer_diversity_gap": 1.0,
    "uncertainty_score": null,
    "reason": "Zero approved samples in dataset.",
    "suggested_signer": "Any consented signer"
  },
  {
    "sign_class_id": 1,
    "gloss": "HELLO",
    "priority": "LOW",
    "priority_score": 0.2,
    "coverage_gap": 0.1,
    "signer_diversity_gap": 0.3,
    "uncertainty_score": 0.12,
    "reason": "Adequate coverage (6 approved samples across 3 signers).",
    "suggested_signer": "Optional"
  }
]
```

---

## 3. UI Usage (Bhavesh)
The Active Learning screen (`frontend/app/active-learning/page.tsx`) renders this list as prioritized cards with:
- Visual badge (`HIGH` red, `MEDIUM` yellow, `LOW` green).
- One-click button: **"Record this sign"**, which navigates directly to `/capture?sign_class_id=4` with the sign pre-selected!
