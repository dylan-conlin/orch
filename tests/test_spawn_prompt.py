"""
Tests for spawn prompt generation in orch spawn.

Tests that spawn prompts use beads as the source of truth for progress tracking,
not WORKSPACE.md files.

Related: orch-cli-30j (Remove legacy WORKSPACE.md instructions)
"""

import pytest
from pathlib import Path

from orch.spawn import (
    build_spawn_prompt,
    SpawnConfig,
    DEFAULT_DELIVERABLES,
)


class TestSpawnPromptBeadsFirst:
    """
    Validates that spawn prompts use beads for progress tracking.

    Beads (`bd comment`) is the source of truth for agent progress.
    WORKSPACE.md instructions should not be included in spawn prompts.
    Related: orch-cli-30j
    """

    def test_spawn_prompt_does_not_include_workspace_instructions(self):
        """Verify spawn prompts do NOT include WORKSPACE.md creation/update instructions."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # These WORKSPACE.md-specific instructions should NOT appear
        # (beads is now source of truth)
        legacy_sections = [
            "COORDINATION ARTIFACT POPULATION (REQUIRED):",
            "Fill TLDR / summary section (problem, status, next)",
            "Capture Session Scope (validate scope estimate, mark checkpoint points)",
            "Fill Progress Tracking (tasks with time estimates)",
            "Update metadata fields (Owner, Started, Phase, Status)",
            "Update Last Activity after each completed task",
            ".orch/docs/workspace-conventions.md for details",
            "Workspace still tracks detailed work state",
            "VERIFY workspace exists",
            "UPDATE workspace",
            "Update workspace Phase field",
        ]

        found_legacy = []
        for section in legacy_sections:
            if section in prompt:
                found_legacy.append(section)

        assert not found_legacy, (
            f"Spawn prompt contains legacy WORKSPACE.md instructions:\n"
            f"{chr(10).join('- ' + s for s in found_legacy)}\n\n"
            f"Beads is now the source of truth for progress tracking.\n"
            f"Remove workspace-specific instructions from spawn_prompt.py.\n"
            f"Reference: orch-cli-30j"
        )

    def test_spawn_prompt_includes_beads_tracking_when_beads_id_provided(self):
        """Verify spawn prompts include beads tracking when beads_id is provided."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Beads progress tracking should be present
        required_beads_sections = [
            "BEADS PROGRESS TRACKING",
            "bd comment test-123",
            "Phase: Planning",
            "Phase: Implementing",
            "Phase: Complete",
        ]

        missing_sections = []
        for section in required_beads_sections:
            if section not in prompt:
                missing_sections.append(section)

        assert not missing_sections, (
            f"Spawn prompt missing beads tracking sections:\n"
            f"{chr(10).join('- ' + s for s in missing_sections)}\n\n"
            f"Beads is the source of truth for progress tracking.\n"
            f"Reference: orch-cli-30j"
        )

    def test_spawn_prompt_status_updates_use_beads_not_workspace(self):
        """Verify STATUS UPDATES section references beads, not workspace."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should NOT reference workspace for status updates
        assert "Update Phase: field in your coordination artifact (WORKSPACE.md)" not in prompt, \
            "STATUS UPDATES should not reference WORKSPACE.md"
        assert "Update Phase: field in WORKSPACE.md" not in prompt, \
            "STATUS UPDATES should not reference WORKSPACE.md"
        assert "reads workspace Phase field" not in prompt, \
            "Monitoring should not reference workspace Phase field"

    def test_spawn_prompt_verification_does_not_reference_workspace(self):
        """Verify verification guidance does not tell agents to copy to workspace."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should NOT tell agents to copy verification requirements to workspace
        assert "Copy the verification requirements above to your workspace" not in prompt, \
            "Verification should not reference copying to workspace"

    def test_fallback_template_does_not_reference_workspace(self):
        """Verify fallback template does not contain WORKSPACE.md references."""
        from orch.spawn_prompt import fallback_template

        template = fallback_template()

        # Fallback should not reference WORKSPACE.md
        assert "WORKSPACE.md" not in template, \
            "Fallback template should not reference WORKSPACE.md"
        assert "Update workspace" not in template, \
            "Fallback template should not reference updating workspace"


class TestSpawnPromptCompletionProtocol:
    """
    Validates that spawn prompts include prominent completion protocol instructions.

    Agents were completing work but not following completion protocol (no Phase: Complete,
    no /exit). This adds prominent instructions at the start of the prompt.
    Related: orch-cli-bha
    """

    def test_spawn_prompt_includes_session_complete_protocol_block(self):
        """Verify spawn prompts include SESSION COMPLETE PROTOCOL block prominently."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # SESSION COMPLETE PROTOCOL should be present
        assert "SESSION COMPLETE PROTOCOL" in prompt, \
            "Spawn prompt must include SESSION COMPLETE PROTOCOL block"

        # Should include the key completion instructions
        assert "Phase: Complete" in prompt, \
            "Spawn prompt must mention Phase: Complete in completion protocol"
        assert "/exit" in prompt, \
            "Spawn prompt must mention /exit command"

    def test_session_complete_protocol_appears_early_in_prompt(self):
        """Verify SESSION COMPLETE PROTOCOL appears before skill content (early visibility)."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Find positions of key sections
        protocol_pos = prompt.find("SESSION COMPLETE PROTOCOL")
        skill_pos = prompt.find("## SKILL GUIDANCE")

        assert protocol_pos > 0, "SESSION COMPLETE PROTOCOL should be in prompt"
        assert skill_pos > 0, "SKILL GUIDANCE should be in prompt"

        # Protocol should appear BEFORE skill guidance (early in prompt)
        assert protocol_pos < skill_pos, (
            f"SESSION COMPLETE PROTOCOL (pos {protocol_pos}) should appear "
            f"before SKILL GUIDANCE (pos {skill_pos}) for early visibility"
        )

    def test_completion_protocol_warns_about_consequences(self):
        """Verify completion protocol explains consequences of not following it."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should warn agents about consequences
        assert "Work is NOT complete" in prompt or "cannot close" in prompt.lower(), \
            "Completion protocol should warn about consequences of not completing"


class TestMetaOrchestrationBoilerplateConditional:
    """
    Validates that meta-orchestration boilerplate is only included for meta-orchestration projects.

    The ~45 lines of META-ORCHESTRATION TEMPLATE SYSTEM warnings should only appear
    for projects that deal with orchestration templates (orch-cli, orch-knowledge).
    Other projects like price-watch should not see this irrelevant content.

    Related: orch-cli-1b5
    """

    def test_meta_orchestration_boilerplate_included_for_orch_cli(self):
        """Verify meta-orchestration boilerplate IS included for orch-cli project."""
        config = SpawnConfig(
            task="Test task",
            project="orch-cli",
            project_dir=Path("/Users/dylan/Documents/personal/orch-cli"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Meta-orchestration boilerplate SHOULD be present for orch-cli
        assert "META-ORCHESTRATION TEMPLATE SYSTEM" in prompt, (
            "Meta-orchestration boilerplate should be included for orch-cli projects"
        )

    def test_meta_orchestration_boilerplate_included_for_orch_knowledge(self):
        """Verify meta-orchestration boilerplate IS included for orch-knowledge project."""
        config = SpawnConfig(
            task="Test task",
            project="orch-knowledge",
            project_dir=Path("/Users/dylan/orch-knowledge"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Meta-orchestration boilerplate SHOULD be present for orch-knowledge
        assert "META-ORCHESTRATION TEMPLATE SYSTEM" in prompt, (
            "Meta-orchestration boilerplate should be included for orch-knowledge projects"
        )

    def test_meta_orchestration_boilerplate_excluded_for_other_projects(self):
        """Verify meta-orchestration boilerplate is NOT included for non-meta projects."""
        config = SpawnConfig(
            task="Test task",
            project="price-watch",
            project_dir=Path("/Users/dylan/Documents/personal/price-watch"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Meta-orchestration boilerplate should NOT be present for price-watch
        assert "META-ORCHESTRATION TEMPLATE SYSTEM" not in prompt, (
            "Meta-orchestration boilerplate should NOT be included for non-meta projects.\n"
            "This 45-line section about template systems is irrelevant for projects\n"
            "like price-watch that never edit orchestration templates.\n"
            "Reference: orch-cli-1b5"
        )

    def test_meta_orchestration_boilerplate_excluded_for_generic_project(self):
        """Verify meta-orchestration boilerplate is NOT included for generic projects."""
        config = SpawnConfig(
            task="Test task",
            project="my-app",
            project_dir=Path("/home/user/projects/my-app"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Meta-orchestration boilerplate should NOT be present for generic projects
        assert "META-ORCHESTRATION TEMPLATE SYSTEM" not in prompt, (
            "Meta-orchestration boilerplate should NOT be included for generic projects.\n"
            "Reference: orch-cli-1b5"
        )


class TestSpawnPromptNoUnfilledPlaceholders:
    """
    Validates that spawn prompts do not contain unfilled placeholder text.

    Placeholder text like "[Agent to define based on task]" or "previous-agent/WORKSPACE.md"
    confuses workers. When no explicit value is provided, these sections should be omitted.
    Related: orch-cli-tmb
    """

    def test_spawn_prompt_does_not_include_agent_to_define_placeholder(self):
        """Verify spawn prompts do NOT include '[Agent to define based on task]' placeholder."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # This placeholder should NOT appear - it confuses workers
        assert "[Agent to define based on task]" not in prompt, (
            "Spawn prompt should not contain '[Agent to define based on task]' placeholder.\n"
            "When scope is not provided, omit the SCOPE section entirely.\n"
            "Reference: orch-cli-tmb"
        )

    def test_spawn_prompt_does_not_include_previous_agent_placeholder(self):
        """Verify spawn prompts do NOT include placeholder prior work paths."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # These placeholder paths should NOT appear - they don't exist
        placeholder_paths = [
            "previous-agent/WORKSPACE.md",
            "[OPTIONAL] Context from Prior Work",
            "YYYY-MM-DD-topic.md (where {type}",
        ]

        found_placeholders = []
        for placeholder in placeholder_paths:
            if placeholder in prompt:
                found_placeholders.append(placeholder)

        assert not found_placeholders, (
            f"Spawn prompt contains placeholder prior work text:\n"
            f"{chr(10).join('- ' + p for p in found_placeholders)}\n\n"
            "When no prior work reference is provided, omit this section entirely.\n"
            "Reference: orch-cli-tmb"
        )

    def test_fallback_template_does_not_include_agent_to_define_placeholder(self):
        """Verify fallback template does not contain '[Agent to define based on task]' placeholder."""
        from orch.spawn_prompt import fallback_template

        template = fallback_template()

        assert "[Agent to define based on task]" not in template, (
            "Fallback template should not contain '[Agent to define based on task]' placeholder.\n"
            "When scope is not provided, omit the SCOPE section entirely.\n"
            "Reference: orch-cli-tmb"
        )


class TestSpawnPromptInvestigationPathReporting:
    """
    Validates that spawn prompts instruct agents to report investigation file path.

    Agents must capture the actual path from `kb create` and report it via beads comment
    so orch complete can update the registry with the correct path.
    Related: orch-cli-57n
    """

    def test_spawn_prompt_includes_investigation_path_reporting_instruction(self):
        """Verify spawn prompts include instruction to report investigation_path via beads."""
        config = SpawnConfig(
            task="Test investigation task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="investigation",
            beads_id="test-123",
            beads_only=False,  # Investigation skills use investigation file, not beads-only
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should include instruction to report investigation_path via beads comment
        assert "investigation_path:" in prompt, (
            "Spawn prompt should include instruction to report investigation_path via beads comment.\n"
            "This allows orch complete to extract the actual file path.\n"
            "Reference: orch-cli-57n"
        )

    def test_spawn_prompt_includes_bd_comment_example_for_path(self):
        """Verify spawn prompts include example bd comment with investigation_path."""
        config = SpawnConfig(
            task="Test investigation task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="investigation",
            beads_id="test-123",
            beads_only=False,  # Investigation skills use investigation file, not beads-only
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Should show example of how to report path via bd comment
        assert "bd comment" in prompt and "investigation_path" in prompt, (
            "Spawn prompt should include example: bd comment <id> 'investigation_path: /path/to/file.md'\n"
            "Reference: orch-cli-57n"
        )

    def test_spawn_prompt_investigation_path_instruction_only_for_investigation_skills(self):
        """Verify investigation_path instruction only appears for investigation-type skills."""
        # Non-investigation skill should NOT have the instruction
        config_feature = SpawnConfig(
            task="Build a feature",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            beads_only=True,  # feature-impl uses beads-only coordination
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config_feature)

        # feature-impl should NOT have investigation_path instruction
        # (feature-impl uses beads_only=True path, not investigation path)
        # The kb create instruction is only for investigation skills
        assert "Run `kb create investigation" not in prompt or "investigation_path" not in prompt, (
            "Non-investigation skills should not have kb create investigation instructions.\n"
            "Reference: orch-cli-57n"
        )


class TestSpawnPromptAgentMailRemoval:
    """
    Validates that Agent Mail coordination section is NEVER included in spawn prompts.

    Agent Mail is no longer actively used and adds ~30 lines of dead weight to spawn context.
    All spawn prompts should exclude Agent Mail regardless of scope or flags.
    Related: orch-cli-pz2
    """

    def test_agent_mail_never_included_by_default(self):
        """Verify Agent Mail section is NEVER included by default."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES,
        )

        prompt = build_spawn_prompt(config)

        # Agent Mail section should NOT appear
        assert "AGENT MAIL COORDINATION" not in prompt, \
            "Agent Mail section should not appear (no longer used)"
        assert "mcp__agent-mail__register_agent" not in prompt, \
            "Agent Mail registration instructions should not appear"
        assert "mcp__agent-mail__fetch_inbox" not in prompt, \
            "Agent Mail inbox check instructions should not appear"
        assert "mcp__agent-mail__send_message" not in prompt, \
            "Agent Mail send message instructions should not appear"

    def test_agent_mail_not_included_even_with_explicit_flag(self):
        """Verify Agent Mail section NOT included even when include_agent_mail=True."""
        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES,
            include_agent_mail=True,  # Flag should be ignored
        )

        prompt = build_spawn_prompt(config)

        # Agent Mail should NOT appear even with flag
        assert "AGENT MAIL COORDINATION" not in prompt, \
            "Agent Mail should not appear (no longer used, even with flag)"

    def test_agent_mail_not_included_for_medium_scope(self):
        """Verify Agent Mail section NOT included for Medium scope (3+ phases)."""
        config = SpawnConfig(
            task="Implement authentication flow",
            project="test-project",
            project_dir=Path("/test/project"),
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES,
            phases="investigation,design,implementation,validation",
        )

        prompt = build_spawn_prompt(config)

        # Agent Mail section should NOT appear even for Medium scope
        assert "AGENT MAIL COORDINATION" not in prompt, \
            "Agent Mail should not appear (no longer used, regardless of scope)"


class TestLoadKbContext:
    """
    Tests for load_kb_context() function which surfaces relevant investigations
    and decisions from kb for spawn prompt enrichment.

    Related: orch-cli-1u8
    """

    def test_load_kb_context_returns_none_when_no_kb_dir(self, tmp_path):
        """Verify load_kb_context returns None when .kb directory doesn't exist."""
        from orch.spawn_prompt import load_kb_context

        # No .kb directory
        result = load_kb_context("test task", tmp_path)
        assert result is None

    def test_load_kb_context_returns_none_for_empty_task(self, tmp_path):
        """Verify load_kb_context returns None for empty task description."""
        from orch.spawn_prompt import load_kb_context

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        result = load_kb_context("", tmp_path)
        assert result is None

    def test_load_kb_context_returns_none_when_no_matches(self, tmp_path, mocker):
        """Verify load_kb_context returns None when kb search returns no results."""
        from orch.spawn_prompt import load_kb_context

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # Mock subprocess to return empty results
        mock_run = mocker.patch('orch.spawn_prompt.subprocess.run')
        mock_run.return_value = mocker.Mock(
            returncode=0,
            stdout='[]',
            stderr=''
        )

        result = load_kb_context("test task with keywords", tmp_path)
        assert result is None

    def test_load_kb_context_formats_results_correctly(self, tmp_path, mocker):
        """Verify load_kb_context formats kb search results into markdown."""
        from orch.spawn_prompt import load_kb_context
        import json

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # Mock subprocess to return search results
        mock_results = [
            {
                "Name": "2025-12-01-spawn-investigation.md",
                "Path": f"{tmp_path}/.kb/investigations/2025-12-01-spawn-investigation.md",
                "Title": "Spawn System Investigation",
                "Type": "investigations",
                "Project": "",
                "Matches": [
                    "42: The spawn system uses templates for prompts",
                    "55: Keywords are extracted from the task description"
                ]
            }
        ]
        mock_run = mocker.patch('orch.spawn_prompt.subprocess.run')
        mock_run.return_value = mocker.Mock(
            returncode=0,
            stdout=json.dumps(mock_results),
            stderr=''
        )

        result = load_kb_context("spawn template keywords", tmp_path)

        # Should include section header
        assert "## PRIOR INVESTIGATIONS (from kb)" in result
        assert "Relevant investigations and decisions discovered" in result

        # Should include result title
        assert "### Spawn System Investigation" in result

        # Should include relative path
        assert ".kb/investigations/2025-12-01-spawn-investigation.md" in result

        # Should include type
        assert "investigations" in result

        # Should include excerpts (cleaned of line numbers)
        assert "The spawn system uses templates for prompts" in result
        assert "Keywords are extracted from the task description" in result

    def test_load_kb_context_limits_to_5_results(self, tmp_path, mocker):
        """Verify load_kb_context limits output to 5 results to avoid context bloat."""
        from orch.spawn_prompt import load_kb_context
        import json

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # Mock 10 results
        mock_results = [
            {
                "Name": f"result-{i}.md",
                "Path": f"{tmp_path}/.kb/investigations/result-{i}.md",
                "Title": f"Result {i}",
                "Type": "investigations",
                "Project": "",
                "Matches": [f"Match text for result {i}"]
            }
            for i in range(10)
        ]
        mock_run = mocker.patch('orch.spawn_prompt.subprocess.run')
        mock_run.return_value = mocker.Mock(
            returncode=0,
            stdout=json.dumps(mock_results),
            stderr=''
        )

        result = load_kb_context("test keywords", tmp_path)

        # Should only include first 5 results
        assert "### Result 0" in result
        assert "### Result 4" in result
        assert "### Result 5" not in result
        assert "### Result 9" not in result

    def test_load_kb_context_limits_excerpt_length(self, tmp_path, mocker):
        """Verify load_kb_context truncates long excerpts."""
        from orch.spawn_prompt import load_kb_context
        import json

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # Mock result with very long match
        long_text = "x" * 300
        mock_results = [
            {
                "Name": "long-result.md",
                "Path": f"{tmp_path}/.kb/investigations/long-result.md",
                "Title": "Long Result",
                "Type": "investigations",
                "Project": "",
                "Matches": [f"10: {long_text}"]
            }
        ]
        mock_run = mocker.patch('orch.spawn_prompt.subprocess.run')
        mock_run.return_value = mocker.Mock(
            returncode=0,
            stdout=json.dumps(mock_results),
            stderr=''
        )

        result = load_kb_context("test keywords", tmp_path)

        # Should truncate long excerpts with ...
        assert "..." in result
        # Should not contain full 300 character string
        assert long_text not in result

    def test_load_kb_context_tries_fewer_keywords_on_no_match(self, tmp_path, mocker):
        """Verify load_kb_context tries progressively fewer keywords."""
        from orch.spawn_prompt import load_kb_context
        import json

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # First call (5 keywords): no results
        # Second call (3 keywords): no results
        # Third call (2 keywords): results found
        call_count = [0]
        def mock_subprocess(*args, **kwargs):
            call_count[0] += 1
            mock_result = mocker.Mock()
            mock_result.returncode = 0
            mock_result.stderr = ''
            if call_count[0] < 3:
                mock_result.stdout = '[]'
            else:
                mock_result.stdout = json.dumps([{
                    "Name": "found.md",
                    "Path": f"{tmp_path}/.kb/investigations/found.md",
                    "Title": "Found Result",
                    "Type": "investigations",
                    "Project": "",
                    "Matches": ["Match found with fewer keywords"]
                }])
            return mock_result

        mocker.patch('orch.spawn_prompt.subprocess.run', side_effect=mock_subprocess)

        result = load_kb_context("one two three four five keywords", tmp_path)

        # Should have found results with fewer keywords
        assert result is not None
        assert "### Found Result" in result
        # Should have tried multiple times
        assert call_count[0] >= 3

    def test_load_kb_context_handles_subprocess_timeout(self, tmp_path, mocker):
        """Verify load_kb_context handles subprocess timeout gracefully."""
        from orch.spawn_prompt import load_kb_context
        import subprocess

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # Mock subprocess to raise timeout
        mocker.patch('orch.spawn_prompt.subprocess.run', side_effect=subprocess.TimeoutExpired('kb', 5))

        result = load_kb_context("test keywords", tmp_path)
        assert result is None

    def test_load_kb_context_handles_invalid_json(self, tmp_path, mocker):
        """Verify load_kb_context handles invalid JSON response gracefully."""
        from orch.spawn_prompt import load_kb_context

        # Create .kb directory
        (tmp_path / '.kb').mkdir()

        # Mock subprocess to return invalid JSON
        mock_run = mocker.patch('orch.spawn_prompt.subprocess.run')
        mock_run.return_value = mocker.Mock(
            returncode=0,
            stdout='not valid json {{{',
            stderr=''
        )

        result = load_kb_context("test keywords", tmp_path)
        assert result is None


class TestSpawnPromptKbContextIntegration:
    """
    Integration tests for kb context in spawn prompts.

    Verifies that load_kb_context is properly integrated into build_spawn_prompt.
    Related: orch-cli-1u8
    """

    def test_spawn_prompt_calls_load_kb_context(self, tmp_path, mocker):
        """Verify build_spawn_prompt calls load_kb_context."""
        from orch.spawn import SpawnConfig, DEFAULT_DELIVERABLES
        from orch.spawn_prompt import build_spawn_prompt

        # Create .kb directory
        kb_dir = tmp_path / '.kb'
        kb_dir.mkdir()

        # Mock load_kb_context to track if it's called
        mock_load_kb = mocker.patch('orch.spawn_prompt.load_kb_context')
        mock_load_kb.return_value = None  # No kb context

        config = SpawnConfig(
            task="Test task with keywords",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        build_spawn_prompt(config)

        # load_kb_context should have been called with task and project_dir
        mock_load_kb.assert_called_once_with("Test task with keywords", tmp_path)

    def test_spawn_prompt_includes_kb_context_when_available(self, tmp_path, mocker):
        """Verify build_spawn_prompt includes kb context in output when available."""
        from orch.spawn import SpawnConfig, DEFAULT_DELIVERABLES
        from orch.spawn_prompt import build_spawn_prompt

        # Create .kb directory
        kb_dir = tmp_path / '.kb'
        kb_dir.mkdir()

        # Mock load_kb_context to return context
        mock_load_kb = mocker.patch('orch.spawn_prompt.load_kb_context')
        mock_load_kb.return_value = """## PRIOR INVESTIGATIONS (from kb)

### Test Investigation
- **Path:** `.kb/investigations/test.md`
- **Type:** investigations
"""

        config = SpawnConfig(
            task="Test task with keywords",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # kb context should be in the prompt
        assert "## PRIOR INVESTIGATIONS (from kb)" in prompt
        assert "### Test Investigation" in prompt

    def test_spawn_prompt_kb_context_after_kn_context(self, tmp_path, mocker):
        """Verify kb context appears after kn context in spawn prompt."""
        from orch.spawn import SpawnConfig, DEFAULT_DELIVERABLES
        from orch.spawn_prompt import build_spawn_prompt

        # Create both .kn and .kb directories
        (tmp_path / '.kn').mkdir()
        (tmp_path / '.kb').mkdir()

        # Mock both context loaders
        mock_load_kn = mocker.patch('orch.spawn_prompt.load_kn_context')
        mock_load_kn.return_value = "## PRIOR KNOWLEDGE (from kn)\n\nSome kn context"

        mock_load_kb = mocker.patch('orch.spawn_prompt.load_kb_context')
        mock_load_kb.return_value = "## PRIOR INVESTIGATIONS (from kb)\n\nSome kb context"

        config = SpawnConfig(
            task="Test task",
            project="test-project",
            project_dir=tmp_path,
            workspace_name="test-workspace",
            skill_name="feature-impl",
            beads_id="test-123",
            deliverables=DEFAULT_DELIVERABLES
        )

        prompt = build_spawn_prompt(config)

        # Both contexts should be present
        assert "PRIOR KNOWLEDGE (from kn)" in prompt
        assert "PRIOR INVESTIGATIONS (from kb)" in prompt

        # kb context should appear after kn context
        kn_pos = prompt.find("PRIOR KNOWLEDGE (from kn)")
        kb_pos = prompt.find("PRIOR INVESTIGATIONS (from kb)")
        assert kb_pos > kn_pos, "kb context should appear after kn context"
