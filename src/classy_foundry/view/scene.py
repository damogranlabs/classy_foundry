"""Save/restore the Polyscope scene state alongside the model pickle.

Polyscope persists none of this itself (its `.polyscope.ini` is only window geometry + UI
scale), but it exposes readers for the parts that matter, so we fold the **savable,
non-appearance** state into the model's opaque `scene` blob (see `model.save`):

- the whole **camera** in one string via `get_view_as_json` — viewpoint, up/front dir, fov,
  projection, navigation style, view centre;
- each **slice plane**'s pose + visibility flags (the cross-section cuts).

Deliberately excluded: the **ground plane** (all its setters are write-only — nothing to
read back) and **appearance** (background, per-structure colours/radii — by request; the
latter also fights the per-rebuild structure re-registration).

Slice planes have no enumeration API, so we probe their auto-names (`Scene Slice Plane N`)
and stop after a few consecutive misses (tolerating a small gap from a removed plane).
"""

import polyscope as ps

_SLICE_NAME = "Scene Slice Plane "  # Polyscope's auto-name for `add_scene_slice_plane`
_PROBE_TOLERANCE = 3  # stop after this many missing indices in a row
_DEFAULT_VERBOSITY = 2  # Polyscope's default; the app never changes it, so this is what we restore


def _slice_plane(index):
    """The scene slice plane at `index`, or None — a phantom name yields a handle whose access
    raises (`get_slice_plane` itself only warns), so touching `get_center` is the real test."""
    try:
        plane = ps.get_slice_plane(f"{_SLICE_NAME}{index}")
        plane.get_center()
        return plane
    except Exception:
        return None


def _slice_planes():
    """Enumerate scene slice planes by probing their auto-names (polyscope has no list API),
    stopping after a few consecutive misses. Verbosity is muted for the probe's duration so a
    missing name doesn't spam an `[ERROR]` line to the console on every save, then restored."""
    ps.set_verbosity(0)
    try:
        planes, index, misses = [], 0, 0
        while misses < _PROBE_TOLERANCE:
            plane = _slice_plane(index)
            if plane is None:
                misses += 1
            else:
                planes.append(plane)
                misses = 0
            index += 1
        return planes
    finally:
        ps.set_verbosity(_DEFAULT_VERBOSITY)


def capture():
    """The savable scene state as a plain (picklable) dict for `model.save`."""
    return {
        "view": ps.get_view_as_json(),
        "slice_planes": [
            {
                "center": [float(x) for x in plane.get_center()],
                "normal": [float(x) for x in plane.get_normal()],
                "enabled": plane.get_enabled(),
                "draw_plane": plane.get_draw_plane(),
                "draw_widget": plane.get_draw_widget(),
            }
            for plane in _slice_planes()
        ],
    }


def apply(scene):
    """Restore a captured scene; a no-op for None (a fresh/legacy model)."""
    if not scene:
        return
    ps.remove_all_slice_planes()
    for spec in scene.get("slice_planes", []):
        plane = ps.add_scene_slice_plane()
        plane.set_pose(spec["center"], spec["normal"])
        plane.set_draw_plane(spec["draw_plane"])
        plane.set_draw_widget(spec["draw_widget"])
        plane.set_enabled(spec["enabled"])
    ps.set_view_from_json(scene["view"])  # last, so the camera is the final word
