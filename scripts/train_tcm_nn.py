#!/usr/bin/env python3
"""Train the Charybdis learned TCM matcher on GPU (RunPod-friendly)."""
from console.charybdis_nn import train

if __name__ == "__main__":
    train(n_samples=16000, epochs=10, batch=512)
