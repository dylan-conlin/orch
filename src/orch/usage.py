"""
Claude Max subscription usage tracking.

Provides programmatic access to Claude Max weekly usage limits using
the undocumented oauth/usage endpoint.

NOTE: This uses an undocumented API endpoint that could change without notice.
See: https://codelynx.dev/posts/claude-code-usage-limits-statusline
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# API configuration
USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA_HEADER = "oauth-2025-04-20"
USER_AGENT = "claude-code/2.0.32"

# Keychain service name for Claude Code credentials
KEYCHAIN_SERVICE = "Claude Code-credentials"


@dataclass
class UsageLimit:
    """Represents a single usage limit (5-hour or 7-day)."""
    utilization: float  # 0-100 percentage
    resets_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional['UsageLimit']:
        """Parse a usage limit from API response data."""
        if data is None:
            return None
        
        resets_at = None
        if data.get('resets_at'):
            try:
                resets_at = datetime.fromisoformat(data['resets_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                pass
        
        return cls(
            utilization=float(data.get('utilization', 0)),
            resets_at=resets_at
        )
    
    @property
    def remaining(self) -> float:
        """Return remaining usage (100 - utilization)."""
        return 100.0 - self.utilization
    
    def time_until_reset(self) -> Optional[str]:
        """Return human-readable time until reset."""
        if not self.resets_at:
            return None
        
        now = datetime.now(timezone.utc)
        if self.resets_at <= now:
            return "now"
        
        delta = self.resets_at - now
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        if delta.days > 0:
            return f"{delta.days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


@dataclass
class UsageInfo:
    """Complete usage information from the API."""
    five_hour: Optional[UsageLimit]
    seven_day: Optional[UsageLimit]
    seven_day_opus: Optional[UsageLimit]
    seven_day_oauth_apps: Optional[UsageLimit]
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UsageInfo':
        """Parse usage info from API response."""
        return cls(
            five_hour=UsageLimit.from_dict(data.get('five_hour')),
            seven_day=UsageLimit.from_dict(data.get('seven_day')),
            seven_day_opus=UsageLimit.from_dict(data.get('seven_day_opus')),
            seven_day_oauth_apps=UsageLimit.from_dict(data.get('seven_day_oauth_apps'))
        )
    
    @classmethod
    def from_error(cls, error: str) -> 'UsageInfo':
        """Create an error response."""
        return cls(
            five_hour=None,
            seven_day=None,
            seven_day_opus=None,
            seven_day_oauth_apps=None,
            error=error
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        def limit_to_dict(limit: Optional[UsageLimit]) -> Optional[dict]:
            if limit is None:
                return None
            return {
                'utilization': limit.utilization,
                'remaining': limit.remaining,
                'resets_at': limit.resets_at.isoformat() if limit.resets_at else None,
                'time_until_reset': limit.time_until_reset()
            }
        
        result = {
            'five_hour': limit_to_dict(self.five_hour),
            'seven_day': limit_to_dict(self.seven_day),
            'seven_day_opus': limit_to_dict(self.seven_day_opus),
            'seven_day_oauth_apps': limit_to_dict(self.seven_day_oauth_apps)
        }
        
        if self.error:
            result['error'] = self.error
        
        return result


class OAuthTokenError(Exception):
    """Raised when OAuth token cannot be retrieved."""
    pass


class UsageAPIError(Exception):
    """Raised when the usage API call fails."""
    pass


def get_oauth_token_from_keychain() -> str:
    """
    Extract OAuth access token from macOS Keychain.
    
    Uses the 'security' command to access Claude Code credentials.
    
    Returns:
        OAuth access token string
        
    Raises:
        OAuthTokenError: If token cannot be retrieved
    """
    if sys.platform != 'darwin':
        raise OAuthTokenError(
            f"Keychain access only supported on macOS (current platform: {sys.platform})"
        )
    
    try:
        # Get credentials JSON from keychain
        result = subprocess.run(
            ['security', 'find-generic-password', '-s', KEYCHAIN_SERVICE, '-w'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise OAuthTokenError(
                f"Could not find Claude Code credentials in keychain. "
                f"Make sure Claude Code is installed and you're logged in with a Max subscription."
            )
        
        # Parse JSON and extract token
        credentials = json.loads(result.stdout.strip())
        
        # Navigate to claudeAiOauth.accessToken
        oauth_data = credentials.get('claudeAiOauth', {})
        access_token = oauth_data.get('accessToken')
        
        if not access_token:
            raise OAuthTokenError(
                "No access token found in Claude Code credentials. "
                "Make sure you're logged in with your Claude Max account."
            )
        
        return access_token
        
    except subprocess.TimeoutExpired:
        raise OAuthTokenError("Timeout accessing keychain")
    except json.JSONDecodeError as e:
        raise OAuthTokenError(f"Failed to parse keychain credentials: {e}")
    except FileNotFoundError:
        raise OAuthTokenError("'security' command not found (not running on macOS?)")


def get_oauth_token_from_file() -> str:
    """
    Extract OAuth access token from OpenCode auth file.
    
    Fallback for when keychain access doesn't work or on Linux.
    
    Returns:
        OAuth access token string
        
    Raises:
        OAuthTokenError: If token cannot be retrieved
    """
    auth_file = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    
    if not auth_file.exists():
        raise OAuthTokenError(
            f"OpenCode auth file not found: {auth_file}\n"
            "Try running OpenCode and authenticating first, or use macOS keychain."
        )
    
    try:
        with open(auth_file) as f:
            data = json.load(f)
        
        if "anthropic" not in data:
            raise OAuthTokenError("No Anthropic tokens found in auth file")
        
        access_token = data["anthropic"].get("access")
        if not access_token:
            raise OAuthTokenError("No access token found in OpenCode auth file")
        
        return access_token
        
    except json.JSONDecodeError as e:
        raise OAuthTokenError(f"Failed to parse auth file: {e}")


def get_oauth_token() -> str:
    """
    Get OAuth token from available sources.
    
    Tries keychain first (macOS), then falls back to OpenCode auth file.
    
    Returns:
        OAuth access token string
        
    Raises:
        OAuthTokenError: If token cannot be retrieved from any source
    """
    errors = []
    
    # Try keychain first (macOS)
    if sys.platform == 'darwin':
        try:
            return get_oauth_token_from_keychain()
        except OAuthTokenError as e:
            errors.append(f"Keychain: {e}")
    
    # Try OpenCode auth file
    try:
        return get_oauth_token_from_file()
    except OAuthTokenError as e:
        errors.append(f"OpenCode: {e}")
    
    # All sources failed
    raise OAuthTokenError(
        "Could not retrieve OAuth token from any source:\n" +
        "\n".join(f"  - {e}" for e in errors)
    )


def fetch_usage() -> UsageInfo:
    """
    Fetch Claude Max usage information from the API.
    
    Returns:
        UsageInfo with current usage data
        
    Raises:
        UsageAPIError: If the API call fails
    """
    try:
        import httpx
    except ImportError:
        raise UsageAPIError(
            "httpx library required for usage API. Install with: pip install httpx"
        )
    
    try:
        token = get_oauth_token()
    except OAuthTokenError as e:
        return UsageInfo.from_error(str(e))
    
    try:
        response = httpx.get(
            USAGE_ENDPOINT,
            headers={
                'Authorization': f'Bearer {token}',
                'anthropic-beta': OAUTH_BETA_HEADER,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': USER_AGENT
            },
            timeout=30.0
        )
        
        if response.status_code == 401:
            return UsageInfo.from_error(
                "Authentication failed (401). OAuth token may be expired. "
                "Try restarting Claude Code to refresh credentials."
            )
        elif response.status_code == 403:
            return UsageInfo.from_error(
                "Access forbidden (403). This feature may require a Max subscription."
            )
        elif response.status_code != 200:
            return UsageInfo.from_error(
                f"API returned status {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        return UsageInfo.from_dict(data)
        
    except httpx.TimeoutException:
        return UsageInfo.from_error("Request timed out")
    except httpx.RequestError as e:
        return UsageInfo.from_error(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        return UsageInfo.from_error(f"Invalid JSON response: {e}")


def format_usage_display(info: UsageInfo) -> str:
    """
    Format usage info for terminal display.
    
    Returns:
        Formatted string for display
    """
    if info.error:
        return f"❌ Error: {info.error}"
    
    lines = []
    lines.append("📊 Claude Max Usage")
    lines.append("")
    
    def format_limit(name: str, limit: Optional[UsageLimit], warning_threshold: float = 80.0) -> list[str]:
        """Format a single usage limit."""
        if limit is None:
            return [f"   {name}: N/A"]
        
        # Choose emoji based on usage level
        if limit.utilization >= 95:
            emoji = "🔴"
        elif limit.utilization >= warning_threshold:
            emoji = "🟡"
        else:
            emoji = "🟢"
        
        result = [f"   {emoji} {name}: {limit.utilization:.1f}% used ({limit.remaining:.1f}% remaining)"]
        
        if limit.resets_at:
            reset_str = limit.time_until_reset()
            result.append(f"      Resets in: {reset_str}")
        
        return result
    
    lines.extend(format_limit("5-Hour Session", info.five_hour))
    lines.append("")
    lines.extend(format_limit("Weekly Limit", info.seven_day))
    
    if info.seven_day_opus and info.seven_day_opus.utilization > 0:
        lines.append("")
        lines.extend(format_limit("Weekly Opus", info.seven_day_opus))
    
    return "\n".join(lines)


def get_usage_summary() -> tuple[str, bool]:
    """
    Get a brief one-line usage summary suitable for SessionStart hooks.
    
    Returns:
        Tuple of (summary_string, is_warning)
        is_warning is True if usage is above 80%
    """
    info = fetch_usage()
    
    if info.error:
        return f"❌ Usage check failed: {info.error[:50]}...", True
    
    if info.seven_day is None:
        return "📊 Usage: N/A", False
    
    usage = info.seven_day.utilization
    remaining = info.seven_day.remaining
    
    if usage >= 95:
        emoji = "🔴"
        is_warning = True
    elif usage >= 80:
        emoji = "🟡"
        is_warning = True
    else:
        emoji = "🟢"
        is_warning = False
    
    reset_str = ""
    if info.seven_day.resets_at:
        reset_str = f" (resets in {info.seven_day.time_until_reset()})"
    
    return f"{emoji} Weekly usage: {usage:.0f}% used, {remaining:.0f}% remaining{reset_str}", is_warning
