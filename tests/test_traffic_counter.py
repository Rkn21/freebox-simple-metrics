"""Unit tests for the WAN byte counter without a Home Assistant runtime."""

from pathlib import Path
import sys
import unittest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "custom_components" / "freebox_simple_metrics"),
)

from traffic_counter import TrafficCounter


class TrafficCounterTest(unittest.TestCase):
    def setUp(self):
        self.counter = TrafficCounter(max_gap=60)
        self.base = 12_000_000_000_000
        for t in (0, 5, 10):
            self.sample(self.base, t)

    def sample(self, raw, now, bandwidth=1_000_000_000):
        self.counter.update(raw, now, bandwidth)
        return self.counter.total

    def test_normal_traffic_at_link_rate(self):
        self.assertEqual(self.sample(self.base + 625_000_000, 15), self.base + 625_000_000)

    def test_one_zero_then_old_counter_returns(self):
        self.assertEqual(self.sample(0, 15), self.base)
        self.assertTrue(self.counter.pending)
        self.assertEqual(self.sample(self.base + 100_000_000, 20), self.base + 100_000_000)
        self.assertFalse(self.counter.pending)

    def test_zero_held_then_multi_terabyte_rebound(self):
        for t in (15, 20, 25):
            self.assertEqual(self.sample(0, t), self.base)
        self.assertEqual(self.sample(self.base, 30), self.base)
        self.assertEqual(self.sample(self.base + 40, 35), self.base)
        self.assertEqual(self.sample(self.base + 60, 40), self.base + 60)

    def test_real_reset_credits_only_observed_growth(self):
        self.assertEqual(self.sample(100, 15), self.base)
        self.assertEqual(self.sample(280, 20), self.base)
        self.assertEqual(self.sample(540, 25), self.base + 440)
        self.assertEqual(self.sample(610, 30), self.base + 510)

    def test_upward_jump_is_not_counted_even_if_it_persists(self):
        high = self.base * 2
        self.assertEqual(self.sample(high, 15), self.base)
        self.assertEqual(self.sample(high + 100, 20), self.base)
        self.assertEqual(self.sample(high + 240, 25), self.base + 240)

    def test_single_upward_jump_does_not_move_anchor(self):
        self.assertEqual(self.sample(self.base * 2, 15), self.base)
        self.assertEqual(self.sample(self.base + 200, 20), self.base + 200)

    def test_advertised_uplink_bounds_delta(self):
        self.assertEqual(self.sample(self.base + 500_000_000, 15, 20_000_000), self.base)
        self.assertTrue(self.counter.pending)

    def test_invalid_samples_are_never_exposed(self):
        for t, value in zip((15, 20, 25, 30, 35), (None, False, -1, "0", 1 << 64)):
            self.assertEqual(self.sample(value, t), self.base)
        self.assertEqual(self.sample(self.base + 123, 40), self.base + 123)

    def test_long_gap_rebases_without_guessing_usage(self):
        self.assertEqual(self.sample(self.base * 2, 120), self.base)
        self.assertEqual(self.sample(self.base * 2 + 50, 125), self.base + 50)

    def test_restart_restores_total_instead_of_raw(self):
        self.counter = TrafficCounter(max_gap=60, restored_total=self.base)
        self.assertEqual(self.sample(0, 0), self.base)
        self.assertEqual(self.sample(50, 5), self.base + 50)

    def test_first_start_does_not_commit_a_one_sample_spike(self):
        self.counter = TrafficCounter(max_gap=60)
        self.assertIsNone(self.sample(self.base * 2, 0))
        self.assertIsNone(self.sample(self.base, 5))
        self.assertIsNone(self.sample(self.base + 100, 10))
        self.assertEqual(self.sample(self.base + 150, 15), self.base + 150)
