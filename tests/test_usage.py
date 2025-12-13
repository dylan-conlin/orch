"""Tests for orch usage command."""

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from orch.cli import cli
from orch.usage import (
    UsageLimit,
    UsageInfo,
    OAuthTokenError,
    get_oauth_token_from_keychain,
    get_oauth_token_from_file,
    get_oauth_token,
    fetch_usage,
    format_usage_display,
    get_usage_summary,
)


class TestUsageLimit:
    """Tests for UsageLimit dataclass."""

    def test_from_dict_basic(self):
        """Test basic UsageLimit creation from dict."""
        data = {'utilization': 45.5, 'resets_at': '2025-12-15T12:00:00+00:00'}
        limit = UsageLimit.from_dict(data)
        
        assert limit.utilization == 45.5
        assert limit.remaining == 54.5
        assert limit.resets_at is not None

    def test_from_dict_null(self):
        """Test UsageLimit.from_dict with None."""
        limit = UsageLimit.from_dict(None)
        assert limit is None

    def test_from_dict_no_reset(self):
        """Test UsageLimit without reset time."""
        data = {'utilization': 30.0, 'resets_at': None}
        limit = UsageLimit.from_dict(data)
        
        assert limit.utilization == 30.0
        assert limit.resets_at is None
        assert limit.time_until_reset() is None

    def test_remaining_calculation(self):
        """Test remaining percentage calculation."""
        limit = UsageLimit(utilization=75.0)
        assert limit.remaining == 25.0

    def test_time_until_reset_days(self):
        """Test time_until_reset with days remaining."""
        future = datetime.now(timezone.utc) + timedelta(days=2, hours=5)
        limit = UsageLimit(utilization=50.0, resets_at=future)
        
        result = limit.time_until_reset()
        assert result.startswith('2d ')

    def test_time_until_reset_hours(self):
        """Test time_until_reset with hours remaining."""
        future = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
        limit = UsageLimit(utilization=50.0, resets_at=future)
        
        result = limit.time_until_reset()
        assert 'h' in result

    def test_time_until_reset_minutes(self):
        """Test time_until_reset with only minutes remaining."""
        future = datetime.now(timezone.utc) + timedelta(minutes=45)
        limit = UsageLimit(utilization=50.0, resets_at=future)
        
        result = limit.time_until_reset()
        assert 'm' in result
        assert 'h' not in result

    def test_time_until_reset_past(self):
        """Test time_until_reset when reset time has passed."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        limit = UsageLimit(utilization=50.0, resets_at=past)
        
        result = limit.time_until_reset()
        assert result == 'now'


class TestUsageInfo:
    """Tests for UsageInfo dataclass."""

    def test_from_dict_full_response(self):
        """Test parsing a full API response."""
        data = {
            'five_hour': {'utilization': 10.0, 'resets_at': '2025-12-15T12:00:00+00:00'},
            'seven_day': {'utilization': 35.0, 'resets_at': '2025-12-20T00:00:00+00:00'},
            'seven_day_opus': {'utilization': 5.0, 'resets_at': None},
            'seven_day_oauth_apps': None,
        }
        info = UsageInfo.from_dict(data)
        
        assert info.five_hour is not None
        assert info.five_hour.utilization == 10.0
        assert info.seven_day is not None
        assert info.seven_day.utilization == 35.0
        assert info.seven_day_opus is not None
        assert info.seven_day_oauth_apps is None
        assert info.error is None

    def test_from_error(self):
        """Test creating error response."""
        info = UsageInfo.from_error("Token expired")
        
        assert info.five_hour is None
        assert info.seven_day is None
        assert info.error == "Token expired"

    def test_to_dict(self):
        """Test converting to dictionary."""
        limit = UsageLimit(utilization=50.0)
        info = UsageInfo(
            five_hour=limit,
            seven_day=None,
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        result = info.to_dict()
        
        assert 'five_hour' in result
        assert result['five_hour']['utilization'] == 50.0
        assert result['five_hour']['remaining'] == 50.0
        assert result['seven_day'] is None

    def test_to_dict_with_error(self):
        """Test to_dict includes error."""
        info = UsageInfo.from_error("API failed")
        result = info.to_dict()
        
        assert result['error'] == "API failed"


class TestOAuthTokenExtraction:
    """Tests for OAuth token extraction functions."""

    @patch('orch.usage.sys')
    def test_keychain_not_macos(self, mock_sys):
        """Test keychain access fails on non-macOS."""
        mock_sys.platform = 'linux'
        
        with pytest.raises(OAuthTokenError) as exc:
            get_oauth_token_from_keychain()
        
        assert 'macOS' in str(exc.value)

    @patch('orch.usage.sys')
    @patch('orch.usage.subprocess.run')
    def test_keychain_success(self, mock_run, mock_sys):
        """Test successful keychain access."""
        mock_sys.platform = 'darwin'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"claudeAiOauth": {"accessToken": "test-token-123"}}'
        )
        
        token = get_oauth_token_from_keychain()
        assert token == "test-token-123"

    @patch('orch.usage.sys')
    @patch('orch.usage.subprocess.run')
    def test_keychain_not_found(self, mock_run, mock_sys):
        """Test keychain access when credentials not found."""
        mock_sys.platform = 'darwin'
        mock_run.return_value = MagicMock(returncode=1, stderr='not found')
        
        with pytest.raises(OAuthTokenError) as exc:
            get_oauth_token_from_keychain()
        
        assert 'Could not find' in str(exc.value)

    @patch('orch.usage.sys')
    @patch('orch.usage.subprocess.run')
    def test_keychain_no_token(self, mock_run, mock_sys):
        """Test keychain access when token missing from JSON."""
        mock_sys.platform = 'darwin'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"claudeAiOauth": {}}'
        )
        
        with pytest.raises(OAuthTokenError) as exc:
            get_oauth_token_from_keychain()
        
        assert 'No access token' in str(exc.value)

    def test_file_not_found(self, tmp_path, monkeypatch):
        """Test auth file not found."""
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)
        
        with pytest.raises(OAuthTokenError) as exc:
            get_oauth_token_from_file()
        
        assert 'not found' in str(exc.value)

    def test_file_success(self, tmp_path, monkeypatch):
        """Test successful auth file access."""
        auth_dir = tmp_path / ".local" / "share" / "opencode"
        auth_dir.mkdir(parents=True)
        auth_file = auth_dir / "auth.json"
        auth_file.write_text('{"anthropic": {"access": "file-token-456"}}')
        
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)
        
        token = get_oauth_token_from_file()
        assert token == "file-token-456"

    def test_file_no_anthropic(self, tmp_path, monkeypatch):
        """Test auth file without anthropic section."""
        auth_dir = tmp_path / ".local" / "share" / "opencode"
        auth_dir.mkdir(parents=True)
        auth_file = auth_dir / "auth.json"
        auth_file.write_text('{"other": {}}')
        
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)
        
        with pytest.raises(OAuthTokenError) as exc:
            get_oauth_token_from_file()
        
        assert 'No Anthropic tokens' in str(exc.value)


class TestGetOAuthToken:
    """Tests for combined get_oauth_token function."""

    @patch('orch.usage.sys')
    @patch('orch.usage.get_oauth_token_from_keychain')
    def test_keychain_preferred_on_macos(self, mock_keychain, mock_sys):
        """Test keychain is tried first on macOS."""
        mock_sys.platform = 'darwin'
        mock_keychain.return_value = "keychain-token"
        
        token = get_oauth_token()
        assert token == "keychain-token"
        mock_keychain.assert_called_once()

    @patch('orch.usage.sys')
    @patch('orch.usage.get_oauth_token_from_keychain')
    @patch('orch.usage.get_oauth_token_from_file')
    def test_fallback_to_file(self, mock_file, mock_keychain, mock_sys):
        """Test fallback to file when keychain fails."""
        mock_sys.platform = 'darwin'
        mock_keychain.side_effect = OAuthTokenError("keychain failed")
        mock_file.return_value = "file-token"
        
        token = get_oauth_token()
        assert token == "file-token"

    @patch('orch.usage.sys')
    @patch('orch.usage.get_oauth_token_from_file')
    def test_file_only_on_linux(self, mock_file, mock_sys):
        """Test only file source used on Linux."""
        mock_sys.platform = 'linux'
        mock_file.return_value = "linux-token"
        
        token = get_oauth_token()
        assert token == "linux-token"

    @patch('orch.usage.sys')
    @patch('orch.usage.get_oauth_token_from_keychain')
    @patch('orch.usage.get_oauth_token_from_file')
    def test_all_sources_fail(self, mock_file, mock_keychain, mock_sys):
        """Test error when all sources fail."""
        mock_sys.platform = 'darwin'
        mock_keychain.side_effect = OAuthTokenError("keychain failed")
        mock_file.side_effect = OAuthTokenError("file failed")
        
        with pytest.raises(OAuthTokenError) as exc:
            get_oauth_token()
        
        assert 'keychain failed' in str(exc.value)
        assert 'file failed' in str(exc.value)


class TestFetchUsage:
    """Tests for fetch_usage function."""

    @patch('orch.usage.get_oauth_token')
    def test_token_error(self, mock_get_token):
        """Test handling of token retrieval error."""
        # Need to mock httpx import to avoid ImportError
        import sys
        mock_httpx = MagicMock()
        with patch.dict(sys.modules, {'httpx': mock_httpx}):
            mock_get_token.side_effect = OAuthTokenError("No token")
            
            info = fetch_usage()
            
            assert info.error is not None
            assert 'No token' in info.error

    @patch('orch.usage.get_oauth_token')
    def test_api_success(self, mock_token):
        """Test successful API response."""
        import sys
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'five_hour': {'utilization': 10.0, 'resets_at': None},
                'seven_day': {'utilization': 35.0, 'resets_at': None},
                'seven_day_opus': None,
                'seven_day_oauth_apps': None
            }
        )
        
        with patch.dict(sys.modules, {'httpx': mock_httpx}):
            mock_token.return_value = "test-token"
            
            info = fetch_usage()
            
            assert info.error is None
            assert info.five_hour.utilization == 10.0
            assert info.seven_day.utilization == 35.0

    @patch('orch.usage.get_oauth_token')
    def test_api_401(self, mock_token):
        """Test handling of 401 response."""
        import sys
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = MagicMock(status_code=401)
        
        with patch.dict(sys.modules, {'httpx': mock_httpx}):
            mock_token.return_value = "expired-token"
            
            info = fetch_usage()
            
            assert info.error is not None
            assert '401' in info.error

    @patch('orch.usage.get_oauth_token')
    def test_api_403(self, mock_token):
        """Test handling of 403 response."""
        import sys
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = MagicMock(status_code=403)
        
        with patch.dict(sys.modules, {'httpx': mock_httpx}):
            mock_token.return_value = "test-token"
            
            info = fetch_usage()
            
            assert info.error is not None
            assert '403' in info.error


class TestFormatUsageDisplay:
    """Tests for format_usage_display function."""

    def test_format_error(self):
        """Test formatting error message."""
        info = UsageInfo.from_error("Something went wrong")
        
        output = format_usage_display(info)
        
        assert '❌' in output
        assert 'Something went wrong' in output

    def test_format_success(self):
        """Test formatting successful response."""
        info = UsageInfo(
            five_hour=UsageLimit(utilization=10.0),
            seven_day=UsageLimit(utilization=35.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        output = format_usage_display(info)
        
        assert '📊' in output
        assert '10.0%' in output
        assert '35.0%' in output

    def test_format_high_usage_warning(self):
        """Test warning emoji for high usage."""
        info = UsageInfo(
            five_hour=UsageLimit(utilization=90.0),
            seven_day=UsageLimit(utilization=85.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        output = format_usage_display(info)
        
        assert '🟡' in output  # Warning level
        assert '90.0%' in output

    def test_format_critical_usage(self):
        """Test critical emoji for very high usage."""
        info = UsageInfo(
            five_hour=UsageLimit(utilization=98.0),
            seven_day=UsageLimit(utilization=35.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        output = format_usage_display(info)
        
        assert '🔴' in output  # Critical level


class TestGetUsageSummary:
    """Tests for get_usage_summary function."""

    @patch('orch.usage.fetch_usage')
    def test_summary_success(self, mock_fetch):
        """Test successful summary."""
        mock_fetch.return_value = UsageInfo(
            five_hour=UsageLimit(utilization=20.0),
            seven_day=UsageLimit(utilization=50.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        summary, is_warning = get_usage_summary()
        
        assert '🟢' in summary
        assert '50%' in summary
        assert not is_warning

    @patch('orch.usage.fetch_usage')
    def test_summary_warning(self, mock_fetch):
        """Test warning-level summary."""
        mock_fetch.return_value = UsageInfo(
            five_hour=UsageLimit(utilization=20.0),
            seven_day=UsageLimit(utilization=85.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        summary, is_warning = get_usage_summary()
        
        assert '🟡' in summary
        assert is_warning

    @patch('orch.usage.fetch_usage')
    def test_summary_error(self, mock_fetch):
        """Test error summary."""
        mock_fetch.return_value = UsageInfo.from_error("Token expired")
        
        summary, is_warning = get_usage_summary()
        
        assert '❌' in summary
        assert is_warning


class TestUsageCLI:
    """Tests for orch usage CLI command."""

    def test_usage_help(self):
        """Test orch usage --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['usage', '--help'])
        
        assert result.exit_code == 0
        assert 'Claude Max' in result.output
        assert '--json' in result.output
        assert '--brief' in result.output

    @patch('orch.usage.fetch_usage')
    def test_usage_basic(self, mock_fetch):
        """Test basic usage command."""
        mock_fetch.return_value = UsageInfo(
            five_hour=UsageLimit(utilization=15.0),
            seven_day=UsageLimit(utilization=45.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        runner = CliRunner()
        result = runner.invoke(cli, ['usage'])
        
        assert result.exit_code == 0
        assert '📊' in result.output
        assert '15.0%' in result.output
        assert '45.0%' in result.output

    @patch('orch.usage.fetch_usage')
    def test_usage_json(self, mock_fetch):
        """Test usage with --json flag."""
        mock_fetch.return_value = UsageInfo(
            five_hour=UsageLimit(utilization=15.0),
            seven_day=UsageLimit(utilization=45.0),
            seven_day_opus=None,
            seven_day_oauth_apps=None
        )
        
        runner = CliRunner()
        result = runner.invoke(cli, ['usage', '--json'])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['five_hour']['utilization'] == 15.0
        assert data['seven_day']['utilization'] == 45.0

    @patch('orch.usage.get_usage_summary')
    def test_usage_brief(self, mock_summary):
        """Test usage with --brief flag."""
        mock_summary.return_value = ("🟢 Weekly usage: 45% used", False)
        
        runner = CliRunner()
        result = runner.invoke(cli, ['usage', '--brief'])
        
        assert result.exit_code == 0
        assert '🟢' in result.output
        assert '45%' in result.output

    @patch('orch.usage.fetch_usage')
    def test_usage_error_exit_code(self, mock_fetch):
        """Test exit code 1 on error."""
        mock_fetch.return_value = UsageInfo.from_error("Failed")
        
        runner = CliRunner()
        result = runner.invoke(cli, ['usage'])
        
        assert result.exit_code == 1

    @patch('orch.usage.get_usage_summary')
    def test_usage_brief_warning_exit_code(self, mock_summary):
        """Test exit code 1 on warning in brief mode."""
        mock_summary.return_value = ("🟡 High usage warning", True)
        
        runner = CliRunner()
        result = runner.invoke(cli, ['usage', '--brief'])
        
        assert result.exit_code == 1
