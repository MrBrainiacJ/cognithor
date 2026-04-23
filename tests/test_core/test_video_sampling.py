# tests/test_core/test_video_sampling.py
from __future__ import annotations

import pytest

from cognithor.core.video_sampling import VideoSampling, _bucket_for_duration


class TestVideoSamplingDataclass:
    def test_fps_only(self):
        s = VideoSampling(fps=2.0, duration_sec=25.0)
        assert s.fps == 2.0
        assert s.num_frames is None
        assert s.duration_sec == 25.0

    def test_num_frames_only(self):
        s = VideoSampling(num_frames=32, duration_sec=900.0)
        assert s.num_frames == 32
        assert s.fps is None

    def test_as_mm_kwargs_fps(self):
        s = VideoSampling(fps=3.0)
        assert s.as_mm_kwargs() == {"fps": 3.0}

    def test_as_mm_kwargs_num_frames(self):
        s = VideoSampling(num_frames=64)
        assert s.as_mm_kwargs() == {"num_frames": 64}

    def test_as_mm_kwargs_raises_when_neither(self):
        s = VideoSampling()  # both None
        with pytest.raises(ValueError):
            s.as_mm_kwargs()


class TestBucketForDuration:
    # Spec bucket table (see design doc § "Frame Sampling"):
    # <10s → fps=3; 10-30s → fps=2; 30s-2min → fps=1;
    # 2-5min → num_frames=64; 5-15min → num_frames=32; >15min → num_frames=32
    @pytest.mark.parametrize(
        "dur,expected_fps,expected_num",
        [
            (5.0, 3.0, None),
            (9.99, 3.0, None),
            (10.0, 2.0, None),
            (29.99, 2.0, None),
            (30.0, 1.0, None),
            (119.99, 1.0, None),
            (120.0, None, 64),
            (299.99, None, 64),
            (300.0, None, 32),
            (899.99, None, 32),
            (900.0, None, 32),  # >15min still 32
            (3600.0, None, 32),
        ],
    )
    def test_buckets(
        self, dur: float, expected_fps: float | None, expected_num: int | None
    ) -> None:
        s = _bucket_for_duration(dur)
        assert s.fps == expected_fps
        assert s.num_frames == expected_num

    def test_zero_or_negative_duration_falls_back(self):
        # Defensive: upstream feeds us >0 but guard anyway
        s = _bucket_for_duration(0.0)
        assert s.num_frames == 32
        assert s.fps is None
        s = _bucket_for_duration(-5.0)
        assert s.num_frames == 32
