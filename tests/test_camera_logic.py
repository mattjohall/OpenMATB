"""Tests for plugins.camera - config loading and CAPcorder control payloads."""

import configparser
from unittest.mock import MagicMock, patch

from plugins.camera import Camera


def _make_camera(**overrides):
    """Create a Camera instance bypassing __init__ for pure logic tests."""
    camera = object.__new__(Camera)
    camera.alias = "camera"
    camera.available = True
    camera.stream_outlet = MagicMock()
    camera.stream_info = MagicMock()
    camera._is_recording = False
    camera.parameters = {
        "fileprefix": "openmatb_camera",
        "outputdir": "",
        "filename": "",
        "width": 320,
        "height": 240,
        "fps": 30,
        "recording": False,
        "autostart": True,
        "streamname": "CAPcorderControl_openmatb",
        "sourceid": "CAPcorder_openmatb",
    }
    camera.__dict__.update(overrides)
    return camera


class TestCameraConfig:
    def test_reads_camera_section(self):
        """INI values override plugin defaults."""
        config = configparser.ConfigParser()
        config.read_dict(
            {
                "Camera": {
                    "stream_name": "CustomControl",
                    "source_id": "CustomSource",
                    "file_prefix": "subject_cam",
                    "output_dir": "captures",
                    "width": "640",
                    "height": "480",
                    "fps": "60",
                    "autostart": "False",
                }
            }
        )

        with patch("plugins.camera.CONFIG", config):
            camera = Camera()

        assert camera.parameters["streamname"] == "CustomControl"
        assert camera.parameters["sourceid"] == "CustomSource"
        assert camera.parameters["fileprefix"] == "subject_cam"
        assert camera.parameters["outputdir"] == "captures"
        assert camera.parameters["width"] == 640
        assert camera.parameters["height"] == 480
        assert camera.parameters["fps"] == 60
        assert camera.parameters["autostart"] is False


class TestStartRecording:
    @patch("plugins.camera.get_logger")
    def test_pushes_start_payload(self, mock_get_logger, tmp_path):
        """start_recording sends a CAPcorder-compatible start payload."""
        logger = MagicMock()
        logger.session_id = 7
        logger.path = tmp_path / "2026-05-26" / "7_260526_120000.csv"
        mock_get_logger.return_value = logger

        camera = _make_camera()
        with patch("plugins.camera.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20260526_120000"
            camera.start_recording()

        pushed = camera.stream_outlet.push_sample.call_args[0][0][0]
        assert "action: start" in pushed
        assert "filename: openmatb_camera_7_20260526_120000" in pushed
        assert "width: 320" in pushed
        assert "height: 240" in pushed
        assert "fps: 30" in pushed
        assert "frame_number: 1" in pushed
        assert "output_dir:" in pushed
        assert camera.parameters["recording"] is True
        assert camera._is_recording is True

    @patch("plugins.camera.get_logger")
    def test_uses_explicit_output_dir(self, mock_get_logger, tmp_path):
        """Configured outputdir is used when provided."""
        logger = MagicMock()
        logger.session_id = 1
        logger.path = tmp_path / "session.csv"
        mock_get_logger.return_value = logger

        explicit_dir = tmp_path / "captures"
        parameters = dict(_make_camera().parameters)
        parameters["outputdir"] = str(explicit_dir)
        camera = _make_camera(parameters=parameters)
        with patch("plugins.camera.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20260526_120000"
            camera.start_recording()

        assert explicit_dir.exists()


class TestStopRecording:
    @patch("plugins.camera.get_logger")
    def test_pushes_stop_payload(self, mock_get_logger):
        """stop_recording sends a CAPcorder-compatible stop payload."""
        mock_get_logger.return_value = MagicMock()
        camera = _make_camera(_is_recording=True)
        camera.parameters["filename"] = "openmatb_camera_7_20260526_120000"

        camera.stop_recording()

        pushed = camera.stream_outlet.push_sample.call_args[0][0][0]
        assert "action: stop" in pushed
        assert "filename: openmatb_camera_7_20260526_120000" in pushed
        assert camera.parameters["recording"] is False
        assert camera._is_recording is False


class TestUpdate:
    def test_update_starts_recording_on_toggle(self):
        """A scenario parameter toggle starts recording once."""
        camera = _make_camera()
        camera.parameters["recording"] = True

        with patch("plugins.camera.AbstractPlugin.update", return_value=None):
            with patch.object(camera, "start_recording") as start_recording:
                camera.update(1.0)

        start_recording.assert_called_once_with()

    def test_update_stops_recording_on_toggle(self):
        """A scenario parameter toggle stops recording once."""
        camera = _make_camera(_is_recording=True)
        camera.parameters["recording"] = False

        with patch("plugins.camera.AbstractPlugin.update", return_value=None):
            with patch.object(camera, "stop_recording") as stop_recording:
                camera.update(1.0)

        stop_recording.assert_called_once_with()
