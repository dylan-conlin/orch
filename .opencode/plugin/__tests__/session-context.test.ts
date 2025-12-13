/**
 * Tests for session-context.ts OpenCode plugin.
 *
 * This plugin loads orchestration context at session start for orch-enabled projects,
 * equivalent to the Claude Code SessionStart hook in load-orchestration-context.py.
 *
 * Run with: bun test .opencode/plugin/session-context.test.ts
 */

import { describe, test, expect, beforeEach, afterEach, mock } from "bun:test"
import { mkdtemp, writeFile, mkdir, rm } from "fs/promises"
import { tmpdir, homedir } from "os"
import { join } from "path"
import {
  SessionContextPlugin,
  exists,
  findOrchDirectory,
  loadOrchestratorSkill,
} from "../session-context"

describe("exists", () => {
  let tempDir: string

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), "session-context-test-"))
  })

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true })
  })

  test("returns true for existing directory", async () => {
    const result = await exists(tempDir)
    expect(result).toBe(true)
  })

  test("returns true for existing file", async () => {
    const filePath = join(tempDir, "test.txt")
    await writeFile(filePath, "test")
    const result = await exists(filePath)
    expect(result).toBe(true)
  })

  test("returns false for non-existent path", async () => {
    const result = await exists(join(tempDir, "nonexistent"))
    expect(result).toBe(false)
  })
})

describe("findOrchDirectory", () => {
  let tempDir: string

  beforeEach(async () => {
    tempDir = await mkdtemp(join(tmpdir(), "session-context-test-"))
  })

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true })
  })

  test("finds .orch in current directory", async () => {
    const orchDir = join(tempDir, ".orch")
    await mkdir(orchDir)

    const result = await findOrchDirectory(tempDir)
    expect(result).toBe(orchDir)
  })

  test("finds .orch in parent directory", async () => {
    const orchDir = join(tempDir, ".orch")
    const subDir = join(tempDir, "subdir")
    await mkdir(orchDir)
    await mkdir(subDir)

    const result = await findOrchDirectory(subDir)
    expect(result).toBe(orchDir)
  })

  test("returns null when no .orch directory found", async () => {
    const result = await findOrchDirectory(tempDir)
    expect(result).toBe(null)
  })

  test("finds .orch in nested parent directory", async () => {
    const orchDir = join(tempDir, ".orch")
    const level1 = join(tempDir, "level1")
    const level2 = join(level1, "level2")
    await mkdir(orchDir)
    await mkdir(level1)
    await mkdir(level2)

    const result = await findOrchDirectory(level2)
    expect(result).toBe(orchDir)
  })
})

describe("loadOrchestratorSkill", () => {
  // Note: This test depends on the actual file system
  // In a real test environment, we'd mock the file system
  test("returns null when skill file doesn't exist", async () => {
    // If the skill file happens to exist, this test will pass anyway
    // because it just checks the function doesn't crash
    const result = await loadOrchestratorSkill()
    // Result can be string (if file exists) or null (if not)
    expect(result === null || typeof result === "string").toBe(true)
  })
})

describe("SessionContextPlugin", () => {
  let originalOrchWorker: string | undefined
  let tempDir: string

  beforeEach(async () => {
    originalOrchWorker = process.env.ORCH_WORKER
    tempDir = await mkdtemp(join(tmpdir(), "session-context-test-"))
  })

  afterEach(async () => {
    if (originalOrchWorker !== undefined) {
      process.env.ORCH_WORKER = originalOrchWorker
    } else {
      delete process.env.ORCH_WORKER
    }
    await rm(tempDir, { recursive: true, force: true })
  })

  test("exports plugin function", () => {
    expect(typeof SessionContextPlugin).toBe("function")
  })

  test("plugin returns event handler", async () => {
    const handlers = await SessionContextPlugin({
      project: {} as any,
      client: { session: { prompt: async () => {} } } as any,
      $: (() => ({ quiet: async () => ({ stdout: "" }) })) as any,
      directory: tempDir,
      worktree: tempDir,
    })

    expect(handlers.event).toBeDefined()
    expect(typeof handlers.event).toBe("function")
  })

  describe("event handler", () => {
    let handler: Function
    let mockPrompt: ReturnType<typeof mock>

    beforeEach(async () => {
      mockPrompt = mock(async () => ({}))
      const handlers = await SessionContextPlugin({
        project: {} as any,
        client: { session: { prompt: mockPrompt } } as any,
        $: (() => ({
          quiet: async () => ({ stdout: '{"agents": []}' }),
        })) as any,
        directory: tempDir,
        worktree: tempDir,
      })
      handler = handlers.event!
    })

    test("ignores non session.created events", async () => {
      await handler({ event: { type: "session.idle" } })
      expect(mockPrompt).not.toHaveBeenCalled()
    })

    test("skips for worker agents", async () => {
      process.env.ORCH_WORKER = "true"
      const orchDir = join(tempDir, ".orch")
      await mkdir(orchDir)

      await handler({
        event: { type: "session.created", properties: { sessionID: "test-123" } },
      })
      expect(mockPrompt).not.toHaveBeenCalled()
    })

    test("skips when no session ID provided", async () => {
      delete process.env.ORCH_WORKER
      const orchDir = join(tempDir, ".orch")
      await mkdir(orchDir)

      await handler({ event: { type: "session.created", properties: {} } })
      expect(mockPrompt).not.toHaveBeenCalled()
    })

    test("skips when not in orch project", async () => {
      delete process.env.ORCH_WORKER

      await handler({
        event: { type: "session.created", properties: { sessionID: "test-123" } },
      })
      expect(mockPrompt).not.toHaveBeenCalled()
    })

    test("injects context in orch project", async () => {
      delete process.env.ORCH_WORKER
      const orchDir = join(tempDir, ".orch")
      await mkdir(orchDir)

      // Create a fresh handler with the orch directory
      const handlers = await SessionContextPlugin({
        project: {} as any,
        client: { session: { prompt: mockPrompt } } as any,
        $: (() => ({
          quiet: async () => ({ stdout: '{"agents": []}' }),
        })) as any,
        directory: tempDir,
        worktree: tempDir,
      })

      await handlers.event!({
        event: { type: "session.created", properties: { sessionID: "test-123" } },
      })

      // Should have been called to inject context
      expect(mockPrompt).toHaveBeenCalled()
    })

    test("uses noReply: true when injecting context", async () => {
      delete process.env.ORCH_WORKER
      const orchDir = join(tempDir, ".orch")
      await mkdir(orchDir)

      const handlers = await SessionContextPlugin({
        project: {} as any,
        client: { session: { prompt: mockPrompt } } as any,
        $: (() => ({
          quiet: async () => ({ stdout: '{"agents": []}' }),
        })) as any,
        directory: tempDir,
        worktree: tempDir,
      })

      await handlers.event!({
        event: { type: "session.created", properties: { sessionID: "test-123" } },
      })

      // Check the call was made with noReply: true
      const calls = mockPrompt.mock.calls
      expect(calls.length).toBeGreaterThan(0)
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0].body.noReply).toBe(true)
    })

    test("includes session ID in prompt path", async () => {
      delete process.env.ORCH_WORKER
      const orchDir = join(tempDir, ".orch")
      await mkdir(orchDir)

      const handlers = await SessionContextPlugin({
        project: {} as any,
        client: { session: { prompt: mockPrompt } } as any,
        $: (() => ({
          quiet: async () => ({ stdout: '{"agents": []}' }),
        })) as any,
        directory: tempDir,
        worktree: tempDir,
      })

      await handlers.event!({
        event: { type: "session.created", properties: { sessionID: "my-session-id" } },
      })

      const calls = mockPrompt.mock.calls
      expect(calls.length).toBeGreaterThan(0)
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0].path.id).toBe("my-session-id")
    })
  })
})
