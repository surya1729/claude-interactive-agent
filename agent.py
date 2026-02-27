import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage


async def main():
    print("=" * 60)
    print("  Interactive Claude Agent - Conversation Mode")
    print("  Type 'exit', 'quit', or 'done' to end")
    print("=" * 60)

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a helpful backend engineering assistant. "
            "You help with Python, system design, APIs, and debugging. "
            "Be concise and practical."
        ),
        allowed_tools=["Read", "Edit", "Glob", "Grep", "Bash"],
        continue_conversation=True  # SDK owns the context, not us
    )

    while True:
        user_message = input("\n👤 You: ").strip()

        if user_message.lower() in ['exit', 'quit', 'done']:
            print("\n👋 Goodbye!")
            break

        if not user_message:
            print("⚠️  Please enter a message.")
            continue

        print("\n🤖 Claude:", flush=True)

        claude_response = []

        async for message in query(
            prompt=user_message,  # ← just the current message, no history stitching
            options=options,
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text"):
                        print(block.text, end="", flush=True)
                        claude_response.append(block.text)
                    elif hasattr(block, "name"):
                        print(f"\n  🔧 [{block.name}]", flush=True)

            elif isinstance(message, ResultMessage):
                if message.subtype == "error":
                    print(f"\n  ⚠️  Error: {message.subtype}")

        print()


asyncio.run(main())