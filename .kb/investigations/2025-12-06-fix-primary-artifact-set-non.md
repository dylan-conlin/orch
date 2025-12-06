**TLDR:** `determine_primary_artifact()` at spawn.py:465 sets primary_artifact for ANY investigation deliverable, ignoring the `required` flag. This causes verification failures when optional investigation deliverables are present because the verification system expects the file to exist. Fix: check `deliverable.required == True` before returning the path.

---

# Investigation: primary_artifact set for non-required deliverables

**Question:** Why does `determine_primary_artifact()` cause verification failures for skills with optional investigation deliverables?

**Started:** 2025-12-06
**Updated:** 2025-12-06
**Owner:** Worker Agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** High (90%)

---

## Findings

### Finding 1: determine_primary_artifact ignores required flag

**Evidence:** The function at spawn.py:465-483 iterates over deliverables and returns the first investigation type found:

```python
def determine_primary_artifact(config: SpawnConfig) -> Optional[Path]:
    if not config.deliverables:
        return None

    for deliverable in config.deliverables:
        if deliverable.type == "investigation":
            rendered = render_deliverable_path(deliverable.path, config)
            return Path(rendered)

    return None
```

No check for `deliverable.required` - it returns ANY investigation deliverable.

**Source:** spawn.py:465-483

**Significance:** When a skill has an optional investigation deliverable, this function still returns a path, causing the verification system to expect a file that may not exist.

---

### Finding 2: SkillDeliverable has required field with default True

**Evidence:** The `SkillDeliverable` dataclass in skill_discovery.py:27-32 includes:

```python
@dataclass
class SkillDeliverable:
    type: str
    path: str
    required: bool = True  # <-- The field being ignored
    description: str = ""
```

**Source:** skill_discovery.py:27-32

**Significance:** The infrastructure exists to distinguish required from optional deliverables - it's just not being used in `determine_primary_artifact()`.

---

### Finding 3: primary_artifact drives verification logic

**Evidence:** In verification.py:77-82 and verification.py:188-203, the `primary_artifact` field is used to locate and verify investigation files:

```python
if agent_info and agent_info.get('primary_artifact'):
    primary_path = Path(agent_info['primary_artifact']).expanduser()
    ...
    if not primary_artifact_path.exists():
        errors.append(f"Investigation file not found: {primary_artifact}")
```

**Source:** verification.py:77-82, verification.py:188-203, verification.py:344-346

**Significance:** If primary_artifact is set but the file doesn't exist (because it was optional and agent skipped it), verification fails with "Investigation file not found" error.

---

## Synthesis

**Key Insights:**

1. **Root cause identified** - The bug is a missing condition check in `determine_primary_artifact()`. It should only return a path for required investigation deliverables.

2. **Fix is minimal** - Single line change: add `and deliverable.required` to the condition.

3. **No architectural change needed** - The required field already exists and is properly parsed from skill frontmatter. Just need to use it.

**Answer to Investigation Question:**

The function returns a primary_artifact path for ANY investigation deliverable, including optional ones. When an agent doesn't create the optional investigation file, verification fails because it expects the file at that path to exist. The fix is to only return paths for required investigation deliverables.

---

## Confidence Assessment

**Current Confidence:** High (90%)

**Why this level?**

Clear code path from bug to symptom. The fix is obvious and low-risk.

**What's certain:**

- ✅ `determine_primary_artifact()` doesn't check `required` flag (verified in code)
- ✅ `SkillDeliverable.required` field exists and defaults to True
- ✅ Verification logic uses `primary_artifact` to locate files and fails if not found

**What's uncertain:**

- ⚠️ Haven't traced an actual verification failure case yet (will test after fix)

**What would increase confidence to Very High:**

- Run tests after implementing fix
- Find or create a skill with optional investigation deliverable and verify fix works

---

## Implementation Recommendations

### Recommended Approach ⭐

**Add required check to determine_primary_artifact** - Add `and deliverable.required` to the condition

**Why this approach:**
- Minimal change (one line)
- Uses existing infrastructure
- Maintains backward compatibility (required defaults to True)

**Trade-offs accepted:**
- None significant

**Implementation sequence:**
1. Add `and deliverable.required` check to spawn.py:479
2. Run existing tests to verify no regression
3. Add specific test case for this scenario

---

## References

**Files Examined:**
- spawn.py:465-483 - determine_primary_artifact function
- skill_discovery.py:27-32 - SkillDeliverable dataclass
- verification.py:77-82, 188-203, 344-346 - primary_artifact usage in verification

---

## Investigation History

**2025-12-06 Phase: Planning:** Investigation started
- Initial question: Why does `determine_primary_artifact()` set primary_artifact for non-required deliverables?
- Context: spawn.py:465 doesn't check required flag, causing verification failures

**2025-12-06 Phase: Implementation:** Fix implemented
- Added `and deliverable.required` check to spawn.py:479
- Added 5 tests for `determine_primary_artifact()` in test_spawn_preview.py
- All 36 tests pass, no regressions

**2025-12-06 Phase: Complete:** Investigation completed
- Final confidence: High (90%)
- Status: Complete
- Key outcome: Single-line fix prevents verification failures for optional investigation deliverables
