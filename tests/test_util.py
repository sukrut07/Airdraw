"""
Unit tests for AirDraw utility functions (geometry, vector math, distance).
"""
import pytest
import numpy as np
from util import xy_euclidean_dist, clamp, vectorize, vector_magnitude, cos_angle


def test_xy_euclidean_dist():
    assert xy_euclidean_dist((0, 0), (3, 4)) == pytest.approx(5.0)
    assert xy_euclidean_dist((1, 1), (1, 1)) == pytest.approx(0.0)
    assert xy_euclidean_dist((-1, -1), (2, 3)) == pytest.approx(5.0)


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10


def test_vectorize():
    u = [1, 2, 3]
    v = [4, 6, 8]
    assert vectorize(u, v) == [3, 4, 5]

    with pytest.raises(AssertionError):
        vectorize([1, 2], [1, 2, 3])


def test_vector_magnitude():
    assert vector_magnitude([3, 4]) == pytest.approx(5.0)
    assert vector_magnitude([0, 0, 0]) == pytest.approx(0.0)
    assert vector_magnitude([1, 2, 2]) == pytest.approx(3.0)


def test_cos_angle():
    # Parallel vectors -> cos = 1.0
    assert cos_angle([1, 0], [2, 0]) == pytest.approx(1.0)
    # Perpendicular vectors -> cos = 0.0
    assert cos_angle([1, 0], [0, 1]) == pytest.approx(0.0)
    # Opposite vectors -> cos = -1.0
    assert cos_angle([1, 0], [-1, 0]) == pytest.approx(-1.0)
    # Zero vector -> safe return 0
    assert cos_angle([0, 0], [1, 1]) == 0.0
    assert cos_angle([1, 1], [0, 0]) == 0.0
