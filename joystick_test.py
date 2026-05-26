from __future__ import annotations

from collections import deque

import pyglet
from pyglet.window import key as winkey


HAT_SIDES: list[str] = ["LEFT", "UP", "RIGHT", "DOWN"]


class JoystickTester(pyglet.window.Window):
    def __init__(self) -> None:
        super().__init__(width=1080, height=760, caption="OpenMATB Joystick Tester", resizable=False)

        self.deadzone: float = 0.05
        self.force: float = 1.0
        self.keyboard_pressed: set[str] = set()
        self.event_log: deque[str] = deque(maxlen=14)

        self.device = None
        self.button_state: dict[str, bool] = {}
        self.hat_state: dict[str, bool] = {}
        self.raw_x: float = 0.0
        self.raw_y: float = 0.0
        self.scaled_x: float = 0.0
        self.scaled_y: float = 0.0

        joysticks = pyglet.input.get_joysticks()
        if joysticks:
            self.device = joysticks[0]
            self.device.open()
            self.button_state = {f"JOY_BTN_{index + 1}": False for index in range(len(self.device.buttons))}
            self.hat_state = {f"JOY_HAT_{side}": False for side in HAT_SIDES}
            self.event_log.append(f"Connected: {self.device.device.name}")
        else:
            self.event_log.append("No joystick detected. Plug one in and relaunch this tester.")

        pyglet.clock.schedule_interval(self.update_state, 1 / 60)

    def on_draw(self) -> None:
        self.clear()

        lines: list[str] = [
            "OpenMATB Joystick Tester",
            "",
            "Controls: [ / ] deadzone  |  - / = force  |  R reset  |  ESC close",
            "",
        ]

        if self.device is None:
            lines.extend(
                [
                    "No joystick found.",
                    "",
                    "Keyboard test:",
                    f"Currently pressed: {self.format_pressed_keys(self.keyboard_pressed)}",
                ]
            )
        else:
            lines.extend(
                [
                    f"Device: {self.device.device.name}",
                    f"Joystick buttons available: {len(self.device.buttons)}",
                    "",
                    f"Deadzone: {self.deadzone:.2f}",
                    f"Force: {self.force:.2f}",
                    "",
                    f"Raw axes:    x={self.raw_x:+.3f}   y={self.raw_y:+.3f}",
                    f"Scaled axes: x={self.scaled_x:+.3f}   y={self.scaled_y:+.3f}",
                    "",
                    f"Pressed joystick inputs: {self.get_pressed_joystick_inputs()}",
                    f"Pressed keyboard keys:   {self.format_pressed_keys(self.keyboard_pressed)}",
                    "",
                    "Suggested OpenMATB mapping examples:",
                    "communications: UP / DOWN / LEFT / RIGHT / ENTER",
                    "resman: NUM_1 ... NUM_8",
                    "sysmon or extra actions: JOY_BTN_1, JOY_BTN_2, JOY_HAT_UP, ...",
                    "",
                    "Example scenario lines:",
                    "0:00:00;sysmon;scales-1-key;JOY_BTN_1",
                    "0:00:00;resman;pump-1-key;NUM_1",
                    "0:00:00;communications;keys-validateresponse;ENTER",
                ]
            )

        lines.extend(["", "Recent events:"])
        lines.extend(list(self.event_log)[-14:])

        label = pyglet.text.Label(
            "\n".join(lines),
            x=20,
            y=self.height - 20,
            width=self.width - 40,
            multiline=True,
            anchor_x="left",
            anchor_y="top",
            font_name="Consolas",
            font_size=14,
        )
        label.draw()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        key_name = winkey.symbol_string(symbol)
        self.keyboard_pressed.add(key_name)
        self.event_log.appendleft(f"Keyboard press: {key_name}")

        if symbol == winkey.ESCAPE:
            self.close()
        elif symbol == winkey.BRACKETLEFT:
            self.deadzone = max(0.0, round(self.deadzone - 0.01, 2))
        elif symbol == winkey.BRACKETRIGHT:
            self.deadzone = min(0.99, round(self.deadzone + 0.01, 2))
        elif symbol == winkey.MINUS:
            self.force = max(0.05, round(self.force - 0.05, 2))
        elif symbol == winkey.EQUAL:
            self.force = min(5.0, round(self.force + 0.05, 2))
        elif symbol == winkey.R:
            self.deadzone = 0.05
            self.force = 1.0

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        key_name = winkey.symbol_string(symbol)
        self.keyboard_pressed.discard(key_name)
        self.event_log.appendleft(f"Keyboard release: {key_name}")

    def update_state(self, dt: float) -> None:
        if self.device is None:
            return

        self.raw_x = float(self.device.x)
        self.raw_y = float(self.device.y)
        self.scaled_x = self.apply_deadzone_and_force(self.raw_x)
        self.scaled_y = self.apply_deadzone_and_force(self.raw_y)

        for index, pressed in enumerate(self.device.buttons):
            button_name = f"JOY_BTN_{index + 1}"
            previous = self.button_state[button_name]
            current = bool(pressed)
            if previous != current:
                state = "press" if current else "release"
                self.event_log.appendleft(f"{button_name} {state}")
            self.button_state[button_name] = current

        next_hat_state = {
            "JOY_HAT_LEFT": self.device.hat_x == -1,
            "JOY_HAT_UP": self.device.hat_y == 1,
            "JOY_HAT_RIGHT": self.device.hat_x == 1,
            "JOY_HAT_DOWN": self.device.hat_y == -1,
        }
        for hat_name, current in next_hat_state.items():
            previous = self.hat_state[hat_name]
            if previous != current:
                state = "press" if current else "release"
                self.event_log.appendleft(f"{hat_name} {state}")
            self.hat_state[hat_name] = current

    def apply_deadzone_and_force(self, value: float) -> float:
        if abs(value) < self.deadzone:
            return 0.0
        return round(value * self.force, 3)

    def get_pressed_joystick_inputs(self) -> str:
        pressed = [name for name, is_pressed in self.button_state.items() if is_pressed]
        pressed.extend([name for name, is_pressed in self.hat_state.items() if is_pressed])
        return ", ".join(pressed) if pressed else "(none)"

    @staticmethod
    def format_pressed_keys(keys: set[str]) -> str:
        if not keys:
            return "(none)"
        return ", ".join(sorted(keys))


if __name__ == "__main__":
    JoystickTester()
    pyglet.app.run()
