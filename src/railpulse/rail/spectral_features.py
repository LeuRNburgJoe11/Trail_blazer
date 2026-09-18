"""Time and frequency features for rail-side recordings."""

from __future__ import annotations

import numpy as np


def _channel_features(signal: np.ndarray, sampling_rate: float) -> list[float]:
	centered = signal - np.mean(signal)
	rms = float(np.sqrt(np.mean(signal * signal)))
	peak_to_peak = float(np.ptp(signal))
	peak = float(np.max(np.abs(signal)))
	crest = peak / max(rms, 1e-12)
	std = max(float(np.std(centered)), 1e-12)
	kurtosis = float(np.mean((centered / std) ** 4))
	spectrum = np.abs(np.fft.rfft(centered)) ** 2
	frequencies = np.fft.rfftfreq(signal.size, 1.0 / sampling_rate)
	band_edges = (0.0, 250.0, 1000.0, 2500.0, sampling_rate / 2.0)
	band_power = [float(spectrum[(frequencies >= lo) & (frequencies < hi)].mean()) for lo, hi in zip(band_edges, band_edges[1:])]
	probability = spectrum / max(float(spectrum.sum()), 1e-12)
	entropy = float(-np.sum(probability * np.log(probability + 1e-12)))
	dominant = float(frequencies[np.argmax(spectrum[1:]) + 1]) if spectrum.size > 1 else 0.0
	return [rms, peak_to_peak, crest, kurtosis, *band_power, entropy, dominant]


def extract_features(values: np.ndarray, sampling_rate: float = 10_000.0) -> dict[str, float]:
	if values.ndim != 2 or values.shape[1] != 129:
		raise ValueError("Rail recording must have shape (samples, 129)")
	features: dict[str, float] = {"speed": 0.0}
	from .speed import estimate_speed
	features["speed"] = estimate_speed(values[:, 0], sampling_rate)
	channel_features = [_channel_features(values[:, index], sampling_rate) for index in range(1, 129, 2)]
	for side, channels in (("side_i", channel_features[0::2]), ("side_ii", channel_features[1::2])):
		matrix = np.asarray(channels)
		for statistic, result in (("median", np.median(matrix, axis=0)), ("quantile", np.quantile(matrix, 0.9, axis=0)), ("max", np.max(matrix, axis=0)), ("std", np.std(matrix, axis=0))):
			for index, value in enumerate(result):
				features[f"{side}_{statistic}_{index}"] = float(value)
	return features
