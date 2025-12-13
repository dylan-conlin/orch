/**
 * Plugin: Inject agentlog context into session start.
 *
 * Equivalent to: ~/.claude/hooks/agentlog-inject.sh (SessionStart hook)
 * OpenCode event: session.created
 *
 * Plugin behavior:
 * 1. Check if agentlog command is available
 * 2. Check if .agentlog directory exists in current project
 * 3. Run `agentlog prime` to get recent errors summary
 * 4. If errors exist, inject context into session
 *
 * This gives agents awareness of recent runtime errors in the codebase.
 */

import type { Plugin } from "@opencode-ai/plugin"
import { access } from "fs/promises"
import { join } from "path"

/**
 * Check if a path exists
 */
async function exists(path: string): Promise<boolean> {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

/**
 * Check if agentlog command is available
 */
async function hasAgentlog($: any): Promise<boolean> {
  try {
    await $`which agentlog`.quiet()
    return true
  } catch {
    return false
  }
}

/**
 * Get agentlog prime output if errors exist
 */
async function getAgentlogContext($: any, directory: string): Promise<string | null> {
  // Check for .agentlog directory in project
  const agentlogDir = join(directory, ".agentlog")
  if (!(await exists(agentlogDir))) {
    return null
  }

  try {
    const result = await $`agentlog prime`.quiet()
    const output = result.stdout.toString().trim()

    // Skip if no errors or not initialized
    if (
      !output ||
      output.includes("No errors logged") ||
      output.includes("No error log found")
    ) {
      return null
    }

    return `# Recent Errors (from agentlog)

${output}

---
*Run \`agentlog errors\` for details or \`agentlog tail\` to watch in real-time.*`
  } catch {
    return null
  }
}

/**
 * Agentlog Inject Plugin
 *
 * Injects recent error context into session when errors exist.
 */
export const AgentlogInjectPlugin: Plugin = async ({
  project,
  client,
  $,
  directory,
  worktree,
}) => {
  return {
    event: async ({ event }: { event: { type: string; properties?: { sessionID?: string } } }) => {
      // Only trigger on session creation
      if (event.type !== "session.created") {
        return
      }

      // Get session ID from event
      const sessionId = event.properties?.sessionID
      if (!sessionId) {
        return
      }

      // Check if agentlog is available
      if (!(await hasAgentlog($))) {
        return
      }

      // Get working directory - handle both string and object types
      const workingDir = typeof directory === "string" ? directory : process.cwd()

      // Get agentlog context
      const context = await getAgentlogContext($, workingDir)
      if (!context) {
        return
      }

      // Inject context into session
      try {
        await client.session.prompt({
          path: { id: sessionId },
          body: {
            noReply: true,
            parts: [
              {
                type: "text",
                text: context,
              },
            ],
          },
        })
        console.log("[agentlog-inject] Error context injected into session")
      } catch (err) {
        console.error("[agentlog-inject] Failed to inject context:", err)
      }
    },
  }
}
