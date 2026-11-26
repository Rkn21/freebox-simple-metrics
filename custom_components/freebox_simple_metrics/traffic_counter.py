"""Reject discontinuities in the Freebox WAN byte counters."""

from __future__ import annotations

from typing import TypeGuard

_MAX_BITS_PER_SECOND = 10_000_000_000
_MAX_COUNTER = (1 << 64) - 1
_CONFIRMATION_SAMPLES = 3


def _is_counter(value: object) -> TypeGuard[int]:
    return type(value) is int and 0 <= value <= _MAX_COUNTER


class TrafficCounter:
    """Keep a monotonic total from plausible, observed counter increments."""

    def __init__(self, *, max_gap: float, restored_total: object = None) -> None:
        self.total: int | None = restored_total if _is_counter(restored_total) else None
        self._max_gap = max_gap
        self._accepted: tuple[int, float] | None = None
        self._candidate: tuple[int, float] | None = None
        self._candidate_count = 0
        self._candidate_bytes = 0

    @property
    def pending(self) -> bool:
        """Return whether a new counter range is being confirmed."""
        return self._candidate is not None

    def _anchor(self, sample: tuple[int, float]) -> None:
        self._accepted = sample
        self._candidate = None
        self._candidate_count = 0
        self._candidate_bytes = 0

    def update(self, raw: object, now: float, bandwidth: object) -> None:
        """Update from one poll; bandwidth is the advertised link rate in bit/s."""
        if not _is_counter(raw):
            self._candidate = None
            return

        if self._candidate is not None and now <= self._candidate[1]:
            return
        bits_per_second: float = _MAX_BITS_PER_SECOND
        if type(bandwidth) is int and bandwidth > 0:
            bits_per_second = min(bits_per_second, bandwidth * 1.25)
        bytes_per_second = bits_per_second / 8

        sample = (raw, now)
        if self._accepted is None:
            if self.total is None:
                self._confirm_range(sample, bytes_per_second)
            else:
                # A restored total must not count the first sample after a restart.
                self._anchor(sample)
            return

        accepted, previous_time = self._accepted
        elapsed = now - previous_time
        if elapsed <= 0:
            return
        if elapsed > self._max_gap:
            self._anchor(sample)
            return

        # Poll completion can differ slightly from the device's sample time.
        ceiling = bytes_per_second * (elapsed + 2)
        delta = raw - accepted
        assert self.total is not None
        if 0 <= delta <= ceiling:
            self.total += delta
            self._anchor(sample)
            return

        self._confirm_range(sample, bytes_per_second)

    def _confirm_range(self, sample: tuple[int, float], bytes_per_second: float) -> None:
        raw, now = sample
        if self._candidate is not None:
            candidate, candidate_time = self._candidate
            delta = raw - candidate
            elapsed = now - candidate_time
            if elapsed <= self._max_gap and 0 <= delta <= bytes_per_second * (elapsed + 2):
                self._candidate = sample
                self._candidate_count += 1
                self._candidate_bytes += delta
                if self._candidate_count >= _CONFIRMATION_SAMPLES:
                    # Count only growth within the confirmed range, never the jump.
                    self.total = raw if self.total is None else self.total + self._candidate_bytes
                    self._anchor(sample)
                return

        self._candidate = sample
        self._candidate_count = 1
        self._candidate_bytes = 0
