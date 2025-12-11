#!/usr/bin/env python3
"""Test: Can Claude Agent SDK use OAuth tokens with magic system prompt?"""

import asyncio
import os
from pathlib import Path

# Read OAuth token
oauth_token_path = Path.home() / ".claude" / ".oauth-token"
if not oauth_token_path.exists():
    print("ERROR: No OAuth token found at ~/.claude/.oauth-token")
    exit(1)

oauth_token = oauth_token_path.read_text().strip()
print(f"OAuth token: {oauth_token[:20]}...{oauth_token[-10:]}")

# Set as ANTHROPIC_API_KEY
os.environ["ANTHROPIC_API_KEY"] = oauth_token

# Magic string from investigation
MAGIC_STRING = "You are Claude Code, Anthropic's official CLI for Claude."

from claude_agent_sdk import query, ClaudeAgentOptions

async def test_with_magic_string():
    """Test with the magic system prompt string."""
    print("\n=== Test 1: With magic string ===")
    try:
        async for message in query(
            prompt="Say 'OAuth works!' and nothing else",
            options=ClaudeAgentOptions(
                system_prompt=MAGIC_STRING,
                model="claude-sonnet-4-20250514",
                max_turns=1,
            )
        ):
            # Print message info
            msg_type = getattr(message, 'type', type(message).__name__)
            msg_content = str(message)[:200]
            print(f"  [{msg_type}] {msg_content}")
        print("  RESULT: SUCCESS")
        return True
    except Exception as e:
        print(f"  RESULT: FAILED - {type(e).__name__}: {e}")
        return False

async def test_without_magic_string():
    """Test without the magic string (should fail)."""
    print("\n=== Test 2: Without magic string ===")
    try:
        async for message in query(
            prompt="Say 'OAuth works!' and nothing else",
            options=ClaudeAgentOptions(
                system_prompt="You are a helpful assistant.",
                model="claude-sonnet-4-20250514",
                max_turns=1,
            )
        ):
            print(f"  {message.type}: {getattr(message, 'message', str(message)[:100])}")
        print("  RESULT: SUCCESS (unexpected!)")
        return True
    except Exception as e:
        print(f"  RESULT: FAILED (expected) - {e}")
        return False

async def test_with_preset():
    """Test with claude_code preset (should include magic string)."""
    print("\n=== Test 3: With claude_code preset ===")
    try:
        async for message in query(
            prompt="Say 'OAuth works!' and nothing else",
            options=ClaudeAgentOptions(
                system_prompt="claude_code",  # Preset that includes the magic string
                model="claude-sonnet-4-20250514",
                max_turns=1,
            )
        ):
            print(f"  {message.type}: {getattr(message, 'message', str(message)[:100])}")
        print("  RESULT: SUCCESS")
        return True
    except Exception as e:
        print(f"  RESULT: FAILED - {e}")
        return False

async def main():
    print("Testing Claude Agent SDK with OAuth token")
    print("=" * 50)

    results = {
        "with_magic": await test_with_magic_string(),
        "without_magic": await test_without_magic_string(),
        "with_preset": await test_with_preset(),
    }

    print("\n" + "=" * 50)
    print("SUMMARY:")
    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test}: {status}")

if __name__ == "__main__":
    asyncio.run(main())
