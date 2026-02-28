# Interactive Agent using Pi

An interactive CLI agent powered by [pi](https://github.com/badlogic/pi-mono) that gives an LLM a persistent Python execution environment via a Jupyter kernel.

## Project Structure

```
interactive-agent-using-pi/
├── worker/
│   ├── demo.py                  # Entry point — launches the pi TUI
│   ├── extensions/
│   │   └── python.ts            # Pi extension: registers the `python` tool
│   └── core/
│       ├── kernel_exec.py       # Manages a persistent Jupyter kernel
│       └── pi_rpc.py            # Python client for pi (interactive + RPC modes)
├── requirements.txt             # Python dependencies
├── package.json                 # Node dependencies (pi, typebox)
└── venv/                        # Python virtual environment (gitignored)
```

## How It Works

```
demo.py  →  pi (TUI)  →  python.ts extension  →  kernel_exec.py  →  Jupyter kernel
```

- **`demo.py`** launches pi with the `python.ts` extension loaded
- **`python.ts`** registers a `python` tool the LLM can call
- **`kernel_exec.py`** manages a persistent Jupyter kernel — first call starts it (~3s), subsequent calls reuse it (~50ms)
- Variables, imports, and state persist across tool calls within a session

## Features Available in the Tool

### Built-in Pi Tools
These are always available regardless of extensions:

| Tool    | What it does                        |
|---------|-------------------------------------|
| `bash`  | Run shell commands                  |
| `read`  | Read files                          |
| `write` | Create files                        |
| `edit`  | Edit files                          |
| `grep`  | Search file contents                |
| `find`  | Find files by pattern               |

### Python Tool (via `python.ts` extension)
Executes Python code in a **persistent Jupyter kernel** — state, variables, and imports survive across calls.

#### How the LLM uses it

At startup, pi registers the `python` tool and its description with the LLM. When you type a prompt:

```
startup:
  pi registers python tool → LLM sees tool description

on prompt "list all my github repos":
  LLM calls python tool
    → runs: from libs import sdk; sdk.list()     # discover available libs
    → runs: sdk.help("github")                   # see github API
    → runs: from libs import github
            github.list_repos()                  # fetch repos
    → returns results to user
```

#### libs/ — available Python libraries

| Library    | What it does                                      |
|------------|---------------------------------------------------|
| `github`   | Wrapper over `gh` CLI — repos, issues, PRs, CI   |

> To add a new library (e.g. Gmail), just drop `gmail.py` into `worker/libs/`.
> The LLM discovers it automatically via `sdk.list()` — no changes to `python.ts` needed.

## Prerequisites

- **Node.js** (v18+)
- **Python 3.10+**
- **pi** installed globally:
  ```bash
  npm install -g @mariozechner/pi-coding-agent
  ```
- An API key from a supported provider (OpenRouter, Anthropic, OpenAI, etc.)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/surya1729/claude-interactive-agent.git
cd interactive-agent-using-pi
```

### 2. Create and activate the Python venv

```bash
python -m venv venv
source venv/Scripts/activate   # Windows (Git Bash)
# or
source venv/bin/activate        # macOS/Linux
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Node dependencies

```bash
npm install
```

### 5. Set your API key

Set the environment variable for your provider (example: OpenRouter):

```bash
export OPENROUTER_API_KEY=your-key-here
```

Or store it permanently in `~/.pi/agent/auth.json`:

```json
{
  "openrouter": { "type": "api_key", "key": "your-key-here" }
}
```

| Provider   | Environment Variable   |
|------------|------------------------|
| OpenRouter | `OPENROUTER_API_KEY`   |
| Anthropic  | `ANTHROPIC_API_KEY`    |
| OpenAI     | `OPENAI_API_KEY`       |
| Gemini     | `GEMINI_API_KEY`       |
| Groq       | `GROQ_API_KEY`         |

## Running

```bash
cd worker
python demo.py --model openrouter/anthropic/claude-haiku-4-5
```

This opens the pi TUI. Type any prompt — the LLM will use the `python` tool to execute code in the persistent kernel.

### Options

```
python demo.py [--model MODEL] [--cwd DIR]

--model   Model ID to use (default: anthropic/claude-haiku-4.5)
--cwd     Working directory for the agent (default: current dir)
```

### Example models

```bash
# OpenRouter
python demo.py --model openrouter/anthropic/claude-haiku-4-5
python demo.py --model openrouter/openai/gpt-4o-mini

# Anthropic direct
python demo.py --model anthropic/claude-haiku-4-5

# Groq
python demo.py --model groq/llama-3.3-70b-versatile
```

## Troubleshooting

### `No module named 'jupyter_client'`
The venv is missing Python dependencies. Run:
```bash
source venv/Scripts/activate
pip install -r requirements.txt
```

### `No API key found for <provider>`
Set the environment variable for your provider — see the table above.

### `No module named 'jupyter_client'` in kernel but venv is active
`kernel_exec.py` uses the venv's Python directly via the path in `python.ts`. Make sure the venv exists at `venv/` in the project root.

### Pi opens but python tool always fails
Check that `venv/Scripts/python.exe` (Windows) or `venv/bin/python` (macOS/Linux) exists. The path in `worker/extensions/python.ts` (line 8) must match your OS.
