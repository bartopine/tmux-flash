"""Tests for PopupUI module."""

import subprocess
from unittest.mock import MagicMock, patch

from src.config import FlashCopyConfig
from src.popup_ui import PopupUI
from src.search_interface import SearchInterface


class TestPopupUIErrorHandling:
    """Test error handling paths in PopupUI."""

    @patch("src.popup_ui.subprocess.run")
    @patch("src.popup_ui.TmuxPaneUtils.get_pane_dimensions")
    @patch("src.popup_ui.DebugLogger.get_instance")
    def test_popup_dimensions_fallback_on_none(
        self, mock_get_instance, mock_get_dims, mock_subprocess
    ):
        """Test fallback to tmux window dimensions when pane dimensions unavailable."""
        mock_logger = MagicMock()
        mock_logger.log_file = ""
        mock_get_instance.return_value = mock_logger

        # Return None to trigger fallback
        mock_get_dims.return_value = None

        # Mock subprocess.run to handle different commands
        def subprocess_side_effect(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "display-message" in cmd:
                result.stdout = "200,50"
            elif "show-buffer" in cmd:
                result.stdout = "3:7"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = subprocess_side_effect

        config = FlashCopyConfig()
        search_interface = MagicMock(spec=SearchInterface)
        search_interface.reverse_search = True
        search_interface.word_separators = ""
        search_interface.case_sensitive = False

        popup_ui = PopupUI(
            pane_content="test content",
            search_interface=search_interface,
            pane_id="test_pane",
            config=config,
        )

        popup_ui._launch_popup()

        # Verify subprocess was called for tmux query
        assert mock_subprocess.called
        first_call = mock_subprocess.call_args_list[0][0][0]
        assert "display-message" in first_call

    @patch("src.popup_ui.subprocess.run")
    @patch("src.popup_ui.TmuxPaneUtils.get_pane_dimensions")
    @patch("src.popup_ui.DebugLogger.get_instance")
    def test_popup_dimensions_fallback_on_subprocess_error(
        self, mock_get_instance, mock_get_dims, mock_subprocess
    ):
        """Test fallback to hardcoded dimensions on subprocess error."""
        mock_logger = MagicMock()
        mock_logger.log_file = ""
        mock_get_instance.return_value = mock_logger

        mock_get_dims.return_value = None

        # Mock subprocess to raise error on first call (display-message), succeed on others
        call_count = [0]

        def subprocess_side_effect(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1 and "display-message" in cmd:
                raise subprocess.CalledProcessError(1, "tmux")
            result = MagicMock()
            result.returncode = 0
            if "show-buffer" in cmd:
                result.stdout = "3:7"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = subprocess_side_effect

        config = FlashCopyConfig()
        search_interface = MagicMock(spec=SearchInterface)
        search_interface.reverse_search = True
        search_interface.word_separators = ""
        search_interface.case_sensitive = False

        popup_ui = PopupUI(
            pane_content="test content",
            search_interface=search_interface,
            pane_id="test_pane",
            config=config,
        )

        popup_ui._launch_popup()

        # Should still call popup command with fallback dimensions
        assert mock_subprocess.call_count >= 1

    @patch("src.popup_ui.subprocess.run")
    @patch("src.popup_ui.TmuxPaneUtils.get_pane_dimensions")
    @patch("src.popup_ui.TmuxPaneUtils.calculate_popup_position")
    @patch("src.popup_ui.DebugLogger.get_instance")
    def test_popup_buffer_read_failure(
        self, mock_get_instance, mock_calc_pos, mock_get_dims, mock_subprocess
    ):
        """Test handling of failed buffer read (CalledProcessError)."""
        mock_logger = MagicMock()
        mock_logger.enabled = True
        mock_logger.log_file = ""
        mock_get_instance.return_value = mock_logger

        mock_get_dims.return_value = {
            "pane_x": 0,
            "pane_y": 0,
            "pane_width": 100,
            "pane_height": 20,
            "terminal_width": 200,
            "terminal_height": 50,
        }

        mock_calc_pos.return_value = {
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 20,
        }

        # Mock subprocess: popup succeeds, buffer read fails
        def subprocess_side_effect(cmd, **kwargs):
            result = MagicMock()
            if "show-buffer" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            result.returncode = 0
            result.stdout = ""
            return result

        mock_subprocess.side_effect = subprocess_side_effect

        config = FlashCopyConfig()
        search_interface = MagicMock(spec=SearchInterface)
        search_interface.reverse_search = True
        search_interface.word_separators = ""
        search_interface.case_sensitive = False

        popup_ui = PopupUI(
            pane_content="test content",
            search_interface=search_interface,
            pane_id="test_pane",
            config=config,
        )

        result = popup_ui._launch_popup()

        # Should return None when buffer read fails
        assert result is None
        # Should log the failure with pane-specific buffer name
        mock_logger.log.assert_any_call(
            "Buffer read FAILED: Command '['tmux', 'show-buffer', '-b', '__tmux_flash_copy_result_test_pane__']' returned non-zero exit status 1."
        )

    @patch("src.popup_ui.subprocess.run")
    @patch("src.popup_ui.TmuxPaneUtils.get_pane_dimensions")
    @patch("src.popup_ui.TmuxPaneUtils.calculate_popup_position")
    @patch("src.popup_ui.DebugLogger.get_instance")
    def test_popup_timeout_expired(
        self, mock_get_instance, mock_calc_pos, mock_get_dims, mock_subprocess
    ):
        """Test handling of popup timeout."""
        mock_logger = MagicMock()
        mock_logger.enabled = True
        mock_logger.log_file = ""
        mock_get_instance.return_value = mock_logger

        mock_get_dims.return_value = {
            "pane_x": 0,
            "pane_y": 0,
            "pane_width": 100,
            "pane_height": 20,
            "terminal_width": 200,
            "terminal_height": 50,
        }

        mock_calc_pos.return_value = {
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 20,
        }

        # Mock subprocess to succeed for buffer operations, timeout for popup command
        def subprocess_side_effect(cmd, **kwargs):
            if "set-buffer" in cmd or "delete-buffer" in cmd:
                # Buffer operations succeed
                result = MagicMock()
                result.returncode = 0
                return result
            # Popup command times out
            raise subprocess.TimeoutExpired("tmux", 35.0)

        mock_subprocess.side_effect = subprocess_side_effect

        config = FlashCopyConfig()
        search_interface = MagicMock(spec=SearchInterface)
        search_interface.reverse_search = True
        search_interface.word_separators = ""
        search_interface.case_sensitive = False

        popup_ui = PopupUI(
            pane_content="test content",
            search_interface=search_interface,
            pane_id="test_pane",
            config=config,
        )

        result = popup_ui._launch_popup()

        # Should return None when timeout occurs
        assert result is None
        # Should log the timeout
        mock_logger.log.assert_any_call("Popup timeout expired")

    @patch("src.popup_ui.subprocess.run")
    @patch("src.popup_ui.TmuxPaneUtils.get_pane_dimensions")
    @patch("src.popup_ui.TmuxPaneUtils.calculate_popup_position")
    @patch("src.popup_ui.DebugLogger.get_instance")
    def test_popup_generic_exception(
        self, mock_get_instance, mock_calc_pos, mock_get_dims, mock_subprocess
    ):
        """Test handling of unexpected exceptions."""
        mock_logger = MagicMock()
        mock_logger.enabled = True
        mock_logger.log_file = ""
        mock_get_instance.return_value = mock_logger

        mock_get_dims.return_value = {
            "pane_x": 0,
            "pane_y": 0,
            "pane_width": 100,
            "pane_height": 20,
            "terminal_width": 200,
            "terminal_height": 50,
        }

        mock_calc_pos.return_value = {
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 20,
        }

        # Mock subprocess to succeed for buffer operations, fail for popup command
        def subprocess_side_effect(cmd, **kwargs):
            if "set-buffer" in cmd or "delete-buffer" in cmd:
                # Buffer operations succeed
                result = MagicMock()
                result.returncode = 0
                return result
            # Popup command raises generic exception
            raise RuntimeError("Unexpected error")

        mock_subprocess.side_effect = subprocess_side_effect

        config = FlashCopyConfig()
        search_interface = MagicMock(spec=SearchInterface)
        search_interface.reverse_search = True
        search_interface.word_separators = ""
        search_interface.case_sensitive = False

        popup_ui = PopupUI(
            pane_content="test content",
            search_interface=search_interface,
            pane_id="test_pane",
            config=config,
        )

        result = popup_ui._launch_popup()

        # Should return None when exception occurs
        assert result is None
        # Should log the exception
        mock_logger.log.assert_any_call("Exception in _launch_popup: Unexpected error")
