/**
 * Tests for bd-close-gate.ts OpenCode plugin.
 *
 * This plugin prevents workers from running 'bd close' commands directly,
 * which would bypass the 'orch complete' verification process.
 *
 * Run with: bun test .opencode/plugin/bd-close-gate.test.ts
 */

import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import { shouldBlockCommand, getBlockedMessage, BdCloseGate } from "./bd-close-gate";

describe("shouldBlockCommand", () => {
  let originalContext: string | undefined;

  beforeEach(() => {
    originalContext = process.env.CLAUDE_CONTEXT;
  });

  afterEach(() => {
    if (originalContext !== undefined) {
      process.env.CLAUDE_CONTEXT = originalContext;
    } else {
      delete process.env.CLAUDE_CONTEXT;
    }
  });

  describe("in worker context", () => {
    beforeEach(() => {
      process.env.CLAUDE_CONTEXT = "worker";
    });

    test("blocks 'bd close' command", () => {
      expect(shouldBlockCommand("bd close orch-cli-abc123")).toBe(true);
    });

    test("blocks 'bd close' with --reason flag", () => {
      expect(shouldBlockCommand('bd close issue-123 --reason "done"')).toBe(true);
    });

    test("blocks 'bd close' with leading whitespace", () => {
      expect(shouldBlockCommand("  bd close issue-123")).toBe(true);
    });

    test("blocks 'bd  close' with multiple spaces", () => {
      expect(shouldBlockCommand("bd  close issue-123")).toBe(true);
    });

    test("allows 'bd comment' command", () => {
      expect(shouldBlockCommand("bd comment issue-123 'Phase: Complete'")).toBe(false);
    });

    test("allows 'bd show' command", () => {
      expect(shouldBlockCommand("bd show issue-123")).toBe(false);
    });

    test("allows 'bd list' command", () => {
      expect(shouldBlockCommand("bd list")).toBe(false);
    });

    test("allows 'bd ready' command", () => {
      expect(shouldBlockCommand("bd ready")).toBe(false);
    });

    test("allows 'bd stats' command", () => {
      expect(shouldBlockCommand("bd stats")).toBe(false);
    });

    test("allows commands containing 'close' but not 'bd close'", () => {
      expect(shouldBlockCommand("git close-stale-issues")).toBe(false);
      expect(shouldBlockCommand("close_connection.py")).toBe(false);
    });

    test("allows quoted 'bd close' in echo command", () => {
      // This is a string being echoed, not an actual bd close command
      expect(shouldBlockCommand("echo 'bd close is blocked'")).toBe(false);
    });
  });

  describe("in orchestrator context", () => {
    beforeEach(() => {
      process.env.CLAUDE_CONTEXT = "orchestrator";
    });

    test("allows 'bd close' command", () => {
      expect(shouldBlockCommand("bd close orch-cli-abc123")).toBe(false);
    });
  });

  describe("without context", () => {
    beforeEach(() => {
      delete process.env.CLAUDE_CONTEXT;
    });

    test("allows 'bd close' command when CLAUDE_CONTEXT not set", () => {
      expect(shouldBlockCommand("bd close orch-cli-abc123")).toBe(false);
    });
  });

  describe("with empty context", () => {
    beforeEach(() => {
      process.env.CLAUDE_CONTEXT = "";
    });

    test("allows 'bd close' command when CLAUDE_CONTEXT is empty", () => {
      expect(shouldBlockCommand("bd close orch-cli-abc123")).toBe(false);
    });
  });
});

describe("getBlockedMessage", () => {
  test("includes guidance about bd comment", () => {
    const message = getBlockedMessage();
    expect(message).toContain("bd comment");
  });

  test("includes guidance about /exit", () => {
    const message = getBlockedMessage();
    expect(message).toContain("/exit");
  });

  test("includes guidance about orch complete", () => {
    const message = getBlockedMessage();
    expect(message).toContain("orch complete");
  });

  test("explains why bd close is blocked", () => {
    const message = getBlockedMessage();
    expect(message).toContain("bypasses verification");
  });
});

describe("BdCloseGate plugin", () => {
  let originalContext: string | undefined;

  beforeEach(() => {
    originalContext = process.env.CLAUDE_CONTEXT;
  });

  afterEach(() => {
    if (originalContext !== undefined) {
      process.env.CLAUDE_CONTEXT = originalContext;
    } else {
      delete process.env.CLAUDE_CONTEXT;
    }
  });

  test("exports plugin function", () => {
    expect(typeof BdCloseGate).toBe("function");
  });

  test("plugin returns tool.execute.before handler", async () => {
    const handlers = await BdCloseGate({
      project: {} as any,
      client: {} as any,
      $: {} as any,
      directory: "/test",
      worktree: "/test",
    });

    expect(handlers["tool.execute.before"]).toBeDefined();
    expect(typeof handlers["tool.execute.before"]).toBe("function");
  });

  describe("tool.execute.before handler", () => {
    let handler: Function;

    beforeEach(async () => {
      const handlers = await BdCloseGate({
        project: {} as any,
        client: {} as any,
        $: {} as any,
        directory: "/test",
        worktree: "/test",
      });
      handler = handlers["tool.execute.before"]!;
    });

    test("ignores non-bash tools", async () => {
      process.env.CLAUDE_CONTEXT = "worker";
      // Should not throw for non-bash tools
      await handler(
        { tool: "read" },
        { args: { filePath: "/test/file" } }
      );
    });

    test("ignores bash tool without command", async () => {
      process.env.CLAUDE_CONTEXT = "worker";
      // Should not throw when no command
      await handler(
        { tool: "bash" },
        { args: {} }
      );
    });

    test("allows bd comment in worker context", async () => {
      process.env.CLAUDE_CONTEXT = "worker";
      // Should not throw
      await handler(
        { tool: "bash" },
        { args: { command: "bd comment issue-123 'done'" } }
      );
    });

    test("throws for bd close in worker context", async () => {
      process.env.CLAUDE_CONTEXT = "worker";
      await expect(
        handler(
          { tool: "bash" },
          { args: { command: "bd close issue-123" } }
        )
      ).rejects.toThrow();
    });

    test("error message includes guidance", async () => {
      process.env.CLAUDE_CONTEXT = "worker";
      try {
        await handler(
          { tool: "bash" },
          { args: { command: "bd close issue-123" } }
        );
        expect.fail("Should have thrown");
      } catch (error) {
        expect((error as Error).message).toContain("bd comment");
        expect((error as Error).message).toContain("orch complete");
      }
    });

    test("allows bd close in orchestrator context", async () => {
      process.env.CLAUDE_CONTEXT = "orchestrator";
      // Should not throw
      await handler(
        { tool: "bash" },
        { args: { command: "bd close issue-123" } }
      );
    });
  });
});
