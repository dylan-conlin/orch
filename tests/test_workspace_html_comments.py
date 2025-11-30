"""Test workspace parsing with HTML comments."""

from pathlib import Path
import tempfile
from orch.workspace import parse_workspace_verification, parse_checkboxes, get_section


def test_parse_checkboxes_ignores_html_comments():
    """Test that parse_checkboxes ignores checkbox items within HTML comments."""
    # Section with only HTML comment examples
    section = """
<!-- Examples:
- [ ] Spawn fix agent
- [ ] Update documentation
- [ ] Add tests
-->

None - work complete.
"""
    items = parse_checkboxes(section)
    assert len(items) == 0, "Should not find checkbox items in HTML comments"


def test_parse_checkboxes_with_mixed_content():
    """Test parsing checkboxes with both HTML comments and real items."""
    section = """
<!-- Examples:
- [ ] This is an example
- [ ] Another example
-->

- [ ] Real action item 1
- [x] Real completed item
- [ ] Real action item 2
"""
    items = parse_checkboxes(section)
    assert len(items) == 3, f"Should find 3 real items, found {len(items)}"
    assert items[0].text == "Real action item 1"
    assert items[0].checked is False
    assert items[1].text == "Real completed item"
    assert items[1].checked is True
    assert items[2].text == "Real action item 2"
    assert items[2].checked is False


def test_workspace_verification_with_html_comments():
    """Test full workspace parsing ignores HTML comment examples."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""
---
Phase: Complete
---

## Verification Required

- [x] Task completed
- [x] Tests pass

## Next-Actions

**Purpose:** Actions that should happen after this work completes.

<!-- Examples:
- [ ] Spawn fix agent: Change logs query to sort DESC
- [ ] Update documentation
- [ ] Add integration tests
-->

None - work complete.
""")
        f.flush()
        
        data = parse_workspace_verification(Path(f.name))
        
        # Should find verification items
        assert data.verification_complete is True
        assert len(data.verification_items) == 2
        
        # Should NOT find HTML comment examples as next-actions
        assert data.has_pending_actions is False
        assert len(data.next_actions) == 0, f"Found {len(data.next_actions)} next-actions from HTML comments"
        
        Path(f.name).unlink()


def test_multiline_html_comments():
    """Test that multi-line HTML comments are properly removed."""
    section = """
Real content before

<!-- This is a
     multi-line
     comment with:
- [ ] Checkbox in comment
- [ ] Another checkbox
-->

- [ ] Real checkbox after comment
"""
    items = parse_checkboxes(section)
    assert len(items) == 1, f"Should find 1 real item, found {len(items)}"
    assert items[0].text == "Real checkbox after comment"


if __name__ == '__main__':
    test_parse_checkboxes_ignores_html_comments()
    test_parse_checkboxes_with_mixed_content()
    test_workspace_verification_with_html_comments()
    test_multiline_html_comments()
    print("✅ All tests passed!")
