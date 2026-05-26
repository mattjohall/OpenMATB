# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from typing import Any, Callable

from core import validation
from plugins import Instructions
import socket
from time import sleep

try:
    import pylsl
except (ImportError, RuntimeError):
    pylsl = None


class Labstreaminglayer(Instructions):
    def __init__(self) -> None:
        super().__init__()

        self.validation_dict: dict[str, Callable[..., Any]] = {
            "marker": validation.is_string,
            "streamsession": validation.is_boolean,
            "pauseatstart": validation.is_boolean,
            "state": validation.is_string,
            "socketnum": validation.is_string,
            "LSLfilename": validation.is_string,
            "recordinglocation": validation.is_string,
        }

        self.parameters.update({"marker": "", "streamsession": False, "pauseatstart": False, "socketnum": 22345, "LSLfilename": "", "recordinglocation": "False"})

        self.stream_info: Any | None = None
        self.stream_outlet: Any | None = None
        self.stop_on_end: bool = False
        self.outlet: bool = False
        self.state: bool = False
        self.createPort()
        self.lsl_wait_msg: str = _("Please enable the OpenMATB stream into your LabRecorder.")

    def start(self) -> None:
        # If we get there it's because the plugin is used.
        # If pylsl is not available this part should fail.
        # Create a LSL marker outlet.
        super().start()
        self.stream_info = pylsl.StreamInfo(
            "OpenMATB",
            type="Markers",
            channel_count=1,
            nominal_srate=0,
            channel_format="string",
            source_id="myuidw435368",
        )
        self.stream_outlet = pylsl.StreamOutlet(self.stream_info)

        if self.parameters["pauseatstart"] is True:
            self.slides = [self.get_msg_slide_content(self.lsl_wait_msg)]

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.parameters["streamsession"] is True and self.logger.lsl is None:
            self.logger.lsl = self
        elif self.parameters["streamsession"] is False and self.logger.lsl is not None:
            self.logger.lsl = None

        if self.parameters["marker"] != "":
            # A marker has been set. Push it to the outlet.
            self.push(self.parameters["marker"])

            # and reset the marker to empty.
            self.parameters["marker"] = ""

    def push(self, message: str) -> None:
        if self.stream_outlet is None:
            return
        self.stream_outlet.push_sample([message])

    #        print(message)

    def stop(self) -> None:
        super().stop()
        self.stream_info = None
        self.stream_outlet = None
        if self.state:
            if self.outlet:
                s = self.socket
                s.sendall(b"stop\n")
                print('stopped LSL')
            self.state = False

    def get_msg_slide_content(self, str_msg: str) -> str:
        return f"<title>Lab streaming layer\n{self.lsl_wait_msg}"
    
    def createPort(self):
        try:
            self.socket = socket.create_connection(("localhost", self.parameters['socketnum']))
            self.outlet = True
            print('Successfully sees LSL Lab Recorder')
        except:
            print('Could not bind LSL Lab Recorder, no recording.')    
    def startLSL(self) -> None:
            if self.outlet:
                s = self.socket
                s.sendall(b"update\n")
                s.sendall(b"select all\n")
                sleep(0.2)
                if self.parameters["LSLfilename"] != "":
                    command = f"filename {{root:{self.parameters['recordinglocation']}}} {{template:{self.parameters['LSLfilename']}}}\n"
                    print(f'Sending LSL setup {command}')
                    s.sendall(command.encode('utf-8'))
                    sleep(0.2)
                sleep(0.2)
                s.sendall(b"start\n")
                print('started LSL')
                self.state = True
    def stopLSL(self) -> None:
        if self.state:
            if self.outlet:
                s = self.socket
                s.sendall(b"stop\n")
                print('stopped LSL')
            self.state = False