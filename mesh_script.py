import classy_blocks as cb
from numpy import pi, e, sin, cos, tan, arcsin, arccos, arctan, arctan2, sqrt, exp, log, radians, degrees, deg2rad, abs

mesh = cb.Mesh()

sketch0 = cb.MappedSketch([], [])

box0 = cb.Box([2.0, 0.0, 0.0], [3.0, 1.0, 1.0])
mesh.add(box0)

cylinder = cb.Cylinder([0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 1.0, 0.0])
mesh.add(cylinder)

half_sphere = cb.Hemisphere([0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0])
mesh.add(half_sphere)

elbow = cb.Elbow([2.0, 0.0, 0.0], [2.0, 1.0, 0.0], [1.0, 0.0, 0.0], -pi/2, [2.0, 0.0, 2.0], [0.0, 1.0, 0.0], 1.0)
mesh.add(elbow)

mesh.write('system/blockMeshDict')
