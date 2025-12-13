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

import type { Plugin } from "@opencode-ai/plugin"
import { shouldBlockCommand, getBlockedMessage } from "../lib/bd-close-helpers"

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
    "tool.execute.before": async (input: any, output: any) => {
      // Only check Bash tool calls
      if (input.tool !== "bash") {
        return
      }

      // Get the command being executed
      const command = output.args?.command as string | undefined
      if (!command) {
        return
      }

      // Check if this command should be blocked
      if (shouldBlockCommand(command)) {
        throw new Error(getBlockedMessage())
      }
    },
  }
}
