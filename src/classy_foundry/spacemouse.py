"""A SpaceMouse, read straight from spacenavd's UNIX socket.

The protocol is eight little-endian `int32`s per packet --
`[type, x, y, z, rx, ry, rz, period]`, type 0 for motion and 1/2 for button press/release
(spacenavd, `src/proto_unix.c`). A proto-v0 client receives motion and button events with
no handshake (`src/client.c`), so this needs no `libspnav`, no ctypes and no dependency.

The device drives **the camera only** -- points and blocks are the mouse's job.

Axis values are the puck's *absolute* deflection, not deltas, so a poll keeps the latest
packet and discards the backlog; anything else would accumulate a lag the hand can feel.
"""

import socket
import struct
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

SOCKET_PATH = "/var/run/spnav.sock"

MOTION, PRESS, RELEASE = 0, 1, 2  # packet types (spacenavd's UEV_* enum)

PACKET = struct.Struct("<8i")
DEADZONE = 6  # counts; spacenavd's autocal removes the drift, this ignores the jitter


@dataclass
class Motion:
    """One puck deflection: translation along, and rotation about, the device's axes
    (x right, y up, z toward the user)."""

    translation: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation: np.ndarray = field(default_factory=lambda: np.zeros(3))

    @property
    def is_still(self) -> bool:
        return not (self.translation.any() or self.rotation.any())


STILL = Motion()


class SpaceMouse:
    """Non-blocking reader. `open()` returns None when there is no daemon, and every error
    afterwards degrades to stillness -- a missing or unplugged device must never stop the
    editor."""

    def __init__(self, sock: socket.socket) -> None:
        self.socket: Optional[socket.socket] = sock
        self.socket.setblocking(False)
        self._buffer = b""

    @classmethod
    def open(cls, path: str = SOCKET_PATH) -> Optional["SpaceMouse"]:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(path)
        except OSError:
            return None
        return cls(sock)

    def poll(self) -> Motion:
        """The puck's current deflection, or `STILL` when it is centred or unavailable."""
        self._buffer += self._read()
        whole = len(self._buffer) // PACKET.size
        packets = [PACKET.unpack_from(self._buffer, i * PACKET.size) for i in range(whole)]
        self._buffer = self._buffer[whole * PACKET.size:]
        motions = [packet for packet in packets if packet[0] == MOTION]
        return self._motion(motions[-1]) if motions else STILL

    def _read(self) -> bytes:
        chunks = []
        for sock in filter(None, [self.socket]):
            chunks.append(self._drain(sock))
        return b"".join(chunks)

    def _drain(self, sock: socket.socket) -> bytes:
        chunks = []
        while True:
            try:
                chunk = sock.recv(4096)
            except BlockingIOError:
                return b"".join(chunks)
            except OSError:
                self.close()
                return b"".join(chunks)
            if not chunk:            # the daemon went away
                self.close()
                return b"".join(chunks)
            chunks.append(chunk)

    @staticmethod
    def _motion(packet) -> Motion:
        axes = np.asarray(packet[1:7], dtype=float)
        axes[np.abs(axes) < DEADZONE] = 0.0
        return Motion(axes[:3], axes[3:])

    def close(self) -> None:
        for sock in filter(None, [self.socket]):
            sock.close()
        self.socket = None
