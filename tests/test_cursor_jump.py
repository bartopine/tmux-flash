"""Tests for src.cursor_jump."""

from unittest.mock import MagicMock, patch

import pytest

from src import cursor_jump


def _argv(call):
    """Extract positional args[0] (the command list) from a mock call."""
    return list(call.args[0])


class TestJumpTo:
    """Tests for cursor_jump.jump_to."""

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_to_origin_emits_copy_mode_and_anchor(self, mock_run: MagicMock):
        """At (0, 0) we enter copy-mode and anchor to top-line/start-of-line, no walking."""
        cursor_jump.jump_to("%5", 0, 0)

        argvs = [_argv(c) for c in mock_run.call_args_list]
        # Must contain: copy-mode -t %5
        assert ["tmux", "copy-mode", "-t", "%5"] in argvs
        # Must contain: send-keys -X -t %5 top-line
        assert ["tmux", "send-keys", "-X", "-t", "%5", "top-line"] in argvs
        assert ["tmux", "send-keys", "-X", "-t", "%5", "start-of-line"] in argvs
        # No cursor-down or cursor-right at origin
        for argv in argvs:
            assert "cursor-down" not in argv
            assert "cursor-right" not in argv

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_to_nonzero_emits_walk(self, mock_run: MagicMock):
        """At (3, 7) we walk down 3 and right 7."""
        cursor_jump.jump_to("%2", 3, 7)

        argvs = [_argv(c) for c in mock_run.call_args_list]
        assert ["tmux", "send-keys", "-X", "-t", "%2", "top-line"] in argvs
        # Walk down 3 rows in a single send-keys -N invocation:
        assert [
            "tmux",
            "send-keys",
            "-X",
            "-N",
            "3",
            "-t",
            "%2",
            "cursor-down",
        ] in argvs
        # Walk right 7 cols:
        assert [
            "tmux",
            "send-keys",
            "-X",
            "-N",
            "7",
            "-t",
            "%2",
            "cursor-right",
        ] in argvs

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_skips_walk_when_zero(self, mock_run: MagicMock):
        """At (0, 5) we walk right but not down. At (5, 0) the inverse."""
        cursor_jump.jump_to("%1", 0, 5)
        argvs = [_argv(c) for c in mock_run.call_args_list]
        assert not any("cursor-down" in argv for argv in argvs)
        assert ["tmux", "send-keys", "-X", "-N", "5", "-t", "%1", "cursor-right"] in argvs

        mock_run.reset_mock()
        cursor_jump.jump_to("%1", 5, 0)
        argvs = [_argv(c) for c in mock_run.call_args_list]
        assert ["tmux", "send-keys", "-X", "-N", "5", "-t", "%1", "cursor-down"] in argvs
        assert not any("cursor-right" in argv for argv in argvs)

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_rejects_negative(self, mock_run: MagicMock):
        with pytest.raises(ValueError):
            cursor_jump.jump_to("%1", -1, 0)
        with pytest.raises(ValueError):
            cursor_jump.jump_to("%1", 0, -1)
        mock_run.assert_not_called()

    @patch("src.cursor_jump.subprocess.run")
    def test_jump_call_order_is_anchor_then_walk(self, mock_run: MagicMock):
        """Order matters: copy-mode first, then top-line/start-of-line, then walk."""
        cursor_jump.jump_to("%9", 2, 3)
        argvs = [_argv(c) for c in mock_run.call_args_list]

        def index_of(argv_match):
            for i, a in enumerate(argvs):
                if a == argv_match:
                    return i
            raise AssertionError(f"Not found: {argv_match} in {argvs}")

        i_copy = index_of(["tmux", "copy-mode", "-t", "%9"])
        i_top = index_of(["tmux", "send-keys", "-X", "-t", "%9", "top-line"])
        i_sol = index_of(["tmux", "send-keys", "-X", "-t", "%9", "start-of-line"])
        i_down = index_of(["tmux", "send-keys", "-X", "-N", "2", "-t", "%9", "cursor-down"])
        i_right = index_of(["tmux", "send-keys", "-X", "-N", "3", "-t", "%9", "cursor-right"])
        assert i_copy < i_top < i_sol < i_down < i_right
