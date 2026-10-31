"""Temperature scaling (Guo et al. 2017): one scalar T fitted on the validation split; argmax is unchanged."""
import numpy as np


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(logits: np.ndarray, y: np.ndarray, temperature: float = 1.0) -> float:
    p = softmax(logits, temperature)[np.arange(len(y)), y]
    return float(-np.log(np.clip(p, 1e-12, 1)).mean())


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Grid search over log-spaced T (robust on tens of clips, no optimiser to diverge)."""
    grid = np.exp(np.linspace(np.log(0.05), np.log(20), 400))
    return float(grid[int(np.argmin([nll(logits, y, t) for t in grid]))])


def reliability(probs: np.ndarray, y: np.ndarray, n_bins: int) -> dict:
    """Expected calibration error plus the per-bin table (n, mean confidence, accuracy) behind it."""
    conf, pred = probs.max(axis=1), probs.argmax(axis=1)
    edges = np.linspace(0, 1, n_bins + 1)
    bins, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        n = int(m.sum())
        acc = float((pred[m] == y[m]).mean()) if n else None
        mc = float(conf[m].mean()) if n else None
        if n:
            ece += n / len(y) * abs(acc - mc)
        bins.append({"lo": round(float(lo), 2), "hi": round(float(hi), 2), "n": n,
                     "mean_confidence": None if mc is None else round(mc, 4),
                     "accuracy": None if acc is None else round(acc, 4)})
    return {"ece": round(ece, 4), "n": int(len(y)), "bins": bins}
