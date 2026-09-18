"""Produce training-only diagnostics and a model comparison figure."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from railpulse.shm.loader import load_recording
from railpulse.shm.rainflow_features import cycle_arrays


def main():
    output = ROOT / "outputs/shm"
    comparison = pd.read_csv(output / "model_comparison.csv")
    oof = pd.read_csv(output / "out_of_fold_predictions.csv")
    selected = oof[(oof.model == "nested_selection") & (oof.repeat == 0)]
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    models = comparison[comparison.model != "nested_selection"].sort_values("mape")
    axes[0].barh(models.model, models.mape * 100, color="#216e89")
    axes[0].invert_yaxis()
    axes[0].set(xlabel="Mean absolute percentage error (%)", title="Same held-out files for every model")
    axes[1].scatter(selected.target, selected.prediction, s=24, alpha=0.8, color="#216e89")
    limits = [min(selected.target.min(), selected.prediction.min()) * 0.8,
              max(selected.target.max(), selected.prediction.max()) * 1.2]
    axes[1].plot(limits, limits, "--", color="gray")
    axes[1].set(xscale="log", yscale="log", xlabel="Reference damage", ylabel="Held-out prediction",
                title="Nested selection · first repetition", xlim=limits, ylim=limits)
    axes[2].scatter(selected.target, selected.ape * 100, s=24, color="#216e89")
    axes[2].set(xscale="log", xlabel="Reference damage", ylabel="Absolute percentage error (%)",
                title="Error across damage levels")
    figure.savefig(output / "validation_diagnostics.png", dpi=160)
    plt.close(figure)
    signal = load_recording(ROOT / "data/SHM/Train/train01.csv").stress
    amplitude, _, count = cycle_arrays(signal)
    edges = np.linspace(0, amplitude.max(), 31)
    centres = (edges[:-1] + edges[1:]) / 2
    figure, axes = plt.subplots(1, 3, figsize=(14, 4), layout="constrained")
    axes[0].plot(np.arange(4000), signal[:4000], linewidth=0.6, color="#216e89")
    axes[0].set(xlabel="Sample index", ylabel="Stress (unspecified source units)", title="train01 · first 4,000 samples")
    axes[1].bar(centres, np.histogram(amplitude, edges, weights=count)[0], width=np.diff(edges), color="#216e89")
    axes[1].set(xlabel="Cycle amplitude (range / 2)", ylabel="Weighted cycle count", title="Full-record rainflow cycles")
    contribution = np.histogram(amplitude, edges, weights=count * amplitude ** 5)[0]
    axes[2].bar(centres, 100 * contribution / contribution.sum(), width=np.diff(edges), color="#216e89")
    axes[2].set(xlabel="Cycle amplitude (source units)", ylabel="Share of fifth-power proxy (%)",
                title="Large cycles dominate the damage proxy")
    figure.savefig(output / "signal_and_cycle_diagnostics.png", dpi=160)
    plt.close(figure)
    print(f"Wrote diagnostics to {output}")


if __name__ == "__main__":
    main()
