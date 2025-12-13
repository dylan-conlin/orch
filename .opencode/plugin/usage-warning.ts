/**
 * Plugin: Inject Claude Max usage warning at session start.
 *
 * Equivalent to: ~/.claude/hooks/usage-warning.sh (SessionStart hook)
 * OpenCode event: session.created
 *
 * Plugin behavior:
 * 1. Run `orch usage --json` to get usage data
 * 2. Check if weekly utilization is >80%
 * 3. If so, inject warning context into session
 *
 * This warns agents when nearing Claude Max weekly limits.
 */

import type { Plugin } from "@opencode-ai/plugin"

interface UsageData {
  error?: string
  seven_day?: {
    utilization?: number
    remaining?: number
    time_until_reset?: string
  }
}

/**
 * Get usage warning message if utilization is high
 */
async function getUsageWarning($: any): Promise<string | null> {
  try {
    const result = await $`orch usage --json`.quiet()
    const output = result.stdout.toString().trim()

    if (!output) {
      return null
    }

    const data: UsageData = JSON.parse(output)

    // Check for error in response
    if (data.error) {
      return null
    }

    const utilization = data.seven_day?.utilization ?? 0
    const remaining = data.seven_day?.remaining ?? 100
    const resetTime = data.seven_day?.time_until_reset ?? "?"

    // Only warn if usage is above 80%
    if (utilization < 80) {
      return null
    }

    // Choose warning level
    let emoji: string
    let level: string
    if (utilization >= 95) {
      emoji = "🔴"
      level = "CRITICAL"
    } else if (utilization >= 90) {
      emoji = "🟠"
      level = "HIGH"
    } else {
      emoji = "🟡"
      level = "WARNING"
    }

    return `${emoji} **Claude Max Usage ${level}**: ${utilization}% of weekly limit used (${remaining}% remaining)
Resets in: ${resetTime}

Consider: shorter responses, fewer iterations, prioritize high-value work.`
  } catch {
    return null
  }
}

/**
 * Usage Warning Plugin
 *
 * Injects usage warnings into session when utilization is high.
 */
export const UsageWarningPlugin: Plugin = async ({
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

      // Get usage warning
      const warning = await getUsageWarning($)
      if (!warning) {
        return
      }

      // Inject warning into session
      try {
        await client.session.prompt({
          path: { id: sessionId },
          body: {
            noReply: true,
            parts: [
              {
                type: "text",
                text: `# Usage Warning\n\n${warning}`,
              },
            ],
          },
        })
        console.log("[usage-warning] Usage warning injected into session")
      } catch (err) {
        console.error("[usage-warning] Failed to inject warning:", err)
      }
    },
  }
}
