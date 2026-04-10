"""ARC-AGI-3 Offline CNN Training Pipeline.

Runs the agent on all available games for many episodes, collecting
training data. Then trains the CNN on the accumulated experience for
better action prediction in future runs.

Usage:
    python -m jarvis.arc.offline_trainer --episodes 100 --games ls20,sc25
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from cognithor.utils.logging import get_logger

__all__ = ["OfflineTrainer"]

log = get_logger(__name__)

_WEIGHTS_DIR = Path.home() / ".cognithor" / "arc" / "weights"


class OfflineTrainer:
    """Collect experience across multiple games and train CNN offline."""

    def __init__(
        self,
        games: list[str] | None = None,
        episodes_per_game: int = 10,
        steps_per_episode: int = 500,
        weights_dir: Path | None = None,
    ) -> None:
        self.games = games or ["ls20"]
        self.episodes_per_game = episodes_per_game
        self.steps_per_episode = steps_per_episode
        self._weights_dir = weights_dir or _WEIGHTS_DIR
        self._weights_dir.mkdir(parents=True, exist_ok=True)
        self._experience: list[tuple[Any, int, bool]] = []  # (grid, action_idx, changed)

    def collect_experience(self) -> int:
        """Run agent on all games and collect (grid, action, changed) tuples."""
        try:
            import arc_agi
            from arcengine import GameAction
        except ImportError:
            log.error("arc_agi SDK not installed")
            return 0

        total = 0
        for game_id in self.games:
            for episode in range(self.episodes_per_game):
                try:
                    arc = arc_agi.Arcade()
                    env = arc.make(game_id)
                    if env is None:
                        continue
                    obs = env.reset()
                    actions = [a for a in env.action_space if a != GameAction.RESET]
                    if not actions:
                        break

                    prev_frame = np.array(obs.frame)
                    if prev_frame.ndim == 3 and prev_frame.shape[0] == 1:
                        prev_frame = prev_frame[0]

                    for step in range(self.steps_per_episode):
                        action = actions[step % len(actions)]
                        obs = env.step(action)
                        curr_frame = np.array(obs.frame)
                        if curr_frame.ndim == 3 and curr_frame.shape[0] == 1:
                            curr_frame = curr_frame[0]

                        changed = not np.array_equal(curr_frame, prev_frame)
                        self._experience.append((prev_frame.copy(), action.value, changed))
                        total += 1
                        prev_frame = curr_frame

                        state_str = str(obs.state)
                        if "GAME_OVER" in state_str:
                            obs = env.step(GameAction.RESET)
                            prev_frame = np.array(obs.frame)
                            if prev_frame.ndim == 3:
                                prev_frame = prev_frame[0]
                        elif "WIN" in state_str:
                            break

                except Exception as exc:
                    log.debug(
                        "offline_collect_error", game=game_id, episode=episode, error=str(exc)[:60]
                    )

                log.info(
                    "offline_episode_done",
                    game=game_id,
                    episode=episode + 1,
                    total_experience=total,
                )

        log.info("offline_collection_done", total=total, games=len(self.games))
        return total

    def train(self, epochs: int = 10, batch_size: int = 64) -> float:
        """Train CNN on collected experience. Returns final loss."""
        try:
            from cognithor.arc.cnn_model import _TORCH_AVAILABLE, OnlineTrainer

            if not _TORCH_AVAILABLE:
                log.error("torch not available")
                return -1.0
        except ImportError:
            log.error("cnn_model not available")
            return -1.0

        if not self._experience:
            log.warning("no experience to train on")
            return -1.0

        trainer = OnlineTrainer(device="cuda")

        # Feed all experience
        for grid, action_idx, changed in self._experience:
            trainer.add_experience(grid, action_idx, frame_changed=changed)

        # Force additional training epochs
        log.info("offline_training_start", samples=len(self._experience), epochs=epochs)
        losses = []
        for epoch in range(epochs):
            loss = trainer._train_step()
            losses.append(loss)
            if (epoch + 1) % 5 == 0:
                log.info("offline_epoch", epoch=epoch + 1, loss=f"{loss:.4f}")

        final_loss = losses[-1] if losses else -1.0

        # Save weights
        import torch

        weights_path = self._weights_dir / "action_predictor.pt"
        torch.save(trainer.model.state_dict(), weights_path)
        log.info("offline_weights_saved", path=str(weights_path), loss=f"{final_loss:.4f}")

        # Save metadata
        meta = {
            "games": self.games,
            "total_experience": len(self._experience),
            "epochs": epochs,
            "final_loss": final_loss,
            "timestamp": time.time(),
        }
        meta_path = self._weights_dir / "training_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))

        return final_loss

    def run(self, epochs: int = 10) -> dict:
        """Full pipeline: collect → train → save."""
        t0 = time.time()
        total = self.collect_experience()
        loss = self.train(epochs=epochs)
        duration = time.time() - t0

        result = {
            "total_experience": total,
            "final_loss": loss,
            "duration_seconds": duration,
            "weights_path": str(self._weights_dir / "action_predictor.pt"),
        }
        log.info("offline_training_complete", **result)
        return result
