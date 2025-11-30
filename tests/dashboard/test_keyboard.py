"""Tests for keyboard input handling."""
import pytest
from orch.dashboard.keyboard import KeyHandler, KeyAction


def test_maps_j_to_move_down():
    """Should map 'j' key to move_down action."""
    handler = KeyHandler()
    action = handler.handle_key('j')
    assert action == KeyAction.MOVE_DOWN


def test_maps_k_to_move_up():
    """Should map 'k' key to move_up action."""
    handler = KeyHandler()
    action = handler.handle_key('k')
    assert action == KeyAction.MOVE_UP


def test_maps_enter_to_toggle():
    """Should map Enter key to toggle_expand action."""
    handler = KeyHandler()
    action = handler.handle_key('\r')  # Enter is carriage return
    assert action == KeyAction.TOGGLE_EXPAND


def test_maps_t_and_1_to_tail():
    """Should map both 't' and '1' to tail action."""
    handler = KeyHandler()
    assert handler.handle_key('t') == KeyAction.TAIL
    assert handler.handle_key('1') == KeyAction.TAIL


def test_maps_q_to_quit():
    """Should map 'q' to quit action."""
    handler = KeyHandler()
    action = handler.handle_key('q')
    assert action == KeyAction.QUIT


def test_unknown_key_returns_none():
    """Should return UNKNOWN for unmapped keys."""
    handler = KeyHandler()
    action = handler.handle_key('z')
    assert action == KeyAction.UNKNOWN
