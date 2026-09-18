import numpy as np
import pytest
import rainflow

from railpulse.shm.rainflow_features import cycle_arrays, extract_features, power_column, build_features


def test_known_triangle_and_half_cycles():
    amplitudes, means, counts = cycle_arrays(np.array([0, 2, 0, 2, 0.0]))
    assert counts.sum() == 2
    np.testing.assert_array_equal(amplitudes, 1)
    np.testing.assert_array_equal(means, 1)
    assert np.dot(counts, amplitudes ** 5) == 2
    a, _, n = cycle_arrays(np.array([0, 1, 2.0]))
    assert a.tolist() == [1] and n.tolist() == [0.5]


def test_plateaus_and_constant_signal():
    a = extract_features(np.array([0, 2, 0, 2, 0.0]))
    b = extract_features(np.array([0, 0, 2, 2, 0, 0, 2, 2, 0, 0.0]))
    assert a[power_column(5)] == b[power_column(5)]
    zero = extract_features(np.ones(30))
    assert zero[power_column(5)] == zero["cycle_count"] == 0
    assert np.isfinite(list(zero.values())).all()


def test_accelerated_counting_matches_reference_on_random_signals():
    generator = np.random.default_rng(42)
    for _ in range(30):
        signal = np.round(generator.normal(size=301), 1)
        a, means, counts = cycle_arrays(signal)
        reference = list(rainflow.extract_cycles(signal))
        for power in (2, 3, 5, 8):
            expected = sum(n * (r / 2) ** power for r, _, n, _, _ in reference)
            assert np.dot(counts, a ** power) == pytest.approx(expected, rel=1e-12)


def test_absolute_amplitude_scaling_and_offset_invariance():
    x = np.array([1, -2, 3, -1, 5, 0, 1.0])
    base, scaled, shifted = [extract_features(s) for s in (x, 2 * x, x + 100)]
    for power in (2, 3, 5, 8):
        name = power_column(power)
        assert scaled[name] == pytest.approx(base[name] * 2 ** power)
        assert shifted[name] == pytest.approx(base[name])


def test_cache_invalidates_on_changed_content(tmp_path):
    inputs = tmp_path / "data"
    inputs.mkdir()
    path = inputs / "signal.csv"
    path.write_text("0\n2\n0\n2\n0\n")
    first, _ = build_features(inputs, tmp_path / "cache")
    second, manifest = build_features(inputs, tmp_path / "cache")
    assert manifest.cached.all()
    np.testing.assert_array_equal(first.values, second.values)
    path.write_text("0\n4\n0\n4\n0\n")
    third, manifest = build_features(inputs, tmp_path / "cache")
    assert not manifest.cached.any()
    assert third.iloc[0][power_column(5)] == first.iloc[0][power_column(5)] * 32

