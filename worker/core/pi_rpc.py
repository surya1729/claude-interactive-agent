"""Python client for Pi agent.

Two modes:
1. run_interactive() — launches pi with its built-in TUI, hands over the terminal
2. PiRPC class — RPC mode for programmatic control (JSON lines on stdin/stdout)
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime

# adding it for windows
PI_CMD = "pi.cmd" if sys.platform == "win32" else "pi"


def run_interactive(model=None, extensions=None, system_prompt=None, cwd=None, no_tools=False, tools=None):
    """Launch pi with its built-in TUI. Blocks until pi exits."""
    cmd = [PI_CMD, "--model", model or "anthropic/claude-haiku-4.5"]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    if no_tools:
        cmd += ["--no-tools"]
    elif tools:
        cmd += ["--tools", tools]
    for ext in (extensions or []):
        cmd += ["-e", ext]
    return subprocess.run(cmd, cwd=cwd)


class PiRPC:
    """Spawn Pi in RPC mode, send prompts, stream output."""

    def __init__(self, model=None, cwd=None, tools=None, no_tools=False, extensions=None, log_dir=None, quiet=False, system_prompt=None):
        self.model = model or "anthropic/claude-haiku-4.5"
        self.cwd = cwd
        self.tools = tools
        self.no_tools = no_tools
        self.quiet = quiet
        self.extensions = extensions or []
        self.system_prompt = system_prompt
        self._proc = None
        self._log_file = None
        self._request_id = 0

        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            self._log_path = os.path.join(log_dir, f"{ts}.log")

    async def start(self):
        cmd = [PI_CMD, "--mode", "rpc", "--no-session", "--model", self.model]
        if self.system_prompt:
            cmd += ["--append-system-prompt", self.system_prompt]
        if self.no_tools:
            cmd += ["--no-tools"]
        elif self.tools:
            cmd += ["--tools", self.tools]
        for ext in self.extensions:
            cmd += ["-e", ext]
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=self.cwd,
            limit=10 * 1024 * 1024,
        )
        if hasattr(self, "_log_path"):
            self._log_file = open(self._log_path, "w")
            self._log("SESSION_START", {"model": self.model, "cwd": self.cwd, "cmd": cmd})

    def _log(self, event_type, data=None):
        if not self._log_file:
            return
        entry = {"ts": datetime.now().isoformat(), "event": event_type}
        if data:
            entry["data"] = data
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    async def _send(self, obj):
        self._request_id += 1
        obj["id"] = str(self._request_id)
        line = json.dumps(obj) + "\n"
        self._proc.stdin.write(line.encode())
        await self._proc.stdin.drain()
        self._log("SEND", obj)
        return obj["id"]

    async def _read_line(self):
        line = await self._proc.stdout.readline()
        if not line:
            return None
        return json.loads(line)

    async def _send_and_wait(self, obj):
        """Send a command and wait for its response."""
        req_id = await self._send(obj)
        while True:
            event = await self._read_line()
            if event is None:
                return None
            if event.get("type") == "response" and event.get("id") == req_id:
                return event
            # Discard other events while waiting for this response

    async def prompt(self, message: str) -> dict:
        """Send a prompt, stream live output, return clean result via get_messages."""
        await self._send({"type": "prompt", "message": message})
        self._log("PROMPT", {"message": message})

        turn_count = 0
        while True:
            event = await self._read_line()
            if event is None:
                break

            t = event.get("type")

            if t == "turn_start":
                turn_count += 1
                if not self.quiet:
                    print(f"\n[turn {turn_count}]", flush=True)
                self._log("TURN", {"n": turn_count})

            elif t == "message_update":
                ae = event.get("assistantMessageEvent", {})
                ae_type = ae.get("type")

                if ae_type == "text_delta":
                    if not self.quiet:
                        print(ae.get("delta", ""), end="", flush=True)

                elif ae_type == "toolcall_end":
                    tc = ae.get("toolCall", {})
                    name = tc.get("name", "?")
                    args = tc.get("arguments", {})
                    self._log("TOOL_CALL", {"tool": name, "args": args})
                    if not self.quiet:
                        print(f"\n  [{name}]", flush=True)
                        if name == "python" and "code" in args:
                            for ln in args["code"].split("\n")[:10]:
                                print(f"    {ln}", flush=True)
                        elif args:
                            print(f"    {str(args)[:300]}", flush=True)

                elif ae_type == "thinking_end":
                    content = ae.get("content", "")
                    if content:
                        self._log("THINKING", {"summary": content[:500]})
                        if not self.quiet:
                            print(f"  ({content[:80]})", flush=True)

            elif t == "agent_end":
                if not self.quiet:
                    print()
                self._log("AGENT_END", {"turns": turn_count})
                break

        # Ask Pi for the clean final state instead of reconstructing it
        messages = await self.get_messages()
        stats = await self.get_session_stats()
        return {"messages": messages, "stats": stats, "turns": turn_count}

    async def get_messages(self):
        """Get full conversation history from Pi."""
        resp = await self._send_and_wait({"type": "get_messages"})
        if resp and resp.get("success"):
            return resp.get("data", {}).get("messages", [])
        return []

    async def get_session_stats(self):
        """Get session stats (tokens, cost) from Pi."""
        resp = await self._send_and_wait({"type": "get_session_stats"})
        if resp and resp.get("success"):
            return resp.get("data", {})
        return {}

    async def abort(self):
        await self._send({"type": "abort"})

    async def close(self):
        if self._log_file:
            self._log("SESSION_END")
            self._log_file.close()
        if self._proc:
            if self._proc.stdin and not self._proc.stdin.is_closing():
                self._proc.stdin.close()
            if self._proc.returncode is None:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    self._proc.kill()
                    await self._proc.wait()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.close()


def print_stats(result: dict):
    """Print cost/usage from get_session_stats result."""
    stats = result.get("stats", {})
    if not stats:
        print("No stats available.")
        return
    tokens = stats.get("tokens", {})
    cost = stats.get("cost", 0)
    turns = result.get("turns", "?")
    tool_calls = stats.get("toolCalls", 0)
    print(f"\nTurns: {turns}  Tools: {tool_calls}  "
          f"Tokens: {tokens.get('total', '?')}  Cost: ${cost:.4f}")
