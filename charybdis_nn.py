"""Learned terrain contour matching for Charybdis.

Small Siamese CNN predicts the est->true horizontal offset from a pair of
bathymetric patches (sonar observation vs stored map at the dead-reckoned fix).
Training runs on GPU; inference is CPU-only so CI stays green without CUDA.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

PATCH = 9
SPAN = 6.0
DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "tcm_cnn.pt"

_model = None
_device = "cpu"


def _require_torch():
    try:
        import torch
        import torch.nn as nn
    except ImportError as exc:
        raise RuntimeError("torch required; pip install torch") from exc
    return torch, nn


def _patch_grid():
    axis = np.linspace(-SPAN, SPAN, PATCH)
    return np.meshgrid(axis, axis)


_GX, _GY = _patch_grid()


def extract_patches(true_pos: np.ndarray, est_pos: np.ndarray, bathy) -> tuple[np.ndarray, np.ndarray]:
    """Return normalised (observed, map) patches as float32 [2, H, W]."""
    obs = bathy(true_pos[0] + _GX, true_pos[1] + _GY).astype(np.float32)
    mp = bathy(est_pos[0] + _GX, est_pos[1] + _GY).astype(np.float32)
    obs = (obs - obs.mean()) / (obs.std() + 1e-3)
    mp = (mp - mp.mean()) / (mp.std() + 1e-3)
    return obs, mp


def build_model():
    torch, nn = _require_torch()

    class Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool2d(3),
                nn.Flatten(),
            )
            self.head = nn.Linear(32 * 3 * 3, 64)

        def forward(self, x):
            return self.head(self.net(x))

    class SiameseTCM(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = Encoder()
            self.reg = nn.Sequential(
                nn.Linear(128, 64), nn.ReLU(),
                nn.Linear(64, 2),
            )

        def forward(self, obs, mp):
            return self.reg(torch.cat([self.enc(obs), self.enc(mp)], dim=1))

    return SiameseTCM()


def load_model(path: str | Path | None = None, device: str = "cpu"):
    """Load weights once; falls back to untrained model if file missing."""
    global _model, _device
    torch, _ = _require_torch()
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


def tcm_nn_match(true_pos: np.ndarray, est_pos: np.ndarray, bathy,
                 model_path: str | Path | None = None,
                 distort=None) -> tuple[np.ndarray, float, None]:
    """Predict offset via learned matcher; returns (corrected, confidence, None)."""
    torch, _ = _require_torch()
    global _model
    if _model is None:
        load_model(model_path, device="cpu")

    obs_raw = bathy(true_pos[0] + _GX, true_pos[1] + _GY)
    if distort is not None:
        obs_raw = distort(obs_raw, _GX, _GY)
    mp_raw = bathy(est_pos[0] + _GX, est_pos[1] + _GY)
    obs = ((obs_raw - obs_raw.mean()) / (obs_raw.std() + 1e-3)).astype(np.float32)
    mp = ((mp_raw - mp_raw.mean()) / (mp_raw.std() + 1e-3)).astype(np.float32)

    t_obs = torch.from_numpy(obs[None, None]).to(_device)
    t_mp = torch.from_numpy(mp[None, None]).to(_device)
    with torch.no_grad():
        off = _model(t_obs, t_mp).cpu().numpy()[0]
    corrected = est_pos + off
    # pseudo-correlation: inverse mapping error on observed vs corrected map patch
    corr_patch = bathy(corrected[0] + _GX, corrected[1] + _GY)
    c = corr_patch - corr_patch.mean()
    o = obs_raw - obs_raw.mean()
    peak = float(np.sum(o * c) / ((np.linalg.norm(o) + 1e-9) * (np.linalg.norm(c) + 1e-9)))
    peak = max(0.0, min(1.0, peak))
    return corrected, peak, None


def _pick_device(preferred: str | None = None) -> str:
    torch, _ = _require_torch()
    if preferred:
        return preferred
    if torch.cuda.is_available():
        try:
            t = torch.zeros(1, device="cuda")
            _ = t + 1
            return "cuda"
        except Exception:
            pass
    return "cpu"


def train(model_path: str | Path | None = None, n_samples: int = 12000,
          epochs: int = 8, batch: int = 256, seed: int = 0, device: str | None = None,
          num_workers: int = 0):
    """Train on synthetic bathymetry; writes ``models/tcm_cnn.pt``."""
    import charybdis_core as core
    torch, nn = _require_torch()
    device = _pick_device(device)
    rng = np.random.default_rng(seed)
    model = build_model().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    bathy = core.bathymetry
    nw = max(0, min(num_workers, 31))

    for ep in range(epochs):
        total = 0.0
        n_batches = max(1, n_samples // batch)
        for b in range(n_batches):
            true = rng.uniform(5, 115, size=(batch, 2))
            err = rng.normal(0, 4.0, size=(batch, 2))
            err += rng.uniform(-8, 8, size=(batch, 2)) * (rng.random((batch, 1)) < 0.3)
            est = true + err
            target = true - est
            if nw > 0:
                from concurrent.futures import ThreadPoolExecutor
                def _one(i):
                    return extract_patches(true[i], est[i], bathy)
                with ThreadPoolExecutor(max_workers=nw) as ex:
                    pairs = list(ex.map(_one, range(batch)))
                obs_list = [p[0] for p in pairs]
                mp_list = [p[1] for p in pairs]
            else:
                obs_list, mp_list = [], []
                for i in range(batch):
                    o, m = extract_patches(true[i], est[i], bathy)
                    obs_list.append(o); mp_list.append(m)
            t_obs = torch.from_numpy(np.stack(obs_list)[:, None]).to(device)
            t_mp = torch.from_numpy(np.stack(mp_list)[:, None]).to(device)
            t_y = torch.from_numpy(target.astype(np.float32)).to(device)
            pred = model(t_obs, t_mp)
            loss = loss_fn(pred, t_y)
            opt.zero_grad(); loss.backward(); opt.step()
            total += float(loss.item())
        print(f"epoch {ep + 1}/{epochs} loss={total / n_batches:.4f} dev={device}")

    out = Path(model_path or DEFAULT_MODEL)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)
    print(f"saved {out} ({out.stat().st_size // 1024} KiB)")
    return out
