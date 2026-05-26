from __future__ import annotations

from typing import Any, Callable

from core import validation
from core.constants import COLORS as C
from core.container import Container
from core.widgets import Frame
from core.window import Window
from plugins.abstractplugin import AbstractPlugin


class Photosensor(AbstractPlugin):
    def __init__(self, label: str = "", taskplacement: str = "invisible", taskupdatetime: int = 10) -> None:
        super().__init__(label, taskplacement, taskupdatetime)

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "widthproportion": validation.is_in_unit_interval,
            "heightproportion": validation.is_in_unit_interval,
            "marginx": validation.is_in_unit_interval,
            "marginy": validation.is_in_unit_interval,
            "flashdurationms": validation.is_natural_integer,
            "color": validation.is_color,
            "onmarker": validation.is_string,
            "offmarker": validation.is_string,
        }

        self.parameters.update(
            dict(
                widthproportion=0.05,
                heightproportion=0.05,
                marginx=0.0,
                marginy=0.0,
                flashdurationms=100,
                color=C["LIGHTGREY"],
                onmarker="ps_on",
                offmarker="ps_off",
            )
        )

        self.display_title = False
        self.active_until: float = 0
        self._is_on: bool = False

    def create_widgets(self) -> None:
        super().create_widgets()
        screen_container = Window.MainWindow.get_container("fullscreen")
        width = screen_container.w * self.parameters["widthproportion"]
        height = screen_container.h * self.parameters["heightproportion"]
        left = screen_container.l + screen_container.w * self.parameters["marginx"]
        bottom = screen_container.b + screen_container.h - height - screen_container.h * self.parameters["marginy"]

        self.add_widget(
            "square",
            Frame,
            container=Container("photosensor_square", left, bottom, width, height),
            fill_color=self.parameters["color"],
            border_color=self.parameters["color"],
            draw_order=100,
        )
        self.widgets["photosensor_square"].set_visibility(False)

    def pulse(self) -> None:
        if not self.alive or self.is_paused():
            return

        self._is_on = True
        self.active_until = self.scenario_time + (self.parameters["flashdurationms"] / 1000)
        self.widgets["photosensor_square"].set_visibility(True)
        self.push_marker(self.parameters["onmarker"])

    def compute_next_plugin_state(self) -> None:
        if not super().compute_next_plugin_state():
            return

        if self._is_on and self.scenario_time >= self.active_until:
            self._is_on = False
            self.widgets["photosensor_square"].set_visibility(False)
            if self.parameters["offmarker"] != "":
                self.push_marker(self.parameters["offmarker"])

    def push_marker(self, marker: str) -> None:
        if marker == "":
            return

        scenario: Any | None = getattr(self, "scenario", None)
        if scenario is None:
            return

        lsl = scenario.plugins.get("labstreaminglayer")
        if lsl is not None and lsl.stream_outlet is not None:
            lsl.push(marker)
