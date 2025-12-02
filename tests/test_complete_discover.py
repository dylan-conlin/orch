"""
Tests for --discover flag in orch complete command.

Following TDD workflow: RED (this file) -> GREEN (implementation) -> REFACTOR

This flag enables capturing discovered/punted work during agent completion,
creating beads issues with --discovered-from links when applicable.

Reference: .orch/investigations/systems/2025-11-29-vc-vs-orch-philosophical-comparison.md
Pattern adopted: Post-completion analysis + Discovery linking (from VC)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, call
from click.testing import CliRunner


class TestDiscoverFlagCLI:
    """Tests for --discover flag in CLI."""

    def test_complete_accepts_discover_flag(self):
        """Test that orch complete command accepts --discover flag."""
        from orch.cli import cli

        runner = CliRunner()

        # Just check the flag is recognized (help output includes it)
        result = runner.invoke(cli, ['complete', '--help'])

        assert '--discover' in result.output, \
            "Expected --discover flag to be available in orch complete"

    def test_complete_discover_flag_prompts_for_items(self):
        """Test that --discover flag prompts user for discovered work items.

        When --discover is set, after successful completion, should prompt
        for discovered/punted work items interactively.
        """
        from orch.cli import cli

        runner = CliRunner()

        with patch('orch.cli.AgentRegistry') as MockRegistry:
            mock_registry = Mock()
            mock_registry.find.return_value = {
                'id': 'test-agent',
                'workspace': '.orch/workspace/test-agent',
                'project_dir': '/tmp/test-project',
                'status': 'active'
            }
            MockRegistry.return_value = mock_registry

            # Patch at the source module where complete_agent_work is defined
            with patch('orch.complete.complete_agent_work') as mock_complete:
                mock_complete.return_value = {
                    'success': True,
                    'verified': True,
                    'errors': [],
                    'warnings': []
                }

                # Also mock subprocess to prevent actual bd calls
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = Mock(returncode=0, stdout='Created: test-123', stderr='')

                    # Simulate user entering one item then empty to finish
                    result = runner.invoke(
                        cli,
                        ['complete', 'test-agent', '--discover', '--sync'],
                        input='Add caching for API calls\n\n'  # One item, then empty
                    )

                    # Should show discovery prompt
                    assert 'discovered' in result.output.lower() or 'punted' in result.output.lower(), \
                        f"Expected discovery prompt in output, got: {result.output}"


class TestDiscoverFunctionality:
    """Tests for discover functionality in complete module."""

    def test_prompt_for_discoveries_returns_items(self):
        """Test that prompt_for_discoveries returns user-entered items."""
        from orch.complete import prompt_for_discoveries

        with patch('click.prompt') as mock_prompt:
            # Simulate user entering two items then empty to finish
            mock_prompt.side_effect = ['Fix memory leak', 'Add tests for edge case', '']

            items = prompt_for_discoveries()

            assert len(items) == 2
            assert 'Fix memory leak' in items
            assert 'Add tests for edge case' in items

    def test_create_beads_issue_calls_bd_create(self):
        """Test that create_beads_issue calls bd create subprocess."""
        from orch.complete import create_beads_issue

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='Created: orch-cli-abc',
                stderr=''
            )

            result = create_beads_issue('Add caching for API calls')

            # Should have called bd create
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == 'bd'
            assert call_args[1] == 'create'
            assert 'Add caching for API calls' in call_args

            # Should return created issue ID
            assert result is not None

    def test_create_beads_issue_with_discovered_from(self):
        """Test that create_beads_issue includes --discovered-from when parent provided."""
        from orch.complete import create_beads_issue

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='Created: orch-cli-xyz',
                stderr=''
            )

            result = create_beads_issue(
                'Add caching for API calls',
                discovered_from='orch-cli-4qg'
            )

            # Should have called bd create with --discovered-from
            call_args = mock_run.call_args[0][0]
            assert '--discovered-from' in call_args
            assert 'orch-cli-4qg' in call_args

    def test_create_beads_issue_without_parent(self):
        """Test that create_beads_issue works without --discovered-from."""
        from orch.complete import create_beads_issue

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='Created: orch-cli-123',
                stderr=''
            )

            result = create_beads_issue('Standalone discovery item')

            # Should NOT have --discovered-from flag
            call_args = mock_run.call_args[0][0]
            assert '--discovered-from' not in call_args


class TestDiscoverIntegration:
    """Integration tests for discover workflow during completion."""

    def test_discover_workflow_creates_multiple_issues(self, tmp_path):
        """Test full discover workflow creates issues for all entered items."""
        from orch.complete import process_discoveries

        items = ['Fix memory leak', 'Add caching', 'Improve error handling']

        with patch('orch.complete.create_beads_issue') as mock_create:
            mock_create.side_effect = [
                'orch-cli-a1',
                'orch-cli-a2',
                'orch-cli-a3'
            ]

            results = process_discoveries(
                items=items,
                discovered_from='orch-cli-parent'
            )

            # Should have created 3 issues
            assert mock_create.call_count == 3

            # All should have discovered-from link
            for call_obj in mock_create.call_args_list:
                assert call_obj[1].get('discovered_from') == 'orch-cli-parent'

            # Should return list of created issue IDs
            assert len(results) == 3

    def test_discover_workflow_handles_bd_failure(self):
        """Test discover workflow handles bd create failures gracefully."""
        from orch.complete import process_discoveries

        items = ['First item', 'Failing item', 'Third item']

        with patch('orch.complete.create_beads_issue') as mock_create:
            # Second call fails
            mock_create.side_effect = [
                'orch-cli-a1',
                None,  # Failure
                'orch-cli-a3'
            ]

            results = process_discoveries(items=items)

            # Should have attempted all 3
            assert mock_create.call_count == 3

            # Results is a list of dicts - extract issue_ids
            issue_ids = [r.get('issue_id') for r in results]

            # Should return successful ones and indicate failure
            assert 'orch-cli-a1' in issue_ids
            assert 'orch-cli-a3' in issue_ids
            # None represents the failure
            assert None in issue_ids

    def test_discover_extracts_parent_from_agent_beads_id(self):
        """Test that discover uses agent's beads_id as parent if available."""
        from orch.complete import get_discovery_parent_id

        # Agent with beads_id field
        agent = {
            'id': 'test-agent',
            'beads_id': 'orch-cli-4qg',
            'status': 'active'
        }

        parent_id = get_discovery_parent_id(agent)

        assert parent_id == 'orch-cli-4qg'

    def test_discover_returns_none_when_no_parent(self):
        """Test that get_discovery_parent_id returns None when agent has no beads link."""
        from orch.complete import get_discovery_parent_id

        # Agent without beads_id field
        agent = {
            'id': 'test-agent',
            'status': 'active'
        }

        parent_id = get_discovery_parent_id(agent)

        assert parent_id is None


class TestDiscoverOutput:
    """Tests for discover output and summary."""

    def test_format_discovery_summary_shows_created_issues(self):
        """Test that summary shows all created issues."""
        from orch.complete import format_discovery_summary

        results = [
            {'item': 'Fix memory leak', 'issue_id': 'orch-cli-a1'},
            {'item': 'Add caching', 'issue_id': 'orch-cli-a2'}
        ]

        summary = format_discovery_summary(results)

        assert 'orch-cli-a1' in summary
        assert 'orch-cli-a2' in summary
        assert 'Fix memory leak' in summary
        assert 'Add caching' in summary

    def test_format_discovery_summary_shows_failures(self):
        """Test that summary indicates any failures."""
        from orch.complete import format_discovery_summary

        results = [
            {'item': 'Success item', 'issue_id': 'orch-cli-a1'},
            {'item': 'Failed item', 'issue_id': None, 'error': 'bd create failed'}
        ]

        summary = format_discovery_summary(results)

        assert 'Failed item' in summary
        assert 'failed' in summary.lower() or 'error' in summary.lower()
