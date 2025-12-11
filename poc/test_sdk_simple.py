#!/usr/bin/env python3
"""Simple test: Does Agent SDK work with OAuth token?"""

import asyncio
import os
from pathlib import Path

# Read OAuth token
oauth_token = (Path.home() / ".claude" / ".oauth-token").read_text().strip()
print(f"OAuth token: {oauth_token[:20]}...{oauth_token[-10:]}")

# Set as ANTHROPIC_API_KEY (may or may not work - SDK might use CLI)
os.environ["ANTHROPIC_API_KEY"] = oauth_token

from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    print("\nTesting Agent SDK...")
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
            # Try to get useful content
            if hasattr(message, 'content'):
                content = str(message.content)[:100]
            elif hasattr(message, 'message'):
                content = str(message.message)[:100]
            else:
                content = str(message)[:100]
            print(f"  [{count}] {msg_type}: {content}")

            # Stop after getting some response
            if count > 5:
                print("  (stopping after 5 messages)")
                break

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        return False

    print(f"\nReceived {count} messages")
    return count > 0

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
