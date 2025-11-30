"""Tests for SessionStart context loading hook.

Tests the hook script at ~/.orch/hooks/load-orchestration-context.py
which auto-loads orchestration context (active agents, recent artifacts,
ROADMAP priorities) when Claude Code sessions start.
"""

import pytest
import json
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def hook_module():
    """Load the hook script as a module for testing."""
    hook_path = Path.home() / ".orch" / "hooks" / "load-orchestration-context.py"

    if not hook_path.exists():
        pytest.skip(f"Hook script not found at {hook_path}")

    spec = importlib.util.spec_from_file_location("hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def orch_project(tmp_path):
    """Create a temporary project with .orch structure."""
    orch_dir = tmp_path / ".orch"
    orch_dir.mkdir()
    (orch_dir / "workspace").mkdir()
    return tmp_path


@pytest.fixture
def sample_readme_content():
    """Sample README.md content with decisions and investigations."""
    return """# .orch README

## Quick Links

- Orchestration guide: See CLAUDE.md
- Active work: See ROADMAP.md

## Recent Decisions (Last 14 Days)

- `decisions/2025-11-27-feature-design.md` - [Accepted] 2025-11-27
- `decisions/2025-11-26-api-pattern.md` - [Proposed] 2025-11-26

## Recent Investigations (Last 7 Days)

- `investigations/simple/2025-11-27-debug-issue.md` - [simple] [Complete]
- `investigations/simple/2025-11-26-analyze-performance.md` - [simple] [In Progress]

## Other Section

This should not be included in the summary.
"""


@pytest.fixture
def sample_roadmap_content():
    """Sample ROADMAP.md content."""
    return """# ROADMAP

## Active Work

**Priority 1:** Implement feature X

This is the current focus.

---

## Backlog

Items for later consideration.
"""


@pytest.fixture
def sample_agent_status():
    """Sample orch status --format json output."""
    return json.dumps({
        "agents": [
            {
                "agent_id": "2025-11-28-feat-test-feature",
                "phase": "Implementation",
                "window": "workers:1",
                "priority": "normal",
                "alerts": []
            },
            {
                "agent_id": "2025-11-28-inv-debug-issue",
                "phase": "Complete",
                "window": "workers:2",
                "priority": "normal",
                "alerts": [{"type": "workspace"}]
            }
        ]
    })


# =============================================================================
# INPUT VALIDATION TESTS
# =============================================================================

class TestInputValidation:
    """Tests for hook input validation and source filtering."""

    def test_startup_source_triggers_context_load(self, hook_module, orch_project):
        """Hook should process 'startup' source."""
        with patch.object(hook_module, 'find_orch_directory', return_value=orch_project / ".orch"):
            with patch.object(hook_module, 'load_active_agents', return_value="**Active Agents:** None\n"):
                with patch.object(hook_module, 'load_readme_summary', return_value=None):
                    with patch.object(hook_module, 'load_roadmap_priorities', return_value=None):
                        # Simulate startup source input
                        input_json = '{"source": "startup"}'
                        with patch('sys.stdin', StringIO(input_json)):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with pytest.raises(SystemExit) as exc_info:
                                    hook_module.main()
                                assert exc_info.value.code == 0
                                # Should have produced output
                                output = mock_stdout.getvalue()
                                assert len(output) > 0

    def test_resume_source_triggers_context_load(self, hook_module, orch_project):
        """Hook should process 'resume' source."""
        with patch.object(hook_module, 'find_orch_directory', return_value=orch_project / ".orch"):
            with patch.object(hook_module, 'load_active_agents', return_value="**Active Agents:** None\n"):
                with patch.object(hook_module, 'load_readme_summary', return_value=None):
                    with patch.object(hook_module, 'load_roadmap_priorities', return_value=None):
                        input_json = '{"source": "resume"}'
                        with patch('sys.stdin', StringIO(input_json)):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with pytest.raises(SystemExit) as exc_info:
                                    hook_module.main()
                                assert exc_info.value.code == 0
                                output = mock_stdout.getvalue()
                                assert len(output) > 0

    def test_clear_source_skipped(self, hook_module):
        """Hook should skip 'clear' source (no context loading needed)."""
        input_json = '{"source": "clear"}'
        with patch('sys.stdin', StringIO(input_json)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    hook_module.main()
                assert exc_info.value.code == 0
                # Should NOT have produced output
                output = mock_stdout.getvalue()
                assert output == ""

    def test_compact_source_skipped(self, hook_module):
        """Hook should skip 'compact' source (no context loading needed)."""
        input_json = '{"source": "compact"}'
        with patch('sys.stdin', StringIO(input_json)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    hook_module.main()
                assert exc_info.value.code == 0
                output = mock_stdout.getvalue()
                assert output == ""

    def test_invalid_json_input_handled_gracefully(self, hook_module):
        """Hook should exit gracefully on invalid JSON input."""
        with patch('sys.stdin', StringIO("not valid json")):
            with pytest.raises(SystemExit) as exc_info:
                hook_module.main()
            # Should exit cleanly (0), not crash
            assert exc_info.value.code == 0

    def test_empty_input_handled_gracefully(self, hook_module):
        """Hook should exit gracefully on empty input."""
        with patch('sys.stdin', StringIO("")):
            with pytest.raises(SystemExit) as exc_info:
                hook_module.main()
            assert exc_info.value.code == 0


# =============================================================================
# DIRECTORY DETECTION TESTS
# =============================================================================

class TestDirectoryDetection:
    """Tests for .orch directory detection."""

    def test_find_orch_in_current_directory(self, hook_module, orch_project):
        """Should find .orch in current working directory."""
        with patch('pathlib.Path.cwd', return_value=orch_project):
            result = hook_module.find_orch_directory()
            assert result == orch_project / ".orch"

    def test_find_orch_in_parent_directory(self, hook_module, orch_project):
        """Should find .orch in parent directory."""
        subdir = orch_project / "src" / "components"
        subdir.mkdir(parents=True)

        with patch('pathlib.Path.cwd', return_value=subdir):
            result = hook_module.find_orch_directory()
            assert result == orch_project / ".orch"

    def test_returns_none_when_no_orch_found(self, hook_module, tmp_path):
        """Should return None when no .orch directory exists."""
        with patch('pathlib.Path.cwd', return_value=tmp_path):
            result = hook_module.find_orch_directory()
            assert result is None

    def test_no_orch_directory_exits_silently(self, hook_module):
        """Hook should exit silently when not in orchestrator context."""
        with patch.object(hook_module, 'find_orch_directory', return_value=None):
            input_json = '{"source": "startup"}'
            with patch('sys.stdin', StringIO(input_json)):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    with pytest.raises(SystemExit) as exc_info:
                        hook_module.main()
                    assert exc_info.value.code == 0
                    assert mock_stdout.getvalue() == ""


# =============================================================================
# CONTEXT LOADING TESTS
# =============================================================================

class TestContextLoading:
    """Tests for loading orchestration context."""

    def test_load_active_agents_formats_output(self, hook_module, sample_agent_status):
        """Should format agent status into readable markdown."""
        with patch.object(hook_module, 'run_command', return_value=sample_agent_status):
            result = hook_module.load_active_agents()

            assert "**Active Agents:**" in result
            assert "2025-11-28-feat-test-feature" in result
            assert "Phase: Implementation" in result
            assert "Window: workers:1" in result

    def test_load_active_agents_shows_alerts(self, hook_module, sample_agent_status):
        """Should display agent alerts in output."""
        with patch.object(hook_module, 'run_command', return_value=sample_agent_status):
            result = hook_module.load_active_agents()
            # Agent with workspace alert should show warning
            assert "workspace" in result

    def test_load_active_agents_handles_no_agents(self, hook_module):
        """Should handle empty agent list gracefully."""
        with patch.object(hook_module, 'run_command', return_value='{"agents": []}'):
            result = hook_module.load_active_agents()
            assert "**Active Agents:** None" in result

    def test_load_active_agents_handles_command_failure(self, hook_module):
        """Should return None when orch status command fails."""
        with patch.object(hook_module, 'run_command', return_value=None):
            result = hook_module.load_active_agents()
            assert result is None

    def test_load_active_agents_limits_to_five(self, hook_module):
        """Should limit displayed agents to 5."""
        many_agents = {
            "agents": [
                {"agent_id": f"agent-{i}", "phase": "Active", "window": f"w:{i}", "priority": "normal", "alerts": []}
                for i in range(10)
            ]
        }
        with patch.object(hook_module, 'run_command', return_value=json.dumps(many_agents)):
            result = hook_module.load_active_agents()
            # Should show 5 agents plus "and X more" message
            assert "...and 5 more agents" in result

    def test_load_readme_summary_extracts_sections(self, hook_module, orch_project, sample_readme_content):
        """Should extract Recent Decisions and Investigations sections."""
        readme_path = orch_project / ".orch" / "README.md"
        readme_path.write_text(sample_readme_content)

        result = hook_module.load_readme_summary(orch_project / ".orch")

        assert "Recent Decisions" in result
        assert "decisions/2025-11-27-feature-design.md" in result
        assert "Recent Investigations" in result
        assert "investigations/simple/2025-11-27-debug-issue.md" in result
        # Should not include "Other Section"
        assert "Other Section" not in result

    def test_load_readme_summary_handles_missing_file(self, hook_module, orch_project):
        """Should return None when README.md doesn't exist."""
        result = hook_module.load_readme_summary(orch_project / ".orch")
        assert result is None

    def test_load_roadmap_priorities(self, hook_module, orch_project, sample_roadmap_content):
        """Should load ROADMAP.md content."""
        roadmap_path = orch_project / ".orch" / "ROADMAP.md"
        roadmap_path.write_text(sample_roadmap_content)

        result = hook_module.load_roadmap_priorities(orch_project / ".orch")

        assert "# ROADMAP" in result
        assert "Priority 1" in result

    def test_load_roadmap_handles_missing_file(self, hook_module, orch_project):
        """Should return None when ROADMAP.md doesn't exist."""
        result = hook_module.load_roadmap_priorities(orch_project / ".orch")
        assert result is None


# =============================================================================
# OUTPUT FORMAT TESTS
# =============================================================================

class TestOutputFormat:
    """Tests for hook JSON output format."""

    def test_output_is_valid_json(self, hook_module, orch_project):
        """Output should be valid JSON."""
        with patch.object(hook_module, 'find_orch_directory', return_value=orch_project / ".orch"):
            with patch.object(hook_module, 'load_active_agents', return_value="**Active Agents:** Test\n"):
                with patch.object(hook_module, 'load_readme_summary', return_value=None):
                    with patch.object(hook_module, 'load_roadmap_priorities', return_value=None):
                        input_json = '{"source": "startup"}'
                        with patch('sys.stdin', StringIO(input_json)):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with pytest.raises(SystemExit):
                                    hook_module.main()
                                output = mock_stdout.getvalue()
                                # Should parse as valid JSON
                                parsed = json.loads(output)
                                assert isinstance(parsed, dict)

    def test_output_has_correct_structure(self, hook_module, orch_project):
        """Output should have hookSpecificOutput.additionalContext structure."""
        with patch.object(hook_module, 'find_orch_directory', return_value=orch_project / ".orch"):
            with patch.object(hook_module, 'load_active_agents', return_value="**Active Agents:** Test\n"):
                with patch.object(hook_module, 'load_readme_summary', return_value=None):
                    with patch.object(hook_module, 'load_roadmap_priorities', return_value=None):
                        input_json = '{"source": "startup"}'
                        with patch('sys.stdin', StringIO(input_json)):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with pytest.raises(SystemExit):
                                    hook_module.main()
                                output = mock_stdout.getvalue()
                                parsed = json.loads(output)

                                assert "hookSpecificOutput" in parsed
                                assert "hookEventName" in parsed["hookSpecificOutput"]
                                assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
                                assert "additionalContext" in parsed["hookSpecificOutput"]

    def test_output_includes_header(self, hook_module, orch_project):
        """Output additionalContext should include orchestration header."""
        with patch.object(hook_module, 'find_orch_directory', return_value=orch_project / ".orch"):
            with patch.object(hook_module, 'load_active_agents', return_value="**Active Agents:** Test\n"):
                with patch.object(hook_module, 'load_readme_summary', return_value=None):
                    with patch.object(hook_module, 'load_roadmap_priorities', return_value=None):
                        input_json = '{"source": "startup"}'
                        with patch('sys.stdin', StringIO(input_json)):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with pytest.raises(SystemExit):
                                    hook_module.main()
                                output = mock_stdout.getvalue()
                                parsed = json.loads(output)
                                context = parsed["hookSpecificOutput"]["additionalContext"]

                                assert "Orchestration Context" in context
                                assert "Auto-loaded via SessionStart hook" in context


# =============================================================================
# GRACEFUL DEGRADATION TESTS
# =============================================================================

class TestGracefulDegradation:
    """Tests for graceful handling of errors and edge cases."""

    def test_handles_subprocess_timeout(self, hook_module):
        """Should handle subprocess timeouts gracefully."""
        def timeout_side_effect(*args, **kwargs):
            import subprocess
            raise subprocess.TimeoutExpired(cmd="test", timeout=5)

        with patch('subprocess.run', side_effect=timeout_side_effect):
            result = hook_module.run_command(['orch', 'status', '--format', 'json'])
            assert result is None

    def test_handles_subprocess_error(self, hook_module):
        """Should handle subprocess errors gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "error"

        with patch('subprocess.run', return_value=mock_result):
            result = hook_module.run_command(['orch', 'status', '--format', 'json'])
            assert result is None

    def test_handles_invalid_json_from_orch_status(self, hook_module):
        """Should handle invalid JSON from orch status gracefully."""
        with patch.object(hook_module, 'run_command', return_value="not valid json"):
            result = hook_module.load_active_agents()
            assert result is None

    def test_handles_readme_read_error(self, hook_module, orch_project):
        """Should handle README read errors gracefully."""
        readme_path = orch_project / ".orch" / "README.md"
        readme_path.write_text("content")

        # Make file unreadable by mocking open
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            result = hook_module.load_readme_summary(orch_project / ".orch")
            assert result is None

    def test_handles_roadmap_read_error(self, hook_module, orch_project):
        """Should handle ROADMAP read errors gracefully."""
        roadmap_path = orch_project / ".orch" / "ROADMAP.md"
        roadmap_path.write_text("content")

        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            result = hook_module.load_roadmap_priorities(orch_project / ".orch")
            assert result is None


# =============================================================================
# RUN_COMMAND TESTS
# =============================================================================

class TestRunCommand:
    """Tests for the run_command helper function."""

    def test_run_command_returns_stdout(self, hook_module):
        """Should return command stdout on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output text\n"

        with patch('subprocess.run', return_value=mock_result):
            result = hook_module.run_command(['echo', 'test'])
            assert result == "output text"

    def test_run_command_strips_whitespace(self, hook_module):
        """Should strip trailing whitespace from output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  output  \n\n"

        with patch('subprocess.run', return_value=mock_result):
            result = hook_module.run_command(['echo', 'test'])
            assert result == "output"

    def test_run_command_uses_timeout(self, hook_module):
        """Should pass timeout to subprocess."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            hook_module.run_command(['echo', 'test'])
            # Verify timeout was passed
            call_kwargs = mock_run.call_args[1]
            assert 'timeout' in call_kwargs
            assert call_kwargs['timeout'] == 5  # Default timeout in hook


# =============================================================================
# PENDING REVIEW TESTS
# =============================================================================

class TestPendingDecisions:
    """Tests for loading pending (proposed) decisions."""

    @pytest.fixture
    def sample_proposed_decision(self):
        """Sample decision with Status: Proposed."""
        return """# Decision: New Architecture

**Date:** 2025-11-28
**Status:** Proposed
**Type:** Architecture

## Background

Proposing a new architecture approach.

## Decision

Use microservices pattern.
"""

    @pytest.fixture
    def sample_accepted_decision(self):
        """Sample decision with Status: Accepted."""
        return """# Decision: Existing Pattern

**Date:** 2025-11-28
**Status:** Accepted
**Type:** Architecture

## Background

Using established pattern.

## Decision

Use monolith pattern.
"""

    def test_load_pending_decisions_finds_proposed(
        self, hook_module, orch_project, sample_proposed_decision
    ):
        """Should find decisions with Status: Proposed."""
        dec_dir = orch_project / ".orch" / "decisions"
        dec_dir.mkdir(parents=True)

        dec_file = dec_dir / "2025-11-28-new-architecture.md"
        dec_file.write_text(sample_proposed_decision)

        result = hook_module.load_pending_decisions(orch_project / ".orch")

        assert result is not None
        assert "Proposed" in result
        assert "2025-11-28-new-architecture" in result

    def test_load_pending_decisions_excludes_accepted(
        self, hook_module, orch_project, sample_accepted_decision
    ):
        """Should not include decisions with Status: Accepted."""
        dec_dir = orch_project / ".orch" / "decisions"
        dec_dir.mkdir(parents=True)

        dec_file = dec_dir / "2025-11-28-existing-pattern.md"
        dec_file.write_text(sample_accepted_decision)

        result = hook_module.load_pending_decisions(orch_project / ".orch")

        assert result is None or "2025-11-28-existing-pattern" not in result

    def test_load_pending_decisions_handles_missing_dir(self, hook_module, orch_project):
        """Should handle missing decisions directory gracefully."""
        result = hook_module.load_pending_decisions(orch_project / ".orch")
        assert result is None


class TestAttentionItems:
    """Tests for loading attention items from backlog.json."""

    @pytest.fixture
    def sample_backlog_with_blocked(self):
        """Sample backlog.json with blocked item."""
        return {
            "version": "1.0",
            "features": [
                {
                    "id": "completed-feature",
                    "description": "Already done",
                    "status": "complete",
                    "type": "feature",
                    "resolution": None
                },
                {
                    "id": "blocked-feature",
                    "description": "Waiting on external dependency",
                    "status": "blocked",
                    "type": "feature",
                    "resolution": None
                },
                {
                    "id": "pending-feature",
                    "description": "Not started",
                    "status": "pending",
                    "type": "feature",
                    "resolution": None
                }
            ]
        }

    @pytest.fixture
    def sample_backlog_with_unresolved_bug(self):
        """Sample backlog.json with completed bug that has no resolution."""
        return {
            "version": "1.0",
            "features": [
                {
                    "id": "fixed-bug",
                    "description": "Bug that was fixed",
                    "status": "complete",
                    "type": "bug",
                    "resolution": "fix"
                },
                {
                    "id": "unresolved-bug",
                    "description": "Bug completed but no resolution recorded",
                    "status": "complete",
                    "type": "bug",
                    "resolution": None
                }
            ]
        }

    @pytest.fixture
    def sample_backlog_no_attention(self):
        """Sample backlog.json with no items needing attention."""
        return {
            "version": "1.0",
            "features": [
                {
                    "id": "completed-feature",
                    "description": "Already done",
                    "status": "complete",
                    "type": "feature",
                    "resolution": None
                },
                {
                    "id": "pending-feature",
                    "description": "Not started",
                    "status": "pending",
                    "type": "feature",
                    "resolution": None
                }
            ]
        }

    def test_load_attention_items_finds_blocked(
        self, hook_module, orch_project, sample_backlog_with_blocked
    ):
        """Should find items with status: blocked."""
        backlog_file = orch_project / ".orch" / "backlog.json"
        backlog_file.write_text(json.dumps(sample_backlog_with_blocked))

        result = hook_module.load_attention_items(orch_project / ".orch")

        assert result is not None
        assert "blocked-feature" in result
        assert "Waiting on external dependency" in result

    def test_load_attention_items_finds_unresolved_bugs(
        self, hook_module, orch_project, sample_backlog_with_unresolved_bug
    ):
        """Should find bugs with status: complete but resolution: null."""
        backlog_file = orch_project / ".orch" / "backlog.json"
        backlog_file.write_text(json.dumps(sample_backlog_with_unresolved_bug))

        result = hook_module.load_attention_items(orch_project / ".orch")

        assert result is not None
        assert "unresolved-bug" in result
        assert "fixed-bug" not in result  # Has resolution, should be excluded

    def test_load_attention_items_excludes_normal_items(
        self, hook_module, orch_project, sample_backlog_no_attention
    ):
        """Should not include items that don't need attention."""
        backlog_file = orch_project / ".orch" / "backlog.json"
        backlog_file.write_text(json.dumps(sample_backlog_no_attention))

        result = hook_module.load_attention_items(orch_project / ".orch")

        assert result is None

    def test_load_attention_items_handles_missing_file(self, hook_module, orch_project):
        """Should handle missing backlog.json gracefully."""
        result = hook_module.load_attention_items(orch_project / ".orch")
        assert result is None

    def test_load_attention_items_handles_invalid_json(self, hook_module, orch_project):
        """Should handle invalid JSON gracefully."""
        backlog_file = orch_project / ".orch" / "backlog.json"
        backlog_file.write_text("not valid json")

        result = hook_module.load_attention_items(orch_project / ".orch")
        assert result is None


class TestPendingReviewSection:
    """Tests for the combined pending review section output."""

    def test_pending_review_section_format(
        self, hook_module, orch_project
    ):
        """Should format pending review section with counts and links."""
        # Create both types of pending items
        # Proposed decision
        dec_dir = orch_project / ".orch" / "decisions"
        dec_dir.mkdir(parents=True)
        (dec_dir / "2025-11-28-proposed.md").write_text(
            "# Decision\n**Status:** Proposed\n"
        )

        # Blocked backlog item
        backlog_file = orch_project / ".orch" / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [{
                "id": "blocked-item",
                "description": "Something is blocking this",
                "status": "blocked",
                "type": "feature",
                "resolution": None
            }]
        }))

        result = hook_module.load_pending_review(orch_project / ".orch")

        assert result is not None
        assert "Pending Review" in result

    def test_pending_review_returns_none_when_no_pending(self, hook_module, orch_project):
        """Should return None when there are no pending items."""
        # Create dirs but no pending items
        (orch_project / ".orch" / "decisions").mkdir(parents=True)
        backlog_file = orch_project / ".orch" / "backlog.json"
        backlog_file.write_text(json.dumps({
            "version": "1.0",
            "features": [{"id": "done", "status": "complete", "type": "feature", "resolution": None}]
        }))

        result = hook_module.load_pending_review(orch_project / ".orch")

        assert result is None


class TestPendingReviewIntegration:
    """Integration tests for pending review in full context output."""

    def test_context_includes_pending_review(self, hook_module, orch_project):
        """Context output should include pending review section when items exist."""
        # Create a proposed decision
        dec_dir = orch_project / ".orch" / "decisions"
        dec_dir.mkdir(parents=True)
        (dec_dir / "2025-11-28-proposed.md").write_text(
            "# Decision\n**Status:** Proposed\n"
        )

        with patch.object(hook_module, 'find_orch_directory', return_value=orch_project / ".orch"):
            with patch.object(hook_module, 'load_active_agents', return_value="**Active Agents:** None\n"):
                with patch.object(hook_module, 'load_readme_summary', return_value=None):
                    with patch.object(hook_module, 'load_roadmap_priorities', return_value=None):
                        input_json = '{"source": "startup"}'
                        with patch('sys.stdin', StringIO(input_json)):
                            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                with pytest.raises(SystemExit):
                                    hook_module.main()
                                output = mock_stdout.getvalue()

                                if output:
                                    parsed = json.loads(output)
                                    context = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
                                    # If pending review is implemented, it should appear
                                    # This test will initially fail (TDD)
                                    assert "Pending Review" in context or "Proposed" in context
