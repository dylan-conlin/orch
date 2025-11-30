"""Keyboard input handling for dashboard."""
from enum import Enum, auto


class KeyAction(Enum):
    """Actions triggered by keypresses."""
    MOVE_DOWN = auto()
    MOVE_UP = auto()
    JUMP_FIRST = auto()
    JUMP_LAST = auto()
    TOGGLE_EXPAND = auto()
    TAIL = auto()
    STATUS = auto()
    MESSAGE = auto()
    INFO = auto()
    STOP = auto()
    REFRESH = auto()
    FILTER = auto()
    CLEAR_FILTER = auto()
    HELP = auto()
    QUIT = auto()
    # New control plane actions
    COMPLETE = auto()       # Complete focused agent
    ACK = auto()            # Acknowledge inbox item
    RESPOND = auto()        # Respond to question (structured)
    SWITCH_PANEL = auto()   # Toggle focus between tree/inbox
    UNKNOWN = auto()


class KeyHandler:
    """Handles keyboard input and maps to actions."""

    def __init__(self):
        """Initialize key mappings."""
        self.key_map = {
            # Movement
            'j': KeyAction.MOVE_DOWN,
            '\x1b[B': KeyAction.MOVE_DOWN,  # Down arrow (ANSI escape)
            'k': KeyAction.MOVE_UP,
            '\x1b[A': KeyAction.MOVE_UP,  # Up arrow (ANSI escape)
            'g': KeyAction.JUMP_FIRST,
            'G': KeyAction.JUMP_LAST,

            # Expand/collapse
            '\r': KeyAction.TOGGLE_EXPAND,  # Enter
            '\n': KeyAction.TOGGLE_EXPAND,  # Also Enter (some terminals)
            'o': KeyAction.TOGGLE_EXPAND,

            # Actions (both mnemonic and numbered)
            't': KeyAction.TAIL,
            '1': KeyAction.TAIL,
            's': KeyAction.STATUS,
            '2': KeyAction.STATUS,
            'm': KeyAction.MESSAGE,
            '3': KeyAction.MESSAGE,
            'i': KeyAction.INFO,
            '4': KeyAction.INFO,
            'x': KeyAction.STOP,
            '5': KeyAction.STOP,

            # Control plane actions
            'c': KeyAction.COMPLETE,
            '6': KeyAction.COMPLETE,
            'a': KeyAction.ACK,
            '7': KeyAction.ACK,
            'R': KeyAction.RESPOND,  # Shift+R for structured response
            '8': KeyAction.RESPOND,
            '\t': KeyAction.SWITCH_PANEL,  # Tab to switch panels

            # Global
            'r': KeyAction.REFRESH,
            '/': KeyAction.FILTER,
            '\x1b': KeyAction.CLEAR_FILTER,  # Esc key
            '?': KeyAction.HELP,
            'q': KeyAction.QUIT,
        }

    def handle_key(self, key: str) -> KeyAction:
        """Map keypress to action.

        Args:
            key: Raw key character or escape sequence

        Returns:
            KeyAction enum value
        """
        return self.key_map.get(key, KeyAction.UNKNOWN)
