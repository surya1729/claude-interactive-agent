"""Execute Python code in a persistent Jupyter kernel.

First call starts the kernel (~3s). Subsequent calls reuse it (~50ms).
Variables, imports, and functions persist across calls.

Usage:
    python kernel_exec.py '<code>'
    python kernel_exec.py '<code>' --cwd /some/dir
    python kernel_exec.py --stop          # kill the kernel
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    def _process_alive(pid: int) -> bool:
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        exit_code = ctypes.wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == 259  # STILL_ACTIVE

    def _kill_process(pid: int):
        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
else:
    def _process_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _kill_process(pid: int):
        try:
            os.kill(pid, 15)
        except OSError:
            pass

WORKER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL_DIR = os.path.join(WORKER_DIR, ".kernel")
CONNECTION_FILE = os.path.join(KERNEL_DIR, "connection.json")
PID_FILE = os.path.join(KERNEL_DIR, "kernel.pid")
LOG_DIR = os.path.join(WORKER_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, f"kernel_{datetime.now().strftime('%Y%m%d')}.log"),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("kernel_exec")

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def is_kernel_alive():
    if not os.path.exists(PID_FILE):
        log.debug("is_kernel_alive: PID file not found")
        return False
    with open(PID_FILE) as f:
        pid = int(f.read().strip())
    alive = _process_alive(pid)
    log.debug(f"is_kernel_alive: pid={pid} {'alive' if alive else 'dead'}")
    return alive


def start_kernel():
    """Start a new ipykernel as a detached process, wait until ready."""
    log.info("start_kernel: starting new kernel")
    os.makedirs(KERNEL_DIR, exist_ok=True)

    for f in [CONNECTION_FILE, PID_FILE]:
        if os.path.exists(f):
            os.remove(f)

    proc = subprocess.Popen(
        [sys.executable, "-m", "ipykernel_launcher", "-f", CONNECTION_FILE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    log.info(f"start_kernel: pid={proc.pid}")

    from jupyter_client import BlockingKernelClient

    for _ in range(50):
        if os.path.exists(CONNECTION_FILE):
            try:
                kc = BlockingKernelClient()
                kc.load_connection_file(CONNECTION_FILE)
                kc.start_channels()
                kc.wait_for_ready(timeout=2)
                # Add worker-poc to sys.path so agent can import libs
                startup_id = kc.execute(
                    f"import sys; sys.path.insert(0, {WORKER_DIR!r})"
                )
                kc.get_shell_msg(timeout=5)
                _drain_iopub(kc, startup_id)
                log.info(f"start_kernel: ready, WORKER_DIR={WORKER_DIR}")
                return kc
            except Exception as e:
                log.debug(f"start_kernel: waiting... ({e})")
                time.sleep(0.1)
                continue
        time.sleep(0.1)

    raise RuntimeError("Kernel failed to start within 5 seconds")


def connect_to_kernel():
    from jupyter_client import BlockingKernelClient

    kc = BlockingKernelClient()
    kc.load_connection_file(CONNECTION_FILE)
    kc.start_channels()

    # Warm up the iopub subscription by executing a no-op and fully draining
    # its messages. This guarantees subsequent executions see their own output.
    warm_id = kc.execute("pass")
    kc.get_shell_msg(timeout=5)
    _drain_iopub(kc, warm_id)

    return kc


def _drain_iopub(kc, msg_id):
    """Drain iopub messages for a specific execution until idle."""
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=5)
            if (
                msg["msg_type"] == "status"
                and msg["content"]["execution_state"] == "idle"
                and msg["parent_header"].get("msg_id") == msg_id
            ):
                break
        except Exception:
            break


def stop_kernel():
    if not os.path.exists(PID_FILE):
        return
    with open(PID_FILE) as f:
        pid = int(f.read().strip())
    _kill_process(pid)
    for f in [CONNECTION_FILE, PID_FILE]:
        if os.path.exists(f):
            os.remove(f)


def execute_code(kc, code):
    msg_id = kc.execute(code)

    stdout_parts = []
    result_value = None
    error = None

    reply = kc.get_shell_msg(timeout=30)
    if reply["content"]["status"] == "error":
        tb = reply["content"].get("traceback", [])
        error = ANSI_ESCAPE.sub("", "\n".join(tb))

    # Drain iopub, only collecting messages belonging to this execution
    while True:
        try:
            msg = kc.get_iopub_msg(timeout=5)
            parent_id = msg["parent_header"].get("msg_id")
            if parent_id != msg_id:
                continue  # Skip messages from other executions

            mt = msg["msg_type"]

            if mt == "stream" and msg["content"]["name"] == "stdout":
                stdout_parts.append(msg["content"]["text"])

            elif mt == "execute_result":
                result_value = msg["content"]["data"].get("text/plain", "")

            elif mt == "error":
                tb = msg["content"].get("traceback", [])
                error = ANSI_ESCAPE.sub("", "\n".join(tb))

            elif mt == "status" and msg["content"]["execution_state"] == "idle":
                break
        except Exception:
            break

    if error:
        return {"output": None, "error": error}

    parts = []
    if stdout_parts:
        parts.append("".join(stdout_parts).rstrip())
    if result_value:
        parts.append(result_value)

    return {"output": "\n".join(parts) if parts else "(no output)", "error": None}


def run(code, cwd=None):
    log.info(f"run: code={code[:80]!r}")
    try:
        if is_kernel_alive() and os.path.exists(CONNECTION_FILE):
            log.info("run: reusing existing kernel")
            try:
                kc = connect_to_kernel()
            except Exception as e:
                log.warning(f"run: failed to connect, restarting kernel: {e}")
                stop_kernel()
                kc = start_kernel()
        else:
            log.info("run: starting fresh kernel")
            kc = start_kernel()

        if cwd:
            execute_code(kc, f"import os; os.chdir({cwd!r})")

        result = execute_code(kc, code)
        log.info(f"run: result error={result.get('error') is not None}")
        if result.get("error"):
            log.error(f"run: error={result['error'][:200]}")
        kc.stop_channels()
        return result
    except Exception as e:
        log.exception(f"run: exception: {e}")
        return {"output": None, "error": str(e)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("code", nargs="?", default=None)
    p.add_argument("--cwd", default=None)
    p.add_argument("--stop", action="store_true", help="Stop the running kernel")
    args = p.parse_args()

    if args.stop:
        stop_kernel()
        return

    if not args.code:
        p.error("code is required unless --stop is used")

    result = run(args.code, args.cwd)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
