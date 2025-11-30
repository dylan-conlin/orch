"""Orch serve command - Start web dashboard."""
import sys
from pathlib import Path
from typing import Tuple, Optional


def get_project_root() -> Path:
    """Get the meta-orchestration project root directory."""
    # Start from this file's location and go up to find project root
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / 'tools' / 'orch').exists():
            return current
        current = current.parent
    return Path.cwd()


def get_dist_path() -> Tuple[Optional[Path], Optional[str]]:
    """Get path to built frontend assets.

    Returns:
        (dist_path, error_message) - dist_path is None if not found
    """
    project_root = get_project_root()
    dist_path = project_root / 'web' / 'frontend' / 'dist'

    if not dist_path.exists():
        error = (
            "❌ Frontend assets not found.\n\n"
            "Please build the frontend first:\n"
            "  cd web/frontend\n"
            "  npm install\n"
            "  npm run build\n\n"
            f"Looking for: {dist_path}"
        )
        return None, error

    # Check for index.html
    if not (dist_path / 'index.html').exists():
        error = (
            "❌ Frontend build incomplete (missing index.html).\n\n"
            "Please rebuild the frontend:\n"
            "  cd web/frontend\n"
            "  npm run build\n\n"
            f"Looking in: {dist_path}"
        )
        return None, error

    return dist_path, None


def check_dist_exists() -> bool:
    """Check if dist directory exists.

    Returns:
        True if exists, False otherwise
    """
    dist_path, _ = get_dist_path()
    return dist_path is not None


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the dashboard server.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    # Check for built assets
    dist_path, error = get_dist_path()
    if error:
        print(error, file=sys.stderr)
        sys.exit(1)

    print(f"🚀 Starting Orch Dashboard...")
    print(f"   Frontend: {dist_path}")
    print(f"   URL: http://{host}:{port}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Add project root to sys.path to enable imports from web/ directory
    project_root = get_project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        import uvicorn
        from web.backend.main import app
        from fastapi.staticfiles import StaticFiles

        # Mount static files (Vue SPA)
        app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")

        # Start server
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped")
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}", file=sys.stderr)
        print("\nMake sure backend dependencies are installed:", file=sys.stderr)
        print("  pip install -r web/backend/requirements.txt", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)
