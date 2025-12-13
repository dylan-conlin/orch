**TLDR:** Question: Is the OpenCode backend correctly NOT the default in orch-cli? Answer: Yes - code default is 'claude' (verified via tests and code inspection). User config `~/.orch/config.yaml` can override this to 'opencode'. Very High confidence (98%) - 5 backend tests pass, code explicitly sets 'claude' as default.

---

# Investigation: Verify OpenCode Default Test

**Question:** Is the OpenCode backend correctly NOT set as the default backend in orch-cli (i.e., 'claude' is the default)?

**Started:** 2025-12-12
**Updated:** 2025-12-12
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (98%)

---

## Findings

### Finding 1: Code explicitly defaults to 'claude' backend

**Evidence:** 
```python
# src/orch/config.py:31
def _defaults() -> Dict[str, Any]:
    ...
    'backend': 'claude',
```

The `_defaults()` function in config.py explicitly sets `'backend': 'claude'` as the default value.

**Source:** `src/orch/config.py:31`

**Significance:** This confirms the code-level default is 'claude', not 'opencode'. The default is baked into the codebase.

---

### Finding 2: All 5 backend tests pass

**Evidence:**
```
tests/test_config.py::test_get_backend_default PASSED
tests/test_config.py::test_get_backend_from_config_file PASSED
tests/test_config.py::test_get_backend_with_cli_override PASSED
tests/test_config.py::test_get_backend_cli_only PASSED
tests/test_config.py::test_get_backend_priority_cli_over_config PASSED
```

Command: `uv run pytest tests/test_config.py -k "backend" -v`

**Source:** `tests/test_config.py:240-295`

**Significance:** Tests verify:
1. Default is 'claude' when no config exists
2. Config file can override default
3. CLI flag overrides config file
4. Priority chain works: CLI > config > default

---

### Finding 3: User config can override to 'opencode' (working as designed)

**Evidence:**
```bash
$ cat ~/.orch/config.yaml
backend: opencode

$ uv run python3 -c "from orch.config import _defaults, get_backend; print('_defaults():', _defaults()['backend']); print('get_backend():', get_backend())"
_defaults(): claude
get_backend(): opencode
```

**Source:** `~/.orch/config.yaml`, manual Python execution

**Significance:** This is correct behavior - the user's config file properly overrides the code default. This is the intended design (CLI > config > default priority).

---

### Finding 4: CLI help correctly states default is 'claude'

**Evidence:**
```
$ uv run orch spawn --help | grep -A1 backend
  --backend [claude|codex|opencode]
                                  AI backend to use (default: claude)
```

**Source:** `orch spawn --help` output

**Significance:** Documentation matches implementation.

---

## Synthesis

**Key Insights:**

1. **Code default is correct** - The `_defaults()` function explicitly returns `'claude'` as the backend default.

2. **Tests validate the behavior** - 5 tests specifically cover backend selection logic, all passing.

3. **User override works correctly** - The current environment has `~/.orch/config.yaml` with `backend: opencode`, which correctly overrides the default. This is working as designed.

**Answer to Investigation Question:**

Yes, the OpenCode backend is correctly NOT the default. The code default is 'claude'. The user's config file (`~/.orch/config.yaml`) has overridden this to 'opencode', which is the expected and correct behavior of the configuration priority system (CLI > config file > code default).

---

## Confidence Assessment

**Current Confidence:** Very High (98%)

**Why this level?**

Multiple independent verification methods all confirm the same answer:
- Source code inspection
- Test suite execution
- Manual Python execution
- CLI help output

**What's certain:**

- `_defaults()['backend']` returns `'claude'` (source code)
- All 5 backend tests pass (test execution)
- `get_backend()` with no config file returns `'claude'` (test coverage)
- `~/.orch/config.yaml` override to `'opencode'` works correctly (manual test)

**What's uncertain:**

- None for this investigation scope

**What would increase confidence to 100%:**

- Would need to verify every code path that uses backend selection, but this is overkill for the question at hand

---

## Implementation Recommendations

N/A - This was a verification investigation. No changes needed.

The system is working correctly:
- Default backend: `claude`
- User can override via `~/.orch/config.yaml`
- CLI flag `--backend` has highest priority

---

## References

**Files Examined:**
- `src/orch/config.py:23-111` - Default definitions and get_backend() function
- `tests/test_config.py:240-295` - Backend test suite
- `src/orch/spawn_commands.py:134` - CLI option definition
- `~/.orch/config.yaml` - User config file

**Commands Run:**
```bash
# Run backend tests
uv run pytest tests/test_config.py -k "backend" -v

# Verify code default vs runtime default
uv run python3 -c "from orch.config import get_backend, _defaults; print('_defaults()[\"backend\"]:', _defaults()['backend']); print('get_backend():', get_backend())"

# Check user config
cat ~/.orch/config.yaml

# Verify CLI help
uv run orch spawn --help | grep -A2 "backend"
```

---

## Self-Review

- [x] Real test performed (not code review)
- [x] Conclusion from evidence (not speculation)
- [x] Question answered
- [x] File complete

**Self-Review Status:** PASSED

---

## Investigation History

**2025-12-12:** Investigation started
- Initial question: Verify opencode is not the default backend
- Context: Spawn task from orchestrator

**2025-12-12:** Investigation completed
- Final confidence: Very High (98%)
- Status: Complete
- Key outcome: Code default is 'claude', user config override to 'opencode' is working correctly
