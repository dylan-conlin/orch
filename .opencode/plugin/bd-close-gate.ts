/**
 * Plugin: Block 'bd close' commands in worker context.
 *
 * Triggered by: tool.execute.before (Bash)
 * When: Worker agent attempts to run 'bd close' command
 * Action: Throw error with guidance to use 'bd comment' instead
 *
 * This prevents workers from closing beads issues directly, which would bypass
 * the 'orch complete' verification process. Only orchestrators should close
 * issues after verifying agent work is complete.
 *
 * Equivalent to: hooks/block-bd-close.py (Claude Code PreToolUse hook)
 */

import type { Plugin } from "@opencode-ai/plugin";

/**
 * Check if a command should be blocked.
 *
 * @param command - The bash command being executed
 * @returns true if the command should be blocked, false otherwise
 */
export function shouldBlockCommand(command: string): boolean {
  // Only block in worker context
  const context = process.env.CLAUDE_CONTEXT ?? "";
  if (context !== "worker") {
    return false;
  }

  // Check for 'bd close' pattern
  // Match: bd close, bd  close (multiple spaces), but not 'echo "bd close"' etc.
  // Use word boundary to avoid matching 'abcd close' or 'bd closed'
  const bdClosePattern = /^\s*bd\s+close\b/;
  return bdClosePattern.test(command);
}

/**
 * Get the error message for blocked commands.
 */
export function getBlockedMessage(): string {
  return `Workers cannot run 'bd close' directly. This bypasses verification and breaks tracking.

Instead:
1. Report completion via: bd comment <beads-id> "Phase: Complete - [summary]"
2. Run /exit to close the agent session
3. The orchestrator will verify and close the issue via 'orch complete'`;
}

/**
 * OpenCode plugin that blocks 'bd close' commands for worker agents.
 */
export const BdCloseGate: Plugin = async ({
  project,
  client,
  $,
  directory,
  worktree,
}) => {
  return {
    "tool.execute.before": async (input, output) => {
      // Only check Bash tool calls
      if (input.tool !== "bash") {
        return;
      }

      // Get the command being executed
      const command = output.args?.command as string | undefined;
      if (!command) {
        return;
      }

      // Check if this command should be blocked
      if (shouldBlockCommand(command)) {
        throw new Error(getBlockedMessage());
      }
    },
  };
};
