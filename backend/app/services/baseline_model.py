"""From-scratch baseline: a small GRU over the shared (T,27,2) feature contract. Random init, NOT pretrained."""
import numpy as np
import torch
from torch import nn


class GRUClassifier(nn.Module):
    def __init__(self, n_classes: int, hidden: int, n_features: int = 27 * 2, dropout: float = 0.0):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, batch_first=True)
        self.drop = nn.Dropout(dropout)  # no weights and a no-op in eval mode, so inference (and the browser port) is unchanged
        self.head = nn.Linear(hidden, n_classes)

    def forward(self, x):  # x: (B, T, 27, 2)
        _, h = self.gru(x.flatten(2))
        return self.head(self.drop(h[-1]))


def augment(X: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Training-only jitter of normalised (B, T, 27, 2) clips: a random crop of the clip's ends re-stretched to T frames,
    then a small rotation, scale and shift, plus noise. Zero-filled (missing) points stay zero. Never used on val/test."""
    B, T = X.shape[:2]
    out = np.empty_like(X)
    for i in range(B):
        a, b = rng.integers(0, max(1, T // 8) + 1), T - rng.integers(0, max(1, T // 8) + 1)
        x = X[i, np.linspace(a, b - 1, T).round().astype(int)]
        th, s = rng.uniform(-0.15, 0.15), rng.uniform(0.9, 1.1)
        R = s * np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]], np.float32)
        y = x @ R.T + rng.uniform(-0.1, 0.1, 2).astype(np.float32) + rng.normal(0, 0.01, x.shape).astype(np.float32)
        out[i] = np.where((x == 0).all(-1, keepdims=True), 0, y)
    return out


def train_baseline(X: np.ndarray, y: np.ndarray, n_classes: int, cfg: dict, seed: int) -> GRUClassifier:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = GRUClassifier(n_classes, cfg["hidden"], dropout=cfg.get("dropout", 0.0))
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    xb, yb = torch.from_numpy(X), torch.from_numpy(y)
    model.train()
    for _ in range(cfg["epochs"]):  # full-batch: corpora here are tens to hundreds of clips
        opt.zero_grad()
        x = torch.from_numpy(augment(X, rng)) if cfg.get("augment") else xb  # a fresh jitter every epoch
        nn.functional.cross_entropy(model(x), yb).backward()
        opt.step()
    return model


@torch.no_grad()
def predict_proba(model: nn.Module, X: np.ndarray) -> np.ndarray:
    model.eval()
    return torch.softmax(model(torch.from_numpy(X)), dim=-1).numpy()


@torch.no_grad()
def predict_logits(model: nn.Module, X: np.ndarray) -> np.ndarray:
    model.eval()
    return model(torch.from_numpy(X)).numpy()
