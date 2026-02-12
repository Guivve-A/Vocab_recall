"""
Tests for the SM-2 spaced-repetition algorithm.
"""

import pytest
from core.srs_engine import calculate_sm2


class TestCalculateSM2:
    """Validate SM-2 outputs for key quality grades."""

    def test_perfect_first_review(self):
        reps, ef, interval = calculate_sm2(quality=5, repetitions=0, easiness=2.5, interval=0)
        assert reps == 1
        assert interval == 1
        assert ef >= 2.5

    def test_perfect_second_review(self):
        reps, ef, interval = calculate_sm2(quality=5, repetitions=1, easiness=2.5, interval=1)
        assert reps == 2
        assert interval == 6

    def test_perfect_third_review(self):
        reps, ef, interval = calculate_sm2(quality=5, repetitions=2, easiness=2.5, interval=6)
        assert reps == 3
        assert interval == round(6 * 2.5)  # 15

    def test_fail_resets_repetitions(self):
        reps, ef, interval = calculate_sm2(quality=1, repetitions=5, easiness=2.5, interval=30)
        assert reps == 0
        assert interval == 1

    def test_easiness_never_below_1_3(self):
        """Repeated failures should not push EF below 1.3."""
        ef = 2.5
        for _ in range(20):
            _, ef, _ = calculate_sm2(quality=0, repetitions=0, easiness=ef, interval=1)
        assert ef >= 1.3

    def test_quality_3_is_passing(self):
        reps, ef, interval = calculate_sm2(quality=3, repetitions=0, easiness=2.5, interval=0)
        assert reps == 1

    def test_quality_2_is_fail(self):
        reps, ef, interval = calculate_sm2(quality=2, repetitions=3, easiness=2.5, interval=10)
        assert reps == 0
        assert interval == 1

    def test_invalid_quality_raises(self):
        with pytest.raises(ValueError):
            calculate_sm2(quality=6, repetitions=0, easiness=2.5, interval=0)
        with pytest.raises(ValueError):
            calculate_sm2(quality=-1, repetitions=0, easiness=2.5, interval=0)
