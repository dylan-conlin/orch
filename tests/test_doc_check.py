"""
Tests for orch doc_check module.

Tests CLI documentation sync checker.
"""

import pytest
import json
import click
from pathlib import Path

from orch.doc_check import (
    extract_command_info,
    extract_cli_reference,
    format_reference_markdown,
    format_reference_json,
    load_documented_commands,
    check_doc_sync,
    generate_reference_files,
)


class TestExtractCommandInfo:
    """Tests for extract_command_info function."""

    def test_extracts_help_text(self):
        """Should extract first line of help text."""
        @click.command()
        def test_cmd():
            """This is the help text.

            More details here.
            """
            pass

        info = extract_command_info(test_cmd)
        assert info['help'] == 'This is the help text.'

    def test_extracts_options(self):
        """Should extract option information."""
        @click.command()
        @click.option('--verbose', '-v', help='Enable verbose output', is_flag=True)
        def test_cmd(verbose):
            """Test command."""
            pass

        info = extract_command_info(test_cmd)
        assert len(info['options']) == 1
        assert info['options'][0]['name'] == '--verbose'
        assert info['options'][0]['help'] == 'Enable verbose output'
        assert info['options'][0]['is_flag'] is True

    def test_extracts_arguments(self):
        """Should extract argument information."""
        @click.command()
        @click.argument('filename')
        def test_cmd(filename):
            """Test command."""
            pass

        info = extract_command_info(test_cmd)
        assert len(info['arguments']) == 1
        assert info['arguments'][0]['name'] == 'filename'

    def test_extracts_subcommands(self):
        """Should list subcommands for command groups."""
        @click.group()
        def test_group():
            """Test group."""
            pass

        @test_group.command()
        def sub1():
            """Subcommand 1."""
            pass

        @test_group.command()
        def sub2():
            """Subcommand 2."""
            pass

        info = extract_command_info(test_group)
        assert 'sub1' in info['subcommands']
        assert 'sub2' in info['subcommands']

    def test_skips_hidden_options(self):
        """Should skip hidden options."""
        @click.command()
        @click.option('--hidden', hidden=True)
        @click.option('--visible', help='Visible option')
        def test_cmd(hidden, visible):
            """Test command."""
            pass

        info = extract_command_info(test_cmd)
        option_names = [o['name'] for o in info['options']]
        assert '--hidden' not in option_names
        assert '--visible' in option_names


class TestExtractCliReference:
    """Tests for extract_cli_reference function."""

    def test_extracts_all_commands(self):
        """Should extract all commands in group."""
        @click.group()
        def cli():
            """Main group."""
            pass

        @cli.command()
        def cmd1():
            """Command 1."""
            pass

        @cli.command()
        def cmd2():
            """Command 2."""
            pass

        reference = extract_cli_reference(cli)
        assert 'cmd1' in reference
        assert 'cmd2' in reference

    def test_handles_nested_groups(self):
        """Should handle nested command groups."""
        @click.group()
        def cli():
            """Main group."""
            pass

        @cli.group()
        def sub():
            """Subgroup."""
            pass

        @sub.command()
        def nested():
            """Nested command."""
            pass

        reference = extract_cli_reference(cli)
        assert 'sub' in reference
        assert 'sub nested' in reference


class TestFormatReferenceMarkdown:
    """Tests for format_reference_markdown function."""

    def test_generates_markdown_header(self):
        """Should generate markdown header."""
        reference = {}
        result = format_reference_markdown(reference)
        assert '# orch CLI Reference' in result

    def test_formats_commands(self):
        """Should format command entries."""
        reference = {
            'test': {
                'help': 'Test command',
                'options': [{'name': '--flag', 'help': 'A flag'}],
                'arguments': [],
                'subcommands': []
            }
        }
        result = format_reference_markdown(reference)
        assert '## `orch test`' in result
        assert 'Test command' in result
        assert '--flag' in result


class TestFormatReferenceJson:
    """Tests for format_reference_json function."""

    def test_generates_valid_json(self):
        """Should generate valid JSON."""
        reference = {'cmd': {'help': 'Test', 'options': [], 'arguments': [], 'subcommands': []}}
        result = format_reference_json(reference)
        parsed = json.loads(result)
        assert 'cmd' in parsed


class TestLoadDocumentedCommands:
    """Tests for load_documented_commands function."""

    def test_returns_empty_when_file_not_exists(self, tmp_path):
        """Should return empty dict when file doesn't exist."""
        result = load_documented_commands(tmp_path / 'nonexistent.json')
        assert result == {}

    def test_loads_json_file(self, tmp_path):
        """Should load documented commands from JSON."""
        ref_file = tmp_path / 'reference.json'
        ref_file.write_text('{"cmd": {"help": "Test"}}')

        result = load_documented_commands(ref_file)
        assert 'cmd' in result

    def test_handles_invalid_json(self, tmp_path):
        """Should return empty dict for invalid JSON."""
        ref_file = tmp_path / 'reference.json'
        ref_file.write_text('not valid json')

        result = load_documented_commands(ref_file)
        assert result == {}


class TestCheckDocSync:
    """Tests for check_doc_sync function."""

    def test_detects_undocumented_commands(self, tmp_path):
        """Should detect commands not in documentation."""
        @click.group()
        def cli():
            """CLI."""
            pass

        @cli.command()
        def new_cmd():
            """New command."""
            pass

        ref_file = tmp_path / 'reference.json'
        ref_file.write_text('{}')  # Empty documentation

        is_sync, issues = check_doc_sync(cli, ref_file)
        assert not is_sync
        assert any('Undocumented commands' in i for i in issues)

    def test_detects_removed_commands(self, tmp_path):
        """Should detect commands removed from CLI."""
        @click.group()
        def cli():
            """CLI."""
            pass

        ref_file = tmp_path / 'reference.json'
        ref_file.write_text('{"old_cmd": {"help": "Old", "options": [], "arguments": [], "subcommands": []}}')

        is_sync, issues = check_doc_sync(cli, ref_file)
        assert not is_sync
        assert any('Removed commands' in i for i in issues)

    def test_returns_true_when_in_sync(self, tmp_path):
        """Should return True when CLI matches documentation."""
        @click.group()
        def cli():
            """CLI."""
            pass

        @cli.command()
        def cmd():
            """Command."""
            pass

        ref_file = tmp_path / 'reference.json'
        ref_file.write_text('{"cmd": {"help": "Command.", "options": [], "arguments": [], "subcommands": []}}')

        is_sync, issues = check_doc_sync(cli, ref_file)
        assert is_sync
        assert len(issues) == 0


class TestGenerateReferenceFiles:
    """Tests for generate_reference_files function."""

    def test_generates_json_file(self, tmp_path):
        """Should generate JSON reference file."""
        @click.group()
        def cli():
            """CLI."""
            pass

        output_dir = tmp_path / 'output'
        generated = generate_reference_files(cli, output_dir, formats=['json'])

        assert len(generated) == 1
        assert generated[0].suffix == '.json'
        assert generated[0].exists()

    def test_generates_markdown_file(self, tmp_path):
        """Should generate Markdown reference file."""
        @click.group()
        def cli():
            """CLI."""
            pass

        output_dir = tmp_path / 'output'
        generated = generate_reference_files(cli, output_dir, formats=['markdown'])

        assert len(generated) == 1
        assert generated[0].suffix == '.md'
        assert generated[0].exists()

    def test_generates_both_formats_by_default(self, tmp_path):
        """Should generate both formats when none specified."""
        @click.group()
        def cli():
            """CLI."""
            pass

        output_dir = tmp_path / 'output'
        generated = generate_reference_files(cli, output_dir)

        assert len(generated) == 2

    def test_creates_output_directory(self, tmp_path):
        """Should create output directory if it doesn't exist."""
        @click.group()
        def cli():
            """CLI."""
            pass

        output_dir = tmp_path / 'nested' / 'output'
        generate_reference_files(cli, output_dir)

        assert output_dir.exists()
