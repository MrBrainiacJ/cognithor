"""Video sampling: map video duration to fps/num_frames for a vLLM request.

Maps duration to the bucket table from
docs/superpowers/specs/2026-04-23-video-input-vllm-design.md.
Pure logic only; I/O entry point ``resolve_sampling`` is added in Task 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VideoSampling:
    """Resolved per-video sampling spec.

    Exactly one of `fps` or `num_frames` is set when sampling is active.
    Both None is a default-constructed placeholder and will raise from
    `as_mm_kwargs()`.
    """

    fps: float | None = None
    num_frames: int | None = None
    duration_sec: float | None = None  # for logging/UI, not sent to vLLM

    def as_mm_kwargs(self) -> dict[str, Any]:
        """Return the dict suitable for `extra_body.mm_processor_kwargs.video`.

        Shape confirmed by Task-1 spike.
        """
        if self.fps is not None:
            return {"fps": self.fps}
        if self.num_frames is not None:
            return {"num_frames": self.num_frames}
        raise ValueError("VideoSampling has neither fps nor num_frames set")


# Bucket thresholds in seconds
_BUCKET_LT_10 = 10.0
_BUCKET_LT_30 = 30.0
_BUCKET_LT_2MIN = 120.0
_BUCKET_LT_5MIN = 300.0
_BUCKET_LT_15MIN = 900.0


def _bucket_for_duration(duration_sec: float) -> VideoSampling:
    """Map a duration in seconds to a VideoSampling per the spec's bucket table.

    Defensive default for non-positive durations: `num_frames=32` so callers
    don't have to special-case ffprobe edge-cases.
    """
    if duration_sec <= 0:
        return VideoSampling(num_frames=32, duration_sec=duration_sec)
    if duration_sec < _BUCKET_LT_10:
        return VideoSampling(fps=3.0, duration_sec=duration_sec)
    if duration_sec < _BUCKET_LT_30:
        return VideoSampling(fps=2.0, duration_sec=duration_sec)
    if duration_sec < _BUCKET_LT_2MIN:
        return VideoSampling(fps=1.0, duration_sec=duration_sec)
    if duration_sec < _BUCKET_LT_5MIN:
        return VideoSampling(num_frames=64, duration_sec=duration_sec)
    # 5 min - 15 min AND > 15 min both use num_frames=32; UI banner is
    # a display concern not a sampling one.
    return VideoSampling(num_frames=32, duration_sec=duration_sec)
