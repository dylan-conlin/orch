#!/usr/bin/env python3
"""Test: Agent SDK with native CLI auth (no API key override)"""

import asyncio
import os

# IMPORTANT: Don't set ANTHROPIC_API_KEY - let CLI use its own OAuth
if "ANTHROPIC_API_KEY" in os.environ:
    del os.environ["ANTHROPIC_API_KEY"]

from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    print("Testing Agent SDK with CLI's native OAuth auth...")
    print("=" * 50)

    count = 0
    try:
        async for message in query(
            prompt="Say exactly: 'Hello from SDK' - nothing else",
            options=ClaudeAgentOptions(
                model="claude-sonnet-4-20250514",
                max_turns=1,
            )
        ):
            count += 1
            msg_type = type(message).__name__

            # Get content
            if hasattr(message, 'content'):
                content = str(message.content)[:150]
            elif hasattr(message, 'message'):
                content = str(message.message)[:150]
            elif hasattr(message, 'data'):
                content = str(message.data)[:150]
            else:
                content = str(message)[:150]

            print(f"  [{count}] {msg_type}: {content}")

            if count > 10:
                print("  (stopping)")
                break

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        return False

    print(f"\nReceived {count} messages")
    return count > 0

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
