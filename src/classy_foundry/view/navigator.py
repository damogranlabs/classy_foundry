"""Wires a SpaceMouse to the polyscope camera, and the panel that tunes it.

The only state is **how far ahead the pivot sits**: the camera's position and direction are
read fresh from polyscope every frame, so ordinary mouse navigation and the puck cooperate
instead of fighting -- an orbit with the mouse simply carries the pivot along in front of
the camera. The camera is written back only while the puck is actually deflected, so a
still device costs nothing and never overrides the mouse.

`up` comes from `ps.get_up_dir()`, the *world* up, not from the camera: polyscope's camera
up is perpendicular to its look direction and therefore tilts, and feeding that back would
let the horizon drift.
"""

import time
from dataclasses import fields
from typing import Optional

import numpy as np
import polyscope as ps
import polyscope.imgui as psim

from ..navigation import CAMERA, OBJECT, Sensitivity, View, navigate
from ..spacemouse import SpaceMouse

MODES = (OBJECT, CAMERA)
SENSITIVITY_RANGE = 3.0  # sliders run -3..3; negative inverts that axis

# What `ps.get_up_dir()` calls each world up direction.
UP_DIRS = {
    "x_up": (1.0, 0.0, 0.0),
    "neg_x_up": (-1.0, 0.0, 0.0),
    "y_up": (0.0, 1.0, 0.0),
    "neg_y_up": (0.0, -1.0, 0.0),
    "z_up": (0.0, 0.0, 1.0),
    "neg_z_up": (0.0, 0.0, -1.0),
}

MAX_STEP = 0.1  # seconds; a stalled frame must not fling the camera across the scene


class Navigator:
    def __init__(self, device: SpaceMouse, distance: float = 1.0) -> None:
        self.device = device
        self.distance = distance
        self.clock = time.perf_counter()
        self.mode = OBJECT
        self.sensitivity = Sensitivity()

    @classmethod
    def attach(cls, distance: float = 1.0) -> Optional["Navigator"]:
        """A navigator, or None when spacenavd isn't running -- the editor is unaffected
        either way."""
        device = SpaceMouse.open()
        return None if device is None else cls(device, distance)

    def step(self, extent: float) -> bool:
        """Poll the puck and move the camera; True if it moved."""
        dt, self.clock = min(time.perf_counter() - self.clock, MAX_STEP), time.perf_counter()
        motion = self.device.poll()
        for deflection in filter(lambda m: not m.is_still, [motion]):
            self._apply(deflection, extent, dt)
            return True
        return False

    def _apply(self, motion, extent: float, dt: float) -> None:
        camera = ps.get_view_camera_parameters()
        position = np.asarray(camera.get_position(), dtype=float)
        up = np.asarray(UP_DIRS[ps.get_up_dir()], dtype=float)
        target = position + np.asarray(camera.get_look_dir(), dtype=float) * self.distance

        moved = navigate(View(position, target, up), motion, extent, dt,
                         self.sensitivity, self.mode)

        self.distance = float(np.linalg.norm(moved.position - moved.target))
        ps.look_at_dir(moved.position, moved.target, up)


def draw_settings(navigator: Optional["Navigator"]) -> None:
    """The Navigation panel: which mode, and how fast each axis is.

    The mode is the coarse choice -- whether the puck moves the model or the eye. The
    sliders are the fine one: each runs through zero, so a **negative** value inverts that
    axis, which is the fix when one control feels backwards in an otherwise correct mode.
    Tuning is live, because the feel of this cannot be read off a number; `Defaults` then
    prints the settings as the line to paste into `navigation.Sensitivity`.
    """
    psim.TextUnformatted("Navigation")
    for device in filter(None, [navigator]):
        _draw_mode(device)
        _draw_sensitivity(device)
    for _ in filter(None, [navigator is None]):
        psim.TextDisabled("no SpaceMouse (spacenavd not running)")


def _draw_mode(navigator: "Navigator") -> None:
    changed, index = psim.Combo("mode", MODES.index(navigator.mode), [mode.name for mode in MODES])
    navigator.mode = MODES[index] if changed else navigator.mode
    psim.TextDisabled({OBJECT: "the puck moves the model",
                       CAMERA: "the puck moves the eye"}[navigator.mode])


def _draw_sensitivity(navigator: "Navigator") -> None:
    """One slider per field of `Sensitivity`, so adding one there adds it here."""
    for field in fields(navigator.sensitivity):
        _, value = psim.SliderFloat(field.name, getattr(navigator.sensitivity, field.name),
                                    -SENSITIVITY_RANGE, SENSITIVITY_RANGE)
        setattr(navigator.sensitivity, field.name, value)
    for _ in filter(None, [psim.Button("Defaults")]):
        print(f"# paste into navigation.Sensitivity, and set Navigator's mode to {navigator.mode.name}")
        print(format_defaults(navigator.sensitivity))


def format_defaults(sensitivity: Sensitivity) -> str:
    """The tuned settings as the source line that would make them the defaults."""
    values = ", ".join(f"{field.name}: float = {getattr(sensitivity, field.name):.2f}"
                       for field in fields(sensitivity))
    return f"    {values.replace(', ', chr(10) + '    ')}"
