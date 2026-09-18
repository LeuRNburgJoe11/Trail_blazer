"""
Feature extraction (Rail_Corrugation_Info_Kit.md Sections 1.1-1.2): corrugation
is a *spatial* wavy wear pattern with wavelength typically 2-50 cm, not a
fixed vibration frequency -- the vibration frequency it produces is
frequency = speed / wavelength, so the same defect shows up at a different
Hz in every file depending on how fast the train was going in that
particular 1-second recording.

To make the feature comparable across files at different speeds, PSD energy
is converted from the frequency axis to a *spatial wavenumber* axis
(cycles per metre = frequency / speed) before binning. A band of
[2, 50] cycles/m corresponds to wavelengths of [2 cm, 50 cm] -- exactly the
range the Info Kit describes -- regardless of the file's speed.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.signal import welch

from railpulse.rail.loader import FS_HZ

# Wavenumber band edges in cycles/metre, i.e. 1/wavelength_m.
# wavelength range ~ [2 cm, 50 cm] per the Info Kit -> wavenumber [2, 50] cyc/m.
WAVENUMBER_BAND_EDGES = [2.0, 4.0, 8.0, 16.0, 32.0, 50.0]


def time_domain_features(sig_matrix: np.ndarray) -> dict:
    """sig_matrix: (n_samples, n_channels). Returns per-feature arrays, one
    value per channel, for the caller to aggregate across channels."""
    rms = np.sqrt(np.mean(sig_matrix ** 2, axis=0))
    peak = np.max(np.abs(sig_matrix), axis=0)
    crest = np.divide(peak, rms, out=np.zeros_like(peak), where=rms > 0)
    kurt = stats.kurtosis(sig_matrix, axis=0, fisher=True, bias=False)
    return {"rms": rms, "crest_factor": crest, "kurtosis": kurt}


def wavenumber_band_energy(
    sig_matrix: np.ndarray, speed_mps: float, fs: int = FS_HZ,
    band_edges_cpm=WAVENUMBER_BAND_EDGES, nperseg: int = 2048,
) -> np.ndarray:
    """Returns (n_bands, n_channels) energy-per-band, band edges converted
    to Hz via freq = wavenumber * speed. If speed is ~0 (shouldn't happen
    in normal operation, but guards against a degenerate file), returns
    zeros rather than dividing by zero."""
    n_channels = sig_matrix.shape[1]
    n_bands = len(band_edges_cpm) - 1
    if speed_mps < 0.5:
        return np.zeros((n_bands, n_channels))

    freqs, psd = welch(sig_matrix, fs=fs, axis=0, nperseg=min(nperseg, sig_matrix.shape[0]))
    freq_edges = np.array(band_edges_cpm) * speed_mps
    energies = np.zeros((n_bands, n_channels))
    for b in range(n_bands):
        mask = (freqs >= freq_edges[b]) & (freqs < freq_edges[b + 1])
        if mask.any():
            energies[b] = psd[mask].sum(axis=0)
    return energies


def extract_side_feature_vector(channel_matrix: np.ndarray, speed_mps: float) -> dict:
    """channel_matrix: (n_samples, n_channels) for ALL axle-box channels
    (both vibration and shock, all positions/cars) belonging to one side.
    Aggregates across channels with max AND mean -- max preserves an
    isolated defect on a single axle box; mean gives the side's overall
    baseline level. Returns a flat, named feature dict."""
    time_feats = time_domain_features(channel_matrix)
    band_energy = wavenumber_band_energy(channel_matrix, speed_mps)  # (n_bands, n_channels)

    feats = {}
    for name, values in time_feats.items():
        feats[f"{name}_max"] = float(np.max(values))
        feats[f"{name}_mean"] = float(np.mean(values))
    for b in range(band_energy.shape[0]):
        feats[f"wavenumber_band{b}_energy_max"] = float(np.max(band_energy[b]))
        feats[f"wavenumber_band{b}_energy_mean"] = float(np.mean(band_energy[b]))
    feats["speed_mps"] = float(speed_mps)
    return feats


FEATURE_COLS = None  # populated lazily below, since it's just the keys of extract_side_feature_vector
