"""The polyscope-facing half of SpaceMouse navigation, driven over a socketpair."""

import socket
import struct

import numpy as np
import polyscope as ps
import polyscope.imgui as psim
import pytest

from classy_foundry.navigation import CAMERA, Sensitivity
from classy_foundry.spacemouse import MOTION, SpaceMouse
from classy_foundry.view.navigator import Navigator, draw_settings

PACKET = struct.Struct("<8i")


@pytest.fixture(scope="module")
def mock_polyscope():
    ps.set_allow_headless_backends(True)
    ps.init("openGL_mock")
    ps.set_up_dir("z_up")
    ps.register_point_cloud("scene", np.random.default_rng(0).random((20, 3)))
    yield
    ps.shutdown()


def a_navigator():
    """The sensitivities are pinned positive: the ones in `navigation` are a user
    preference and must not decide which way these tests expect the camera to go."""
    ours, daemon = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    navigator = Navigator(SpaceMouse(ours), distance=5.0)
    navigator.sensitivity = Sensitivity(pan=0.7, dolly=1.2, orbit=1.5)
    return navigator, daemon


def deflect(sock, *axes):
    sock.sendall(PACKET.pack(MOTION, *axes, 0))


def test_a_still_puck_leaves_the_camera_untouched(mock_polyscope):
    navigator, _ = a_navigator()
    ps.look_at_dir((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    ps.frame_tick()
    before = np.asarray(ps.get_view_camera_parameters().get_position(), dtype=float)

    assert navigator.step(extent=2.0) is False
    assert np.allclose(ps.get_view_camera_parameters().get_position(), before)


def test_a_deflection_moves_the_camera(mock_polyscope):
    navigator, daemon = a_navigator()
    ps.look_at_dir((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    ps.frame_tick()
    before = np.asarray(ps.get_view_camera_parameters().get_position(), dtype=float)
    deflect(daemon, 0, 0, 0, 0, 300, 0)          # a twist

    assert navigator.step(extent=2.0) is True
    assert not np.allclose(ps.get_view_camera_parameters().get_position(), before)


def test_dollying_updates_the_remembered_pivot_distance(mock_polyscope):
    """Object mode by default: pulling the puck toward you brings the model closer."""
    navigator, daemon = a_navigator()
    ps.look_at_dir((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    ps.frame_tick()
    deflect(daemon, 0, 0, 300, 0, 0, 0)          # pull the cap toward you

    navigator.step(extent=2.0)

    assert navigator.distance < 5.0


def test_the_mode_can_be_switched_and_reverses_the_dolly(mock_polyscope):
    navigator, daemon = a_navigator()
    navigator.mode = CAMERA
    ps.look_at_dir((0.0, -10.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    ps.frame_tick()
    deflect(daemon, 0, 0, 300, 0, 0, 0)

    navigator.step(extent=2.0)

    assert np.isclose(navigator.distance, 5.0)   # camera mode flies: the pivot comes along


def test_the_navigation_panel_draws_with_and_without_a_device(mock_polyscope):
    navigator, _ = a_navigator()
    ps.frame_tick()

    if psim.Begin("test"):
        draw_settings(navigator)
        draw_settings(None)
    psim.End()


def test_attach_returns_none_without_a_daemon(monkeypatch):
    monkeypatch.setattr(SpaceMouse, "open", classmethod(lambda cls, *args: None))

    assert Navigator.attach() is None
