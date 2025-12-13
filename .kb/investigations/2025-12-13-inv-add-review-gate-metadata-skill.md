**TLDR:** Question: How to add review gate metadata to skill schema? Answer: Added `review` field to `SkillMetadata` dataclass accepting values 'required', 'optional', or 'none'. Field is parsed from YAML frontmatter in SKILL.md files. High confidence (95%) - implemented with 6 passing tests.

---

# Investigation: Add Review Gate Metadata to Skill Schema

**Question:** How should review gate metadata (review: required|optional|none) be added to the skill schema?

**Started:** 2025-12-13
**Updated:** 2025-12-13
**Owner:** Worker agent
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: Current Skill Schema Structure

**Evidence:** The `SkillMetadata` dataclass in `src/orch/skill_discovery.py` (lines 44-56) contains the following fields:
- `name`: str
- `triggers`: List[str]
- `deliverables`: List[SkillDeliverable]
- `verification`: Optional[SkillVerification]
- `category`: Optional[str]
- `description`: Optional[str]
- `allowed_tools`: Optional[List[str]]
- `disallowed_tools`: Optional[List[str]]
- `default_model`: Optional[str]

**Source:** `src/orch/skill_discovery.py:44-56`

**Significance:** The existing schema uses Optional[str] for simple string fields like `category`, `description`, and `default_model`. The `review` field fits this same pattern.

---

### Finding 2: Frontmatter Parsing Pattern

**Evidence:** The `parse_skill_metadata` function (lines 155-248) parses YAML frontmatter using `yaml.safe_load()` and extracts fields with `frontmatter.get('field_name')`. Simple string fields like `category`, `description`, `default_model` are passed directly from frontmatter to the dataclass.

**Source:** `src/orch/skill_discovery.py:238-248`

**Significance:** Adding a new field follows an established pattern - just add to the dataclass and include in the return statement of `parse_skill_metadata()`.

---

### Finding 3: Existing Test Patterns

**Evidence:** Tests in `tests/test_skill_discovery.py` follow consistent patterns:
- `TestSkillMetadata` class tests dataclass creation with various field combinations
- `TestParseSkillMetadata` class tests frontmatter parsing for each field type
- Tests verify both explicit values and default behaviors (None when not specified)

**Source:** `tests/test_skill_discovery.py:77-351`

**Significance:** New tests should follow the same pattern: test dataclass creation with the review field, test parsing from frontmatter, and test default behavior.

---

## Synthesis

**Key Insights:**

1. **Minimal Implementation** - The review field is a simple Optional[str] that follows existing patterns for `default_model` and `category`. No complex validation or parsing logic needed.

2. **YAML Frontmatter Integration** - Skills can specify `review: required|optional|none` in their SKILL.md frontmatter, and it will be automatically parsed into the metadata.

3. **Backward Compatible** - The field defaults to None, so existing skills without the review field continue to work unchanged.

**Answer to Investigation Question:**

The review gate metadata was added by:
1. Adding `review: Optional[str] = None` to the `SkillMetadata` dataclass (line 56)
2. Adding `review=frontmatter.get('review')` to the return statement of `parse_skill_metadata()` (line 248)
3. Adding 6 tests covering dataclass creation and frontmatter parsing

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

The implementation follows established patterns in the codebase and all 47 runnable tests pass (including 6 new tests specifically for the review field).

**What's certain:**

- ✅ The `review` field is correctly added to `SkillMetadata` dataclass
- ✅ Frontmatter parsing correctly extracts the `review` value
- ✅ Default behavior (None when not specified) works correctly
- ✅ All existing tests continue to pass

**What's uncertain:**

- ⚠️ Validation of allowed values ('required', 'optional', 'none') is not enforced - any string value is accepted
- ⚠️ Downstream consumers of SkillMetadata need to handle the new field

**What would increase confidence to Very High (100%):**

- Add validation to reject invalid review values
- Verify downstream code (spawn.py, spawn_prompt.py) handles the field correctly

---

## Implementation Recommendations

**Purpose:** Document what was implemented for future reference.

### Implemented Approach ⭐

**Add Optional[str] field to SkillMetadata** - Simple string field matching existing patterns.

**Why this approach:**
- Matches existing patterns (category, default_model)
- No complex validation needed at schema level
- Allows flexibility for future review values

**Trade-offs accepted:**
- No schema-level validation of allowed values
- Downstream code must handle unknown values gracefully

**Implementation sequence:**
1. Added field to dataclass
2. Added parsing in parse_skill_metadata
3. Added tests

### Alternative Approaches Considered

**Option B: Enum type for review values**
- **Pros:** Type safety, clear valid values
- **Cons:** More complex, requires enum definition, less flexible for future values
- **When to use instead:** If strict validation is needed

---

### Implementation Details

**What was implemented:**

1. `src/orch/skill_discovery.py:56` - Added `review: Optional[str] = None` to SkillMetadata
2. `src/orch/skill_discovery.py:248` - Added `review=frontmatter.get('review')` to parse_skill_metadata return
3. `tests/test_skill_discovery.py` - Added 6 tests:
   - `test_creates_with_review_gate`
   - `test_review_gate_defaults_to_none`
   - `test_parses_review_required_from_frontmatter`
   - `test_parses_review_optional_from_frontmatter`
   - `test_parses_review_none_from_frontmatter`
   - `test_review_defaults_to_none_when_not_in_frontmatter`

**Example SKILL.md usage:**
```yaml
---
name: feature-impl
skill-type: procedure
review: required
---
```

---

## References

**Files Examined:**
- `src/orch/skill_discovery.py` - Main implementation file
- `tests/test_skill_discovery.py` - Test file
- `~/.claude/skills/worker/investigation/SKILL.md` - Example skill frontmatter
- `~/.claude/skills/worker/feature-impl/SKILL.md` - Example skill frontmatter
- `~/.claude/skills/worker/codebase-audit/SKILL.md` - Example skill frontmatter

**Commands Run:**
```bash
# Run tests
uv run python -m pytest tests/test_skill_discovery.py -v --tb=short

# Verify import
uv run python -c "from orch.skill_discovery import SkillMetadata; m = SkillMetadata(name='test', triggers=[], deliverables=[], review='required'); print(m.review)"
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

**2025-12-13 [start]:** Investigation started
- Initial question: How to add review gate metadata to skill schema?
- Context: Issue orch-cli-dfe requested adding review gate metadata

**2025-12-13 [complete]:** Investigation completed
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Added `review` field to SkillMetadata with 6 tests passing
