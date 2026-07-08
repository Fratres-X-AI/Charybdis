"""Learned terrain matcher: SO(2)-equivariant Siamese net + suitability head.

Rotation-equivariant encoding via channel-wise max over discrete rotations,
plus a scalar suitability score for terrain-aided fix quality.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

PATCH = 9
SPAN = 400.0
N_ROT = 8
DEFAULT_MODEL = Path(__file__).resolve().parents[1] / "models" / "tcm_so2.pt"

_model = None
_device = "cpu"


def _require_torch():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
    except ImportError as exc:
        raise RuntimeError("torch required; pip install torch") from exc
    return torch, nn, F


def _grid():
    axis = np.linspace(-SPAN, SPAN, PATCH)
    return np.meshgrid(axis, axis)


_GX, _GY = _grid()


def extract_patch(center: np.ndarray, terrain) -> np.ndarray:
    z = terrain.elevation(center[0] + _GX, center[1] + _GY).astype(np.float32)
    return ((z - z.mean()) / (z.std() + 1e-3))[None]  # [1,H,W]


def extract_patches_batch(centers: np.ndarray, terrain) -> np.ndarray:
    cx = centers[:, 0][:, None, None] + _GX[None]
    cy = centers[:, 1][:, None, None] + _GY[None]
    z = terrain.elevation(cx, cy).astype(np.float32)
    mu = z.mean(axis=(1, 2), keepdims=True)
    sd = z.std(axis=(1, 2), keepdims=True) + 1e-3
    return ((z - mu) / sd)[:, None]


def build_model():
    torch, nn, F = _require_torch()

    class SO2Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool2d(3),
            )
            self.fc = nn.Linear(32 * 3 * 3, 64)

        def forward(self, x):
            feats = []
            for k in range(N_ROT):
                xk = torch.rot90(x, k, (2, 3))
                f = self.conv(xk).flatten(1)
                feats.append(self.fc(f))
            return torch.stack(feats, dim=0).max(dim=0).values

    class TerrainMatcher(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = SO2Encoder()
            self.offset = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 2))
            self.suit = nn.Sequential(nn.Linear(128, 32), nn.ReLU(), nn.Linear(32, 1),
                                      nn.Sigmoid())

        def forward(self, obs, mp):
            eo, em = self.enc(obs), self.enc(mp)
            h = torch.cat([eo, em], dim=1)
            return self.offset(h), self.suit(h).squeeze(-1)

    return TerrainMatcher()


def load_model(path: str | Path | None = None, device: str = "cpu"):
    global _model, _device
    torch, _, _ = _require_torch()
    _device = device
    model = build_model()
    p = Path(path or DEFAULT_MODEL)
    if p.is_file():
        try:
            state = torch.load(p, map_location=device, weights_only=True)
        except TypeError:
            state = torch.load(p, map_location=device)
        model.load_state_dict(state)
    model.to(device).eval()
    _model = model
    return model


def predict_offset(obs_patch: np.ndarray, map_patch: np.ndarray,
                   model_path: str | Path | None = None) -> tuple[np.ndarray, float]:
    torch, _, _ = _require_torch()
    global _model
    if _model is None:
        load_model(model_path, "cpu")
    t_o = torch.from_numpy(obs_patch[None].astype(np.float32)).to(_device)
    t_m = torch.from_numpy(map_patch[None].astype(np.float32)).to(_device)
    with torch.no_grad():
        off, suit = _model(t_o, t_m)
    return off.cpu().numpy()[0], float(suit.cpu().numpy()[0])


def match_position(true_pos: np.ndarray, est_pos: np.ndarray, terrain,
                   model_path: str | Path | None = None) -> tuple[np.ndarray, float]:
    obs = extract_patch(true_pos, terrain)
    mp = extract_patch(est_pos, terrain)
    off, suit = predict_offset(obs, mp, model_path)
    return est_pos + off, suit


def _pick_device(preferred: str | None = None) -> str:
    torch, _, _ = _require_torch()
    if preferred:
        return preferred
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def train(model_path: str | Path | None = None, n_samples: int = 8000,
          epochs: int = 6, batch: int = 256, seed: int = 0,
          device: str | None = None):
    from .config import SimConfig
    from .terrain import Terrain
    torch, nn, _ = _require_torch()
    device = _pick_device(device)
    rng = np.random.default_rng(seed)
    terrain = Terrain.synthetic(SimConfig(seed=seed))
    model = build_model().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_off = nn.MSELoss()
    loss_suit = nn.BCELoss()

    for ep in range(epochs):
        total = 0.0
        nb = max(1, n_samples // batch)
        for _ in range(nb):
            true = rng.uniform(500, 35000, size=(batch, 2))
            err = rng.normal(0, 120.0, size=(batch, 2))
            est = true + err
            target = (true - est).astype(np.float32)
            obs = extract_patches_batch(true, terrain)
            mp = extract_patches_batch(est, terrain)
            suit_t = (np.linalg.norm(err, axis=1) < 80.0).astype(np.float32)
            t_o = torch.from_numpy(obs).to(device)
            t_m = torch.from_numpy(mp).to(device)
            t_y = torch.from_numpy(target).to(device)
            t_s = torch.from_numpy(suit_t).to(device)
            pred, suit = model(t_o, t_m)
            loss = loss_off(pred, t_y) + 0.3 * loss_suit(suit, t_s)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item())
        print(f"epoch {ep + 1}/{epochs} loss={total / nb:.4f} dev={device}")

    out = Path(model_path or DEFAULT_MODEL)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)
    print(f"saved {out}")
    return out
