/**
 * OpenCode Plugin: Auto-load orchestration context at session start.
 *
 * Equivalent to: hooks/load-orchestration-context.py (SessionStart hook)
 * OpenCode event: session.created
 *
 * Plugin behavior:
 * 1. Detect if in orch project (.orch/ directory exists)
 * 2. Load orchestrator skill from ~/.claude/skills/orchestrator/SKILL.md
 * 3. Load active agents via orch status --format json
 * 4. Load recent kn entries
 * 5. Inject as system context via client.session.prompt with noReply: true
 *
 * Installation:
 *   Place in .opencode/plugin/ directory (project) or ~/.config/opencode/plugin/ (global)
 *
 * Run tests with: bun test .opencode/plugin/__tests__/session-context.test.ts
 */

import type { Plugin } from "@opencode-ai/plugin"
import { readFile, access } from "fs/promises"
import { join, resolve } from "path"
import { homedir } from "os"

interface AgentInfo {
  agent_id: string
  phase: string
  window: string
  alerts?: { type: string }[]
}

interface OrchStatusOutput {
  agents: AgentInfo[]
}

/**
 * Check if a file or directory exists
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
 * Find .orch directory in current directory or parents
 */
async function findOrchDirectory(startDir: string | unknown): Promise<string | null> {
  // Defensive: ensure startDir is a string
  if (typeof startDir !== "string") {
    console.log("[session-context] findOrchDirectory called with non-string:", typeof startDir)
    return null
  }

  let currentDir = resolve(startDir)

  // Check current directory
  const orchPath = join(currentDir, ".orch")
  if (await exists(orchPath)) {
    return orchPath
  }

  // Check parent directories (up to 10 levels)
  for (let i = 0; i < 10; i++) {
    const parentDir = resolve(currentDir, "..")
    if (parentDir === currentDir) break // Reached root

    const parentOrchPath = join(parentDir, ".orch")
    if (await exists(parentOrchPath)) {
      return parentOrchPath
    }
    currentDir = parentDir
  }

  return null
}

/**
 * Load orchestrator skill from ~/.claude/skills/orchestrator/SKILL.md
 */
async function loadOrchestratorSkill(): Promise<string | null> {
  const skillPath = join(homedir(), ".claude", "skills", "orchestrator", "SKILL.md")

  try {
    const content = await readFile(skillPath, "utf-8")
    return content
  } catch {
    return null
  }
}

/**
 * Load active agents via orch status --format json
 */
async function loadActiveAgents($: any): Promise<string | null> {
  try {
    const result = await $`orch status --format json`.quiet()
    const output = result.stdout.toString().trim()

    if (!output) {
      return "**Active Agents:** None\n"
    }

    const data: OrchStatusOutput = JSON.parse(output)
    const agents = data.agents || []

    if (agents.length === 0) {
      return "**Active Agents:** None\n"
    }

    const lines = ["**Active Agents:**\n"]
    for (const agent of agents.slice(0, 5)) {
      const agentId = agent.agent_id || "Unknown"
      const phase = agent.phase || "Unknown"
      const window = agent.window || "N/A"

      let alertStr = ""
      if (agent.alerts && agent.alerts.length > 0) {
        const alertTypes = agent.alerts.map((a) => a.type || "").filter(Boolean)
        if (alertTypes.length > 0) {
          alertStr = ` [${alertTypes.join(", ")}]`
        }
      }

      lines.push(`- \`${agentId}\` - Phase: ${phase} | Window: ${window}${alertStr}`)
    }

    if (agents.length > 5) {
      lines.push(`\n*...and ${agents.length - 5} more agents*`)
    }

    return lines.join("\n") + "\n"
  } catch {
    return null
  }
}

/**
 * Load recent kn entries if .kn exists
 */
async function loadKnRecent($: any, directory: string): Promise<string | null> {
  if (typeof directory !== "string") return null
  
  const knDir = join(directory, ".kn")
  if (!(await exists(knDir))) {
    return null
  }

  try {
    const result = await $`kn recent --limit 10`.quiet()
    const output = result.stdout.toString().trim()

    if (!output) {
      return null
    }

    return output
  } catch {
    return null
  }
}

/**
 * Session Context Plugin
 *
 * Loads orchestration context at session start for orch-enabled projects.
 */
export const SessionContextPlugin: Plugin = async ({
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

      // Skip for worker agents (they have skill embedded in SPAWN_CONTEXT.md)
      if (process.env.ORCH_WORKER) {
        return
      }

      // Get session ID from event
      const sessionId = event.properties?.sessionID
      if (!sessionId) {
        console.log("[session-context] No session ID in event, skipping context injection")
        return
      }

      // Must be in an orch project - use process.cwd() as directory may be object
      const workingDir = typeof directory === "string" ? directory : process.cwd()
      const orchDir = await findOrchDirectory(workingDir)
      if (!orchDir) {
        return
      }

      // Build context
      const contextParts: string[] = []
      contextParts.push("# Orchestration Context\n")
      contextParts.push("*Auto-loaded via OpenCode session plugin*\n\n")

      // Load orchestrator skill
      const skillContent = await loadOrchestratorSkill()
      if (skillContent) {
        contextParts.push("---\n\n")
        contextParts.push(skillContent)
        contextParts.push("\n\n---\n\n")
      }

      // Load active agents
      const agents = await loadActiveAgents($)
      if (agents) {
        contextParts.push("## Active Agents\n\n")
        contextParts.push(agents)
      }

      // Load recent kn entries
      const knRecent = await loadKnRecent($, workingDir)
      if (knRecent) {
        contextParts.push("\n## Recent Knowledge (kn)\n\n")
        contextParts.push("*Quick decisions, constraints, failed attempts, questions*\n\n")
        contextParts.push("```\n")
        contextParts.push(knRecent)
        contextParts.push("\n```\n\n")
        contextParts.push("*Run `kn context \"<topic>\"` to get knowledge about a specific area*\n")
      }

      // Output context if we have meaningful content
      if (contextParts.length > 2) {
        const fullContext = contextParts.join("")

        // Log that context was loaded (visible in OpenCode logs)
        console.log("[session-context] Orchestration context loaded for orch project")

        // Inject context using session.prompt with noReply: true
        // This adds the context as a user message without triggering an AI response
        try {
          await client.session.prompt({
            path: { id: sessionId },
            body: {
              noReply: true,
              parts: [
                {
                  type: "text",
                  text: fullContext,
                },
              ],
            },
          })
          console.log("[session-context] Context injected into session")
        } catch (err) {
          // If injection fails, log the error and context summary
          console.error("[session-context] Failed to inject context:", err)
          console.log("[session-context] Context would have been:")
          console.log(fullContext.substring(0, 500) + "...")
        }
      }
    },
  }
}
