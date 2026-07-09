"""Learned terrain matcher: SO(2)-equivariant Siamese net + suitability head.

WARNING: Experimental / unstable API. Do not use in production navigation
paths. Import through :mod:`charybdis.experimental.nn_matcher`.

Rotation-equivariant encoding via channel-wise max over discrete rotations,
plus a scalar suitability score for terrain-aided fix quality.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

PATCH = 17
SPAN = 500.0
N_ROT = 8
DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "tcm_so2.pt"

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


def _scale_patches(
    obs_z: np.ndarray, mp_z: np.ndarray, relief: float
) -> tuple[np.ndarray, np.ndarray]:
    """Pair-normalize using the observation reference so offset signal is preserved."""
    ref = obs_z.mean(axis=(1, 2), keepdims=True) if obs_z.ndim == 3 else obs_z.mean()
    scale = max(float(relief), 1.0)
    if obs_z.ndim == 3:
        obs = ((obs_z - ref) / scale)[:, None]
        mp = ((mp_z - ref) / scale)[:, None]
    else:
        obs = ((obs_z - ref) / scale)[None]
        mp = ((mp_z - ref) / scale)[None]
    return obs.astype(np.float32), mp.astype(np.float32)


def extract_pair_batch(
    true_xy: np.ndarray, est_xy: np.ndarray, terrain, relief: float = 350.0
) -> tuple[np.ndarray, np.ndarray]:
    cx_t = true_xy[:, 0][:, None, None] + _GX[None]
    cy_t = true_xy[:, 1][:, None, None] + _GY[None]
    cx_e = est_xy[:, 0][:, None, None] + _GX[None]
    cy_e = est_xy[:, 1][:, None, None] + _GY[None]
    obs_z = terrain.elevation(cx_t, cy_t).astype(np.float32)
    mp_z = terrain.elevation(cx_e, cy_e).astype(np.float32)
    return _scale_patches(obs_z, mp_z, relief)


def extract_patch(center: np.ndarray, terrain, relief: float = 350.0) -> np.ndarray:
    z = terrain.elevation(center[0] + _GX, center[1] + _GY).astype(np.float32)
    obs, _ = _scale_patches(z, z, relief)
    return obs


def extract_patches_batch(
    centers: np.ndarray, terrain, relief: float = 350.0
) -> np.ndarray:
    """Legacy batch extractor (single patch per center, obs-style reference)."""
    cx = centers[:, 0][:, None, None] + _GX[None]
    cy = centers[:, 1][:, None, None] + _GY[None]
    z = terrain.elevation(cx, cy).astype(np.float32)
    obs, _ = _scale_patches(z, z, relief)
    return obs


def build_model():
    torch, nn, _ = _require_torch()

    class ConvBlock(nn.Module):
        def __init__(self, in_ch: int, out_ch: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 3, padding=1),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(),
            )

        def forward(self, x):
            return self.net(x)

    class SO2Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.stem = nn.Sequential(
                ConvBlock(1, 24),
                ConvBlock(24, 48),
                ConvBlock(48, 64),
                nn.AdaptiveAvgPool2d(4),
            )
            self.fc = nn.Linear(64 * 4 * 4, 96)

        def forward(self, x):
            feats = []
            for k in range(N_ROT):
                xk = torch.rot90(x, k, (2, 3))
                feats.append(self.fc(self.stem(xk).flatten(1)))
            return torch.stack(feats, dim=0).max(dim=0).values

    class DiffEncoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                ConvBlock(1, 24),
                ConvBlock(24, 48),
                nn.AdaptiveAvgPool2d(4),
                nn.Flatten(),
                nn.Linear(48 * 4 * 4, 64),
                nn.ReLU(),
            )

        def forward(self, x):
            return self.net(x)

    class TerrainMatcher(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = SO2Encoder()
            self.diff_enc = DiffEncoder()
            self.offset = nn.Sequential(
                nn.Linear(96 + 96 + 64, 128),
                nn.ReLU(),
                nn.Linear(128, 2),
            )
            self.suit = nn.Sequential(
                nn.Linear(96 + 96 + 64, 48),
                nn.ReLU(),
                nn.Linear(48, 1),
                nn.Sigmoid(),
            )

        def forward(self, obs, mp):
            eo, em = self.enc(obs), self.enc(mp)
            ed = self.diff_enc(mp - obs)
            h = torch.cat([eo, em, ed], dim=1)
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


def predict_offset(
    obs_patch: np.ndarray, map_patch: np.ndarray, model_path: str | Path | None = None
) -> tuple[np.ndarray, float]:
    torch, _, _ = _require_torch()
    global _model
    if _model is None:
        load_model(model_path, "cpu")
    t_o = torch.from_numpy(obs_patch[None].astype(np.float32)).to(_device)
    t_m = torch.from_numpy(map_patch[None].astype(np.float32)).to(_device)
    with torch.no_grad():
        off_n, suit = _model(t_o, t_m)
    off = off_n.cpu().numpy()[0] * SPAN
    return off, float(suit.detach().cpu().numpy()[0])


def match_position(
    true_pos: np.ndarray,
    est_pos: np.ndarray,
    terrain,
    model_path: str | Path | None = None,
    relief: float = 350.0,
) -> tuple[np.ndarray, float]:
    obs_z = terrain.elevation(true_pos[0] + _GX, true_pos[1] + _GY).astype(np.float32)
    mp_z = terrain.elevation(est_pos[0] + _GX, est_pos[1] + _GY).astype(np.float32)
    obs, mp = _scale_patches(obs_z, mp_z, relief)
    off, suit = predict_offset(obs, mp, model_path)
    return est_pos + off, suit


def _pick_device(preferred: str | None = None) -> str:
    torch, _, _ = _require_torch()
    if preferred:
        return preferred
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _sample_errors(
    rng: np.random.Generator, batch: int, hard: bool = False
) -> np.ndarray:
    """Mix error magnitudes; hard mode adds extreme 120-220 m outliers."""
    mag = np.empty(batch, dtype=np.float32)
    if hard:
        roll = rng.random(batch)
        small = roll < 0.25
        med = (roll >= 0.25) & (roll < 0.55)
        large = roll >= 0.55
        mag[small] = rng.uniform(10.0, 50.0, size=int(small.sum()))
        mag[med] = rng.uniform(50.0, 120.0, size=int(med.sum()))
        mag[large] = rng.uniform(120.0, 220.0, size=int(large.sum()))
    else:
        small = rng.random(batch) < 0.4
        mag[small] = rng.uniform(12.0, 55.0, size=int(small.sum()))
        mag[~small] = rng.uniform(55.0, 170.0, size=int((~small).sum()))
    theta = rng.uniform(0.0, 2 * np.pi, size=batch)
    return np.stack([mag * np.cos(theta), mag * np.sin(theta)], axis=1).astype(
        np.float32
    )


def _sample_positions(
    rng: np.random.Generator, batch: int, margin: float
) -> np.ndarray:
    lo, hi = margin, 40000.0 - margin
    return rng.uniform(lo, hi, size=(batch, 2)).astype(np.float32)


def eval_hard(
    model,
    terrains: list,
    relief: float,
    device: str,
    rng: np.random.Generator,
    n: int = 4096,
    infer_batch: int = 512,
) -> dict[str, float]:
    """Stress eval: mixed terrains, wide error distribution, position-level metrics."""
    torch, _, _ = _require_torch()
    model.eval()
    before, after, corr = [], [], []
    margin = SPAN + 400.0
    with torch.no_grad():
        done = 0
        while done < n:
            b = min(infer_batch, n - done)
            terr = terrains[rng.integers(0, len(terrains))]
            true = _sample_positions(rng, b, margin)
            err = _sample_errors(rng, b, hard=True)
            est = true + err
            obs, mp = extract_pair_batch(true, est, terr, relief)
            t_o = torch.from_numpy(obs).to(device)
            t_m = torch.from_numpy(mp).to(device)
            pred_n, _ = model(t_o, t_m)
            pred = pred_n.cpu().numpy() * SPAN
            target = true - est
            corr.append(np.linalg.norm(pred - target, axis=1))
            before.append(np.linalg.norm(est - true, axis=1))
            after.append(np.linalg.norm(est + pred - true, axis=1))
            done += b
    model.train()
    before_a = np.concatenate(before)
    after_a = np.concatenate(after)
    corr_a = np.concatenate(corr)
    large = before_a > 100.0
    return {
        "corr_mae": float(corr_a.mean()),
        "before_mean": float(before_a.mean()),
        "after_mean": float(after_a.mean()),
        "after_p50": float(np.percentile(after_a, 50)),
        "after_p90": float(np.percentile(after_a, 90)),
        "after_p95": float(np.percentile(after_a, 95)),
        "large_after_mean": float(after_a[large].mean()) if large.any() else 0.0,
        "improve_pct": float(
            100.0 * (1.0 - after_a.mean() / max(before_a.mean(), 1e-3))
        ),
    }


def _fmt_hard(m: dict[str, float]) -> str:
    return (
        f"hard n=4096 corr={m['corr_mae']:.1f}m "
        f"{m['before_mean']:.0f}->{m['after_mean']:.0f}m "
        f"p50={m['after_p50']:.0f} p90={m['after_p90']:.0f} p95={m['after_p95']:.0f} "
        f"large={m['large_after_mean']:.0f}m imp={m['improve_pct']:.0f}%"
    )


def train(
    model_path: str | Path | None = None,
    n_samples: int = 8000,
    epochs: int = 25,
    batch: int = 256,
    seed: int = 0,
    device: str | None = None,
    n_terrains: int = 8,
    relief: float = 350.0,
    resume: str | Path | None = None,
    lr: float = 3e-4,
    hard: bool = False,
):
    from ..config import SimConfig
    from ..terrain import Terrain

    torch, nn, _ = _require_torch()
    device = _pick_device(device)
    rng = np.random.default_rng(seed)
    terrains = [
        Terrain.synthetic(SimConfig(seed=seed + i * 17)) for i in range(n_terrains)
    ]
    model = build_model().to(device)
    if resume is not None:
        ckpt = Path(resume)
        if ckpt.is_file():
            try:
                state = torch.load(ckpt, map_location=device, weights_only=True)
            except TypeError:
                state = torch.load(ckpt, map_location=device)
            model.load_state_dict(state)
            print(f"resumed {ckpt}")
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(epochs, 1))
    huber = nn.SmoothL1Loss()
    bce = nn.BCELoss()
    margin = SPAN + 400.0

    for ep in range(epochs):
        total = 0.0
        nb = max(1, n_samples // batch)
        for _ in range(nb):
            terr = terrains[rng.integers(0, n_terrains)]
            true = _sample_positions(rng, batch, margin)
            err = _sample_errors(rng, batch, hard=hard)
            est = true + err
            target_n = ((true - est) / SPAN).astype(np.float32)
            obs, mp = extract_pair_batch(true, est, terr, relief)
            suit_t = (np.linalg.norm(err, axis=1) < 70.0).astype(np.float32)
            t_o = torch.from_numpy(obs).to(device)
            t_m = torch.from_numpy(mp).to(device)
            t_y = torch.from_numpy(target_n).to(device)
            t_s = torch.from_numpy(suit_t).to(device)
            pred_n, suit = model(t_o, t_m)
            loss = huber(pred_n, t_y) + 0.15 * bce(suit, t_s)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step()
            total += float(loss.item())
        sched.step()
        hm = eval_hard(
            model, terrains, relief, device, rng, infer_batch=min(batch, 512)
        )
        print(
            f"epoch {ep + 1}/{epochs} loss={total / nb:.4f} "
            f"lr={sched.get_last_lr()[0]:.2e} dev={device} {_fmt_hard(hm)}"
        )

    out = Path(model_path or DEFAULT_MODEL)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)
    print(f"saved {out}")
    return out
