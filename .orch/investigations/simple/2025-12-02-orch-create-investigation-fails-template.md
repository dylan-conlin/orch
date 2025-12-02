---
started: "2025-12-02"
status: "Resolved"
confidence: "High"
resolution-status: "Resolved"
---

# Investigation: orch create-investigation "Template not found" Error

## Question

Why does `orch create-investigation` fail with "Template not found: ~/.orch/templates/investigations/SIMPLE.md"?

## Hypothesis

The template file doesn't exist because `orch build global` hasn't been run to sync templates from the source location.

## Test performed

1. **Checked template destination directory:**
   ```bash
   ls -la ~/.orch/templates/investigations/
   ```
   Result: Only INDEX.md was present, SIMPLE.md was missing.

2. **Checked template source directory:**
   ```bash
   ls -la ~/orch-knowledge/templates-src/investigations/
   ```
   Result: SIMPLE.md exists in the source location.

3. **Traced code path:**
   - `investigations.py:114` uses `Path.home() / '.orch' / 'templates' / 'investigations' / template_name`
   - Template name comes from `TEMPLATE_MAP['simple']` = 'SIMPLE.md'
   - Code is correct - template file simply didn't exist at destination

4. **Verified fix:**
   ```bash
   orch build global
   # Synced templates from ~/orch-knowledge/templates-src/ to ~/.orch/templates/

   orch create-investigation test-template-fix
   # SUCCESS - investigation created
   ```

## Outcome

**Root Cause:** The `orch build global` command hadn't been run, so templates weren't synced from `~/orch-knowledge/templates-src/investigations/` to `~/.orch/templates/investigations/`.

**Fix:** Run `orch build global` to sync templates.

**Why the discrepancy between projects:** The original report said it "works from orch-cli but fails from orch-knowledge" - this was likely a testing artifact. The template location is global (`~/.orch/templates/`) so it should fail identically from both projects if templates aren't synced.

## Related

- Template sync command: `orch build global` in `src/orch/cli.py:1929`
- Template source: `~/orch-knowledge/templates-src/investigations/`
- Template destination: `~/.orch/templates/investigations/`
- Investigation types defined in: `src/orch/investigations.py:17` (TEMPLATE_MAP)

## Side Note: Secondary Bug Discovered

During testing, I noticed that `orch create-investigation` run from `~/orch-knowledge` created files in `~/Documents/personal/orch-cli/.orch/investigations/` instead of `~/orch-knowledge/.orch/investigations/`. This is a separate project detection bug worth investigating.
