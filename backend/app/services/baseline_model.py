"""From-scratch baseline: a small GRU over the shared (T,27,2) feature contract. Random init, NOT pretrained."""
import numpy as np
import torch
from torch import nn


class GRUClassifier(nn.Module):
    def __init__(self, n_classes: int, hidden: int, n_features: int = 27 * 2):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, batch_first=True)
        self.head = nn.Linear(hidden, n_classes)

    def forward(self, x):  # x: (B, T, 27, 2)
        _, h = self.gru(x.flatten(2))
        return self.head(h[-1])


def train_baseline(X: np.ndarray, y: np.ndarray, n_classes: int, cfg: dict, seed: int) -> GRUClassifier:
    torch.manual_seed(seed)
    model = GRUClassifier(n_classes, cfg["hidden"])
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    xb, yb = torch.from_numpy(X), torch.from_numpy(y)
    model.train()
    for _ in range(cfg["epochs"]):  # full-batch: corpora here are tens to hundreds of clips
        opt.zero_grad()
        nn.functional.cross_entropy(model(xb), yb).backward()
        opt.step()
    return model


@torch.no_grad()
def predict_proba(model: nn.Module, X: np.ndarray) -> np.ndarray:
    model.eval()
    return torch.softmax(model(torch.from_numpy(X)), dim=-1).numpy()
