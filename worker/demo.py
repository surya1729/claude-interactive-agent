"""CLI: python demo.py or python demo.py "do something" """

import argparse
import os
from core.pi_rpc import run_interactive

WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXT = os.path.join(WORKER_DIR, "extensions", "python.ts")


def main():
    p = argparse.ArgumentParser(description="Run a Pi agent task")
    p.add_argument("task", nargs="?", default=None, help="Optional task (opens TUI if omitted)")
    p.add_argument("--cwd", default=None, help="Working directory for the agent")
    p.add_argument("--model", default="anthropic/claude-haiku-4.5", help="Model ID (e.g. anthropic/claude-haiku-4.5)")
    args = p.parse_args()

    run_interactive(
        model=args.model,
        cwd=args.cwd,
        extensions=[PYTHON_EXT],
    )


if __name__ == "__main__":
    main()
