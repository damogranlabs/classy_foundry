"""The spacenavd wire protocol, tested over a socketpair -- no hardware needed.

A packet is 8 little-endian int32s: `[type, x, y, z, rx, ry, rz, period]`, where type 0 is
motion and 1/2 are button press/release (see spacenavd's `src/proto_unix.c`).
"""

import socket
import struct

import numpy as np

from classy_foundry.spacemouse import DEADZONE, MOTION, PRESS, SpaceMouse

PACKET = struct.Struct("<8i")


def a_pair():
    """(the device as foundry sees it, the socket spacenavd would write to)."""
    ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    return SpaceMouse(ours), theirs


def send(sock, kind, *values):
    sock.sendall(PACKET.pack(kind, *values, *([0] * (7 - len(values)))))


def test_a_still_device_reports_no_motion():
    device, _ = a_pair()

    motion = device.poll()

    assert motion.is_still
    assert np.allclose(motion.translation, 0)
    assert np.allclose(motion.rotation, 0)


def test_a_motion_packet_becomes_translation_and_rotation():
    device, daemon = a_pair()
    send(daemon, MOTION, 100, 200, 300, 400, 500, 600, 16)

    motion = device.poll()

    assert np.allclose(motion.translation, [100, 200, 300])
    assert np.allclose(motion.rotation, [400, 500, 600])
    assert not motion.is_still


def test_only_the_latest_deflection_counts():
    """Axis values are absolute, not deltas, so a backlog must not accumulate."""
    device, daemon = a_pair()
    send(daemon, MOTION, 100, 0, 0, 0, 0, 0)
    send(daemon, MOTION, 300, 0, 0, 0, 0, 0)

    motion = device.poll()

    assert np.allclose(motion.translation, [300, 0, 0])


def test_button_packets_are_ignored():
    device, daemon = a_pair()
    send(daemon, PRESS, 1, 1)

    assert device.poll().is_still


def test_a_button_does_not_discard_the_motion_before_it():
    device, daemon = a_pair()
    send(daemon, MOTION, 250, 0, 0, 0, 0, 0)
    send(daemon, PRESS, 0, 1)

    assert np.allclose(device.poll().translation, [250, 0, 0])


def test_noise_below_the_deadzone_reads_as_still():
    device, daemon = a_pair()
    send(daemon, MOTION, DEADZONE - 1, 0, 0, 0, -(DEADZONE - 1), 0)

    motion = device.poll()

    assert motion.is_still
    assert np.allclose(motion.translation, 0)


def test_a_half_delivered_packet_waits_for_its_rest():
    device, daemon = a_pair()
    whole = PACKET.pack(MOTION, 300, 0, 0, 0, 0, 0, 0)
    daemon.sendall(whole[:20])

    assert device.poll().is_still                 # nothing usable yet

    daemon.sendall(whole[20:])

    assert np.allclose(device.poll().translation, [300, 0, 0])


def test_a_closed_daemon_is_not_fatal():
    device, daemon = a_pair()
    daemon.close()

    assert device.poll().is_still                 # the editor keeps running


def test_open_returns_none_when_there_is_no_daemon(tmp_path):
    assert SpaceMouse.open(str(tmp_path / "absent.sock")) is None
