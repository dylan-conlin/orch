**TLDR:** Added allowed_tools, disallowed_tools, and default_model fields to SkillMetadata dataclass. Implementation was straightforward - extended the dataclass with 3 optional fields and updated parse_skill_metadata to read them from frontmatter. Very high confidence (95%) - all 33 skill discovery tests pass.

---

# Investigation: Add Tool/Model Fields to Skill Frontmatter Schema

**Question:** How to extend SkillMetadata to support allowed_tools, disallowed_tools, and default_model in SKILL.md frontmatter?

**Started:** 2025-12-09
**Updated:** 2025-12-09
**Owner:** Worker agent (orch-cli-98u)
**Phase:** Complete
**Next Step:** None
**Status:** Complete
**Confidence:** Very High (95%)

---

## Findings

### Finding 1: SkillMetadata dataclass structure is straightforward

**Evidence:** The existing `SkillMetadata` dataclass uses Python dataclasses with optional fields defaulting to None.

**Source:** `src/orch/skill_discovery.py:45-55`

**Significance:** Adding new optional fields follows the existing pattern - just add fields with `Optional[List[str]] = None`.

---

### Finding 2: parse_skill_metadata reads from YAML frontmatter via .get()

**Evidence:** The function uses `frontmatter.get('field_name')` to read optional fields from YAML frontmatter, returning None when missing.

**Source:** `src/orch/skill_discovery.py:238-248`

**Significance:** Adding new fields to parsing is trivial - just add `frontmatter.get('field_name')` calls.

---

### Finding 3: Existing test patterns are clear and comprehensive

**Evidence:** Tests cover both dataclass construction and frontmatter parsing. Pattern: create content with YAML frontmatter, call parse_skill_metadata, assert field values.

**Source:** `tests/test_skill_discovery.py:77-286`

**Significance:** Following existing patterns made TDD straightforward.

---

## Synthesis

**Key Insights:**

1. **Simple extension pattern** - The SkillMetadata class is designed for easy extension with optional fields
2. **YAML-first design** - All skill configuration comes from SKILL.md frontmatter, parsed via yaml.safe_load
3. **Good test coverage** - Existing tests provided clear patterns to follow

**Answer to Investigation Question:**

Extend SkillMetadata by:
1. Adding 3 fields to dataclass: `allowed_tools`, `disallowed_tools`, `default_model`
2. Adding 3 `.get()` calls in parse_skill_metadata return statement
3. Writing tests following existing patterns

---

## Confidence Assessment

**Current Confidence:** Very High (95%)

**Why this level?**

All 33 skill discovery tests pass. Implementation is minimal (7 lines added) and follows established patterns.

**What's certain:**

- The dataclass correctly accepts the new fields
- parse_skill_metadata correctly reads these fields from frontmatter
- Default behavior (None when not specified) works correctly

**What's uncertain:**

- How these fields will be consumed by spawn logic (out of scope)
- Whether additional validation is needed for field values

---

## References

**Files Examined:**
- `src/orch/skill_discovery.py` - Main implementation
- `tests/test_skill_discovery.py` - Test patterns

**Commands Run:**
```bash
python -m pytest tests/test_skill_discovery.py -v
```

---

## Investigation History

**2025-12-09:** Investigation started
- Initial question: How to extend SkillMetadata for tool restrictions
- Context: Part of --agent flag integration

**2025-12-09:** Implementation complete
- Final confidence: Very High (95%)
- Status: Complete
- Key outcome: Added 3 new optional fields to SkillMetadata with full test coverage
