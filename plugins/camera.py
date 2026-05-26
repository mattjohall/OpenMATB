# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from time import sleep

from core import validation
from core.constants import CONFIG, PATHS
from core.error import get_errors
from core.logger import get_logger
from plugins.abstractplugin import AbstractPlugin

try:
    from pylsl import StreamInfo, StreamOutlet
except (ImportError, RuntimeError):
    StreamInfo = None
    StreamOutlet = None


class Camera(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "invisible", taskupdatetime: int = 10) -> None:
        super().__init__(_("Camera"), taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "recording": validation.is_boolean,
            "width": validation.is_positive_integer,
            "height": validation.is_positive_integer,
            "fps": validation.is_positive_integer,
            "filename": validation.is_string,
            "outputdir": validation.is_string,
        }

        self.available: bool = StreamInfo is not None and StreamOutlet is not None
        if not self.available:
            get_errors().add_error(_("pylsl is missing. Camera control plugin will be disabled."))

        stream_name: str = self._get_config_value("stream_name", "CAPcorderControl_openmatb")
        source_id: str = self._get_config_value("source_id", "CAPcorder_openmatb")
        file_prefix: str = self._get_config_value("file_prefix", "openmatb_camera")
        output_dir: str = self._get_config_value("output_dir", "")
        width: int = self._get_int_config_value("width", 320)
        height: int = self._get_int_config_value("height", 240)
        fps: int = self._get_int_config_value("fps", 30)
        autostart: bool = self._get_bool_config_value("autostart", True)

        self.parameters.update(
            {
                "streamname": stream_name,
                "sourceid": source_id,
                "fileprefix": file_prefix,
                "outputdir": output_dir,
                "filename": "",
                "width": width,
                "height": height,
                "fps": fps,
                "autostart": autostart,
                "recording": False,
            }
        )

        self.stream_info: Any | None = None
        self.stream_outlet: Any | None = None
        self._is_recording: bool = False

    def start(self) -> None:
        super().start()

        if not self.available:
            return

        self.stream_info = StreamInfo(
            self.parameters["streamname"],
            "videocontrol",
            1,
            0,
            "string",
            self.parameters["sourceid"],
        )
        self.stream_outlet = StreamOutlet(self.stream_info)

        if self.parameters["autostart"]:
            self.start_recording()

    def stop(self) -> None:
        if self._is_recording:
            self.stop_recording()

        self.stream_info = None
        self.stream_outlet = None
        super().stop()

    def update(self, scenario_time: float) -> None:
        super().update(scenario_time)

        if self.parameters["recording"] and not self._is_recording:
            self.start_recording()
        elif not self.parameters["recording"] and self._is_recording:
            self.stop_recording()

    def start_recording(self) -> None:
        if not self.available or self.stream_outlet is None or self._is_recording:
            return

        filename: str = self.parameters["filename"] or self._build_filename()
        output_dir: str = self._get_output_dir_payload()
        payload: dict[str, Any] = {
            "action": "start",
            "filename": filename,
            "width": self.parameters["width"],
            "height": self.parameters["height"],
            "fps": self.parameters["fps"],
            "frame_number": 1,
            "output_dir": output_dir,
        }
        sleep(0.5)
        self._push_payload(payload)
        payload: dict[str, Any] = {
            "action": "start",
            "filename": filename,
        }
        
        #self._push_payload(payload)
        self.parameters["filename"] = filename
        self.parameters["recording"] = True
        self._is_recording = True

    def stop_recording(self) -> None:
        if not self.available or self.stream_outlet is None or not self._is_recording:
            return

        self._push_payload(
            {
                "action": "stop",
                "filename": self.parameters["filename"] or self._build_filename(),
            }
        )
        self.parameters["recording"] = False
        self._is_recording = False

    def _push_payload(self, payload: dict[str, Any]) -> None:
        if self.stream_outlet is None:
            return

        message: str = "; ".join(f"{key}: {self._stringify_value(value)}" for key, value in payload.items())
        print(message)
        self.stream_outlet.push_sample([message])
        get_logger().record_state(f"{self.alias}_control", "payload", message)

    def _build_filename(self) -> str:
        prefix: str = self._safe_slug(self.parameters["fileprefix"], "openmatb_camera")
        session_id: Any = getattr(get_logger(), "session_id", "session")
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{session_id}_{timestamp}"

    def _get_output_dir_payload(self) -> str:
        raw_output_dir: str = str(self.parameters["outputdir"]).strip()
        output_path: Path
        if raw_output_dir:
            output_path = Path(raw_output_dir).expanduser()
        else:
            logger_path: Path | None = getattr(get_logger(), "path", None)
            if logger_path is not None:
                output_path = logger_path.parent / "video"
            else:
                output_path = PATHS["SESSIONS"] / "video"

        output_path.mkdir(parents=True, exist_ok=True)
        return str(output_path.resolve()).replace(":", "")

    def _get_config_value(self, key: str, default: str) -> str:
        if CONFIG.has_section("Camera") and CONFIG.has_option("Camera", key):
            return CONFIG.get("Camera", key).strip()
        return default

    def _get_int_config_value(self, key: str, default: int) -> int:
        if not CONFIG.has_section("Camera") or not CONFIG.has_option("Camera", key):
            return default

        value: str = CONFIG.get("Camera", key).strip()
        parsed, error = validation.is_positive_integer(value)
        if error is not None:
            get_errors().add_error(_("Camera config [%s] %s Using default value %s.") % (key, error, default))
            return default
        return parsed

    def _get_bool_config_value(self, key: str, default: bool) -> bool:
        if not CONFIG.has_section("Camera") or not CONFIG.has_option("Camera", key):
            return default

        value: str = CONFIG.get("Camera", key).strip()
        parsed, error = validation.is_boolean(value)
        if error is not None:
            get_errors().add_error(_("Camera config [%s] %s Using default value %s.") % (key, error, default))
            return default
        return parsed

    def _safe_slug(self, value: str, fallback: str) -> str:
        allowed: list[str] = [c if c.isalnum() or c in "._-" else "_" for c in str(value).strip()]
        slug: str = "".join(allowed).strip("._-")
        return slug or fallback

    @staticmethod
    def _stringify_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
