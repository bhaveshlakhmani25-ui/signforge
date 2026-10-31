import numpy as np


def classification_metrics(y_true: list[int], y_pred: list[int], labels: list[int]) -> dict:
    """Top-1 accuracy, macro-F1 over classes that have test support, per-class P/R/F1/support, confusion matrix.

    Confusion rows = true class, columns = predicted class, both in `labels` order.
    """
    idx = {c: i for i, c in enumerate(labels)}
    cm = np.zeros((len(labels), len(labels)), int)
    for t, p in zip(y_true, y_pred):
        cm[idx[t], idx[p]] += 1
    per_class = {}
    for c, i in idx.items():
        tp, support, predicted = cm[i, i], cm[i].sum(), cm[:, i].sum()
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[c] = {"precision": round(float(precision), 4), "recall": round(float(recall), 4),
                        "f1": round(float(f1), 4), "support": int(support)}
    supported = [v["f1"] for v in per_class.values() if v["support"]]
    return {
        "accuracy": round(float(np.trace(cm) / cm.sum()), 4) if cm.sum() else None,
        "macro_f1": round(float(np.mean(supported)), 4) if supported else None,
        "macro_f1_over": "classes with test support",
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "labels": labels,
        "n_test": int(cm.sum()),
    }
