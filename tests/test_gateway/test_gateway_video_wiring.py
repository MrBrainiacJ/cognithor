from __future__ import annotations


class TestClassifyAttachments:
    def test_video_and_image_classified_correctly(self):
        from cognithor.gateway.gateway import _classify_attachments

        images, video, rejected = _classify_attachments(
            [
                "/tmp/pic.png",
                "/tmp/clip.mp4",
            ]
        )
        assert images == ["/tmp/pic.png"]
        assert video == "/tmp/clip.mp4"
        assert rejected == []

    def test_second_video_is_rejected(self):
        from cognithor.gateway.gateway import _classify_attachments

        images, video, rejected = _classify_attachments(
            [
                "/tmp/clip1.mp4",
                "/tmp/clip2.mp4",
                "/tmp/clip3.webm",
            ]
        )
        assert images == []
        assert video == "/tmp/clip1.mp4"  # first wins
        assert rejected == ["/tmp/clip2.mp4", "/tmp/clip3.webm"]

    def test_no_videos_returns_none(self):
        from cognithor.gateway.gateway import _classify_attachments

        images, video, rejected = _classify_attachments(
            [
                "/tmp/pic.png",
                "/tmp/doc.pdf",
            ]
        )
        assert video is None
        assert rejected == []
        assert images == ["/tmp/pic.png"]

    def test_empty_input_returns_empty(self):
        from cognithor.gateway.gateway import _classify_attachments

        images, video, rejected = _classify_attachments([])
        assert images == []
        assert video is None
        assert rejected == []
