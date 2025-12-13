/**
 * Shared helpers for OpenCode plugins.
 *
 * These are exported separately from the plugins to avoid OpenCode
 * plugin loader trying to call them as plugin functions.
 */

import { access, readFile } from "fs/promises"
import { join, resolve } from "path"
import { homedir } from "os"

/**
 * Check if a file or directory exists
 */
export async function exists(path: string): Promise<boolean> {
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
export async function findOrchDirectory(startDir: string | unknown): Promise<string | null> {
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
 * Load orchestrator skill from ~/.claude/skills/policy/orchestrator/SKILL.md
 */
export async function loadOrchestratorSkill(): Promise<string | null> {
  const skillPath = join(homedir(), ".claude", "skills", "policy", "orchestrator", "SKILL.md")

  try {
    const content = await readFile(skillPath, "utf-8")
    return content
  } catch {
    return null
  }
}
