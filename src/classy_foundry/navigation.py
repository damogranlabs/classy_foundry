"""SpaceMouse navigation: a puck deflection applied to the camera.

Pure math -- no polyscope. The view layer reads the camera, calls `navigate`, and writes
the result back, which keeps this testable and means the device can never touch the
document: it moves the camera and nothing else.

**Two modes**, the classic 3Dconnexion split, differing in three things -- what the
rotation pivots about, what a dolly does, and the sign of every axis:

- `OBJECT` (the default): the puck moves *the model*. Push right and the model goes right,
  so the camera goes left; rotation orbits the model, which stays in the middle of the
  view; a dolly changes the distance and is clamped, so you can never zoom through the
  thing you are building.
- `CAMERA`: the puck moves *the eye*. Push right and the camera goes right; rotation turns
  the gaze from where it stands; a dolly flies, target and all, straight through the scene.

Both keep `up`, so the horizon never rolls and the model never ends up upside down -- which
is why a puck roll (rz) is unmapped; there is nothing for it to do that would not
disorient.

The device's axes are x right, y up (cap lift) and z toward the user (cap pull). Every
sensitivity is signed: **negate one to invert that axis**, which is the fix when a single
control feels backwards in an otherwise correct mode.
"""

from dataclasses import dataclass

import numpy as np
from classy_blocks.util import functions as cbf

FULL_DEFLECTION = 350.0  # counts at the puck's limit; deflections are read as a fraction of it

ORIGIN = np.zeros(3)
POLE_MARGIN = 0.12  # radians kept clear of straight-up and straight-down
MIN_DISTANCE = 0.01  # of the scene extent: how close `OBJECT` mode may get to the model


@dataclass
class Sensitivity:
    """Pan and dolly are in scene extents per second; orbit is in radians per second.
    Negate any of them to invert that axis."""

    pan: float = 2.0
    dolly: float = -2.0
    orbit: float = -2.0


SENSITIVITY = Sensitivity()


@dataclass
class View:
    """The camera, as polyscope describes it and takes it back."""

    position: np.ndarray
    target: np.ndarray
    up: np.ndarray


class ObjectMode:
    """The puck moves the model: the camera does the opposite and orbits around it."""

    name = "Object"
    sign = -1.0

    @staticmethod
    def orbit(view: View, angles: np.ndarray) -> View:
        """The eye goes round; the model stays in the middle of the view."""
        offset = _turn(view.position - view.target, angles, view.up)
        return View(view.target + offset, view.target, view.up)

    @staticmethod
    def dolly(view: View, step: float, extent: float) -> View:
        """Distance only, so the camera keeps pointing where it pointed -- and clamped, so
        it never arrives at the model, let alone passes through it."""
        offset = view.position - view.target
        distance = max(float(np.linalg.norm(offset)) + step * extent, MIN_DISTANCE * extent)
        return View(view.target + _unit(offset) * distance, view.target, view.up)


class CameraMode:
    """The puck moves the eye: it looks around from where it stands, and flies."""

    name = "Camera"
    sign = 1.0

    @staticmethod
    def orbit(view: View, angles: np.ndarray) -> View:
        """The gaze turns; the eye stays put."""
        offset = _turn(view.target - view.position, angles, view.up)
        return View(view.position, view.position + offset, view.up)

    @staticmethod
    def dolly(view: View, step: float, extent: float) -> View:
        """Straight ahead, pivot and all -- through the scene, with nothing to stop at."""
        travel = _unit(view.target - view.position) * -step * extent
        return View(view.position + travel, view.target + travel, view.up)


OBJECT = ObjectMode()
CAMERA = CameraMode()


def navigate(
    view: View,
    motion,
    extent: float,
    dt: float,
    sensitivity: Sensitivity = SENSITIVITY,
    mode=OBJECT,
) -> View:
    """The camera after one frame of the given deflection. A still puck returns the same
    view because every term is zero -- no special case needed."""
    scale = mode.sign / FULL_DEFLECTION
    translation = np.asarray(motion.translation, dtype=float) * scale
    rotation = np.asarray(motion.rotation, dtype=float) * scale

    turned = mode.orbit(view, rotation * sensitivity.orbit * dt)
    closer = mode.dolly(turned, translation[2] * sensitivity.dolly * dt, extent)
    return _pan(closer, translation[:2] * sensitivity.pan * dt * extent)


def _turn(offset: np.ndarray, angles: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Azimuth about `up`, then elevation about the right axis, keeping the length. The
    elevation is clipped rather than branched on, so the view slides to a stop just short
    of the pole instead of flipping over."""
    turned = cbf.rotate(offset, -angles[1], up, ORIGIN)
    right = np.cross(_unit(turned), up)
    polar = _angle(turned, up)
    allowed = np.clip(polar + angles[0], POLE_MARGIN, np.pi - POLE_MARGIN) - polar
    return cbf.rotate(turned, allowed, right, ORIGIN)


def _pan(view: View, step: np.ndarray) -> View:
    """Sideways and vertically in camera axes. The target travels with the camera in both
    modes, so the next rotation turns around whatever was panned into view."""
    forward = _unit(view.target - view.position)
    right = _unit(np.cross(forward, view.up))
    shift = right * step[0] + _unit(np.cross(right, forward)) * step[1]
    return View(view.position + shift, view.target + shift, view.up)


def _unit(vector: np.ndarray) -> np.ndarray:
    return np.asarray(vector, dtype=float) / np.linalg.norm(vector)


def _angle(vector: np.ndarray, axis: np.ndarray) -> float:
    return float(np.arccos(np.clip(_unit(vector) @ _unit(axis), -1.0, 1.0)))
