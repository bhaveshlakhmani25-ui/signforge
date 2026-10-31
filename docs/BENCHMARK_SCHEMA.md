# Benchmark Output Schema Specification

**Agreed by:** Aakarshi Dwivedi, Reuben Raju (ML), Bhavesh Lakhmani (Frontend)  
**Output Path:** `data/benchmark_results.json` (also mirrored at `frontend/public/benchmark/benchmark.sample.json`)

---

## 1. Schema Definition
Reuben's evaluation script writes a single JSON document with this exact schema. Bhavesh's Benchmark page reads this file to plot learning curves and display performance metrics.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "BenchmarkResults",
  "type": "object",
  "required": [
    "schema_version",
    "generated_at",
    "is_demo",
    "dataset",
    "metric",
    "seeds",
    "samples_added",
    "curves"
  ],
  "properties": {
    "schema_version": { "type": "integer", "enum": [1] },
    "generated_at": { "type": "string", "format": "date-time" },
    "is_demo": { "type": "boolean" },
    "dataset": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "n_signs": { "type": "integer" },
        "split": { "type": "string" },
        "source": { "type": "string" }
      }
    },
    "protocol": { "type": "string" },
    "metric": { "type": "string", "enum": ["accuracy", "macro_f1"] },
    "seeds": {
      "type": "array",
      "items": { "type": "integer" }
    },
    "samples_added": {
      "type": "array",
      "items": { "type": "integer" }
    },
    "curves": {
      "type": "object",
      "properties": {
        "ranker": {
          "type": "object",
          "properties": {
            "mean": { "type": "array", "items": { "type": "number" } },
            "std": { "type": "array", "items": { "type": "number" } }
          }
        },
        "balanced": {
          "type": "object",
          "properties": {
            "mean": { "type": "array", "items": { "type": "number" } },
            "std": { "type": "array", "items": { "type": "number" } }
          }
        },
        "random": {
          "type": "object",
          "properties": {
            "mean": { "type": "array", "items": { "type": "number" } },
            "std": { "type": "array", "items": { "type": "number" } }
          }
        }
      }
    }
  }
}
```

---

## 2. Key Differentiation
This curve proves that **Active Learning (Ranker)** reaches high accuracy with fewer collected samples than uniform random collection, directly validating the SIGNFORGE hypothesis.
