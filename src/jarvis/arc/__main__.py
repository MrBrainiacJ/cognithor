"""ARC-AGI-3 CLI entry point for Cognithor.

Usage:
    python -m jarvis.arc --game <game_id> [options]
    python -m jarvis.arc --list-games
    python -m jarvis.arc --mode benchmark
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m jarvis.arc",
        description="Cognithor ARC-AGI-3 Benchmark Agent",
    )
    parser.add_argument(
        "--game",
        metavar="GAME_ID",
        default="",
        help="Game/environment ID to play (required for single mode)",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "benchmark"],
        default="single",
        help="Run mode: single (default), benchmark (all games sequential)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help="Disable LLM planner (algorithmic-only mode)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Verbose output",
    )
    parser.add_argument(
        "--list-games",
        action="store_true",
        default=False,
        help="List available game IDs and exit",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default="",
        help="Path to Jarvis config.yaml (optional)",
    )
    return parser


def _load_config(config_path: str) -> Any:
    """Load Jarvis config, optionally from a custom path."""
    try:
        from jarvis.config import load_config

        if config_path:
            from pathlib import Path

            return load_config(Path(config_path))
        return load_config()
    except Exception as exc:
        print(f"[WARN] Could not load Jarvis config: {exc}", file=sys.stderr)
        return None


def _run_single(game_id: str, use_llm: bool, verbose: bool, config: Any) -> int:
    """Run the agent on a single game. Returns exit code."""
    try:
        from jarvis.arc.agent import CognithorArcAgent
    except ImportError as exc:
        print(
            f"[FAIL] Could not import CognithorArcAgent: {exc}\n"
            "Make sure jarvis[arc] dependencies are installed.",
            file=sys.stderr,
        )
        return 1

    if verbose:
        print(f"[INFO] Starting single game: {game_id}")
        print(f"[INFO] LLM planner: {'enabled' if use_llm else 'disabled'}")

    try:
        agent = CognithorArcAgent(
            game_id=game_id,
            use_llm_planner=use_llm,
        )
        result = agent.run()
    except Exception as exc:
        print(f"[FAIL] Agent run failed: {exc}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc()
        return 1

    print("[RESULT]")
    print(f"  game_id         : {result.get('game_id', game_id)}")
    print(f"  levels_completed: {result.get('levels_completed', 0)}")
    print(f"  total_steps     : {result.get('total_steps', 0)}")
    print(f"  score           : {result.get('score', 0.0):.4f}")
    return 0


def _run_benchmark(use_llm: bool, verbose: bool, config: Any) -> int:
    """Run all known games sequentially."""
    try:
        from jarvis.arc.adapter import ArcEnvironmentAdapter

        game_ids = ArcEnvironmentAdapter.list_games()
    except Exception:
        game_ids = []

    if not game_ids:
        print("[WARN] No game IDs found.", file=sys.stderr)
        return 1

    wins = 0
    total = len(game_ids)
    for i, game_id in enumerate(game_ids):
        if verbose:
            print(f"[{i + 1}/{total}] Playing {game_id}...")
        code = _run_single(game_id, use_llm, verbose, config)
        if code == 0:
            wins += 1

    print(f"\n[BENCHMARK] {wins}/{total} games won ({100 * wins / total:.1f}%)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --list-games
    if args.list_games:
        try:
            from jarvis.arc.adapter import ArcEnvironmentAdapter

            games = ArcEnvironmentAdapter.list_games()
        except ImportError as exc:
            print(f"[FAIL] ARC adapter not available: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"[FAIL] Could not list games: {exc}", file=sys.stderr)
            return 1

        if games:
            print("Available games:")
            for g in games:
                print(f"  {g}")
        else:
            print("No games found (ARC SDK may not be installed).")
        return 0

    config = _load_config(args.config)
    use_llm = not args.no_llm

    if args.mode == "single":
        if not args.game:
            print("[FAIL] --game is required for single mode.", file=sys.stderr)
            parser.print_help()
            return 1
        return _run_single(
            game_id=args.game,
            use_llm=use_llm,
            verbose=args.verbose,
            config=config,
        )

    if args.mode == "benchmark":
        return _run_benchmark(use_llm=use_llm, verbose=args.verbose, config=config)

    print(f"[FAIL] Unknown mode: {args.mode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
