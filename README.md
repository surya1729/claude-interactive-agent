# Claude Interactive Agent

An interactive CLI agent built with the Claude Agent SDK that maintains conversation history and enables natural back-and-forth dialogue with Claude.

## Features

- 💬 **Interactive Conversation Loop** - Continuous chat with context retention
- 🧠 **Conversation History** - Remembers previous exchanges (last 10 messages)
- 🛠️ **File System Tools** - Built-in access to Read, Edit, Glob, and Grep tools
- 🔄 **Multi-Turn Conversations** - Natural back-and-forth dialogue
- ⚡ **Async Streaming** - Real-time response streaming
- 🎯 **Smart Tool Usage** - Claude automatically uses the right tools for the task

## Prerequisites

- Python 3.8+
- Claude Code CLI (authenticated)
- Claude Agent SDK

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/claude-interactive-agent.git
cd claude-interactive-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Ensure Claude Code CLI is installed and authenticated:
```bash
claude --version
```

## Usage

Run the interactive agent:
```bash
python agent.py
```

### Example Conversation

```
============================================================
Interactive Claude Agent - Conversation Mode
Type 'exit', 'quit', or 'done' to end the conversation
============================================================

👤 You: Review utils.py for bugs

🤖 Claude: I found 3 bugs in utils.py...
1. ZeroDivisionError in calculate_average()
2. Missing input validation
3. KeyError in get_user_name()

What would you like to do?

------------------------------------------------------------

👤 You: Fix all bugs

🤖 Claude: I'll fix all the bugs now...
[Using tool: Edit]
Done! All bugs have been fixed.

------------------------------------------------------------

👤 You: exit
👋 Ending conversation. Goodbye!
```

## Configuration

### Allowed Tools

You can customize which tools Claude can use by modifying the `allowed_tools` list in `agent.py`:

```python
options=ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Glob", "Grep", "WebFetch"],
)
```

Available tools:
- `Read` - Read files
- `Edit` - Edit files
- `Write` - Create new files
- `Glob` - Search for files by pattern
- `Grep` - Search file contents
- `WebFetch` - Fetch web content
- `Bash` - Execute shell commands

### Permission Modes

Set permission mode for automatic approval:

```python
options=ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Glob"],
    permission_mode="acceptEdits"  # Auto-approve edits
)
```

Options:
- `None` (default) - Ask for permission
- `"acceptEdits"` - Auto-approve Read/Edit/Write
- `"ask"` - Prompt for all tools
- `"auto"` - Auto-approve all (use with caution!)

### Conversation History Limit

Adjust how many messages to keep in context (default: 10):

```python
context = "\n".join(conversation_history[-10:])  # Change 10 to desired number
```

## How It Works

1. **Conversation History** - Stores all user and Claude messages
2. **Context Building** - Passes recent conversation to each query
3. **Tool Execution** - Claude automatically uses tools based on the task
4. **Streaming Responses** - Displays Claude's thinking in real-time
5. **Interactive Loop** - Continues until you type 'exit'

## Production Usage

For production environments, you'll need to provide an API key explicitly:

```python
options=ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Glob"],
    api_key=os.getenv("ANTHROPIC_API_KEY")  # Set via environment variable
)
```

Get your API key from [Anthropic Console](https://console.anthropic.com/).

## Troubleshooting

### "Permission denied" errors
- Make sure tools are included in `allowed_tools`
- Check `permission_mode` setting

### "API key not found"
- Ensure Claude Code CLI is authenticated: `claude doctor`
- For production, set `ANTHROPIC_API_KEY` environment variable

### Conversation ends unexpectedly
- Don't press Enter without typing (will prompt to try again)
- Use explicit 'exit', 'quit', or 'done' to end

## Acknowledgments

Built with [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) by Anthropic.
