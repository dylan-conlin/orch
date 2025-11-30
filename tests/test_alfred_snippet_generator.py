"""Tests for Alfred snippet generator utility."""

import json
import os
import plistlib
import pytest
import tempfile
import zipfile


def test_create_snippet_json_structure():
    """Test that snippet JSON has correct structure with required fields."""
    from tools.alfred_snippet_generator import create_snippet_json

    snippet_data = {
        "name": "Test Snippet",
        "keyword": "!test",
        "snippet": "This is test content"
    }

    result = create_snippet_json(snippet_data)

    # Parse JSON to verify it's valid
    parsed = json.loads(result)

    # Verify top-level structure
    assert "alfredsnippet" in parsed

    # Verify required fields
    alfred_snippet = parsed["alfredsnippet"]
    assert alfred_snippet["name"] == "Test Snippet"
    assert alfred_snippet["keyword"] == "!test"
    assert alfred_snippet["snippet"] == "This is test content"

    # Verify uid is present and is a valid UUID format
    assert "uid" in alfred_snippet
    uid = alfred_snippet["uid"]
    # UUID format: 8-4-4-4-12 hexadecimal characters
    assert len(uid) == 36  # Standard UUID length with hyphens
    assert uid.count("-") == 4

    # Verify dontautoexpand defaults to false (auto-expand enabled)
    assert "dontautoexpand" in alfred_snippet
    assert alfred_snippet["dontautoexpand"] is False


def test_create_snippet_with_autoexpand_disabled():
    """Test that snippet can be created with auto-expand disabled."""
    from tools.alfred_snippet_generator import create_snippet_json

    snippet_data = {
        "name": "Manual Snippet",
        "keyword": "!manual",
        "snippet": "Requires manual activation",
        "dontautoexpand": True
    }

    result = create_snippet_json(snippet_data)
    parsed = json.loads(result)

    alfred_snippet = parsed["alfredsnippet"]
    assert alfred_snippet["dontautoexpand"] is True


def test_create_info_plist():
    """Test that info.plist is created with correct structure."""
    from tools.alfred_snippet_generator import create_info_plist

    collection_name = "Test Collection"
    config = {
        "snippetkeywordprefix": "!",
        "snippetkeywordsuffix": ""
    }

    result = create_info_plist(collection_name, config)

    # Parse plist to verify it's valid
    parsed = plistlib.loads(result)

    # Verify required fields
    assert parsed["snippetkeywordprefix"] == "!"
    assert parsed["snippetkeywordsuffix"] == ""

    # Verify it's valid XML plist format
    assert result.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    assert b'<plist version="1.0">' in result


def test_generate_alfredsnippets_file():
    """Test complete .alfredsnippets file generation."""
    from tools.alfred_snippet_generator import generate_alfredsnippets

    snippets = [
        {
            "name": "Snippet 1",
            "keyword": "!s1",
            "snippet": "Content 1"
        },
        {
            "name": "Snippet 2",
            "keyword": "!s2",
            "snippet": "Content 2"
        }
    ]

    collection_name = "Test Collection"
    config = {
        "snippetkeywordprefix": "!",
        "snippetkeywordsuffix": ""
    }

    # Use temporary directory for output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test.alfredsnippets")

        result_path = generate_alfredsnippets(snippets, collection_name, config, output_path)

        # Verify file was created
        assert os.path.exists(result_path)
        assert result_path.endswith(".alfredsnippets")

        # Verify it's a valid ZIP file
        assert zipfile.is_zipfile(result_path)

        # Verify contents
        with zipfile.ZipFile(result_path, 'r') as zf:
            namelist = zf.namelist()

            # Should have info.plist and 2 snippet JSON files
            assert "info.plist" in namelist
            assert len([n for n in namelist if n.endswith(".json")]) == 2

            # Verify info.plist content
            info_plist_data = zf.read("info.plist")
            parsed_plist = plistlib.loads(info_plist_data)
            assert parsed_plist["snippetkeywordprefix"] == "!"

            # Verify snippet JSON files
            for name in namelist:
                if name.endswith(".json"):
                    snippet_data = zf.read(name)
                    parsed_snippet = json.loads(snippet_data)
                    assert "alfredsnippet" in parsed_snippet
                    assert "uid" in parsed_snippet["alfredsnippet"]
                    assert "name" in parsed_snippet["alfredsnippet"]
