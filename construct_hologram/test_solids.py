"""Solids as a modelling program reads them: every primitive wound outward and closed where it should be, and a
mirrored copy wound like its original (seen in Blender's face orientation on the R34: the whole left side of the car
and every tyre, lamp and wheel were inside out; its fully rounded C-pillar was not a closed surface)."""

import unittest

from . import scene, shapes


def _volume(tris):
    return sum((a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6 for a, b, c in tris)


def _edges(tris):
    """(edges used twice the same way round, edges with no partner, degenerate triangles)"""
    key = lambda p: tuple(round(x, 7) for x in p)
    used = {}
    for t in tris:
        a, b, c = (key(p) for p in t)
        for e in ((a, b), (b, c), (c, a)):
            used[e] = used.get(e, 0) + 1
    same = sum(1 for n in used.values() if n > 1)
    loose = sum(1 for (a, b) in used if (b, a) not in used)
    flat = sum(1 for t in tris if len({key(p) for p in t}) < 3)
    return same, loose, flat


SQUARE = [(0, 0), (1, 0), (1, 1), (0, 1)]


class Winding(unittest.TestCase):
    def test_every_closed_primitive_is_wound_outward_and_closed(self):
        solids = {
            "box": shapes.box([1, 2, 3]),
            "cylinder": shapes.frustum(0.5, 0.5, 1.0),
            "cone": shapes.frustum(0.5, 0.2, 1.0),
            "lathe up": shapes.lathe([(0, 0), (1, 0), (1, 1), (0, 1)]),
            "lathe down": shapes.lathe([(0, 1), (1, 1), (1, 0), (0, 0)]),
            "torus": shapes.torus(1.0, 0.3),
            "sphere": shapes.ellipsoid([1.0, 2.0, 1.5]),
            "loft": shapes.loft([[0, 1, 0, 1], [1, 0.8, 0.1, 0.9]]),
            "loft fine": shapes.loft([[0, 1, 0, 1], [1, 0.8, 0.1, 0.9], [2, 0.5, 0.2, 0.6]], 0.5, True),
            "tube with caps": shapes.tube([(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)], 0.1, caps=True),
        }
        for axis in "xyz":
            for turn, prof in (("ccw", SQUARE), ("cw", SQUARE[::-1])):
                solids["extrude %s %s" % (axis, turn)] = shapes.extrude(prof, 1.0, axis)
        for name, m in solids.items():
            with self.subTest(name):
                self.assertGreater(_volume(m.tris), 0, "inside out")
                self.assertEqual(_edges(m.tris), (0, 0, 0), "not one closed surface wound one way")

    def test_open_primitives_face_out_and_have_no_slivers(self):
        for name, m in (("open cylinder", shapes.frustum(0.5, 0.5, 1.0, caps=False)),
                        ("bowl", shapes.lathe([(0, 0), (1, 0.2), (1.2, 1)])),
                        ("open tube", shapes.tube([(0, 0, 0), (0, 0.5, 0.5), (0, 0, 1)], 0.1))):
            with self.subTest(name):
                same, _, flat = _edges(m.tris)
                self.assertEqual((same, flat), (0, 0))
                # a sample side face points away from the axis
                (a, b, c) = next(t for t in m.tris if all(abs(p[0]) + abs(p[2]) > 1e-6 for p in t))
                n = shapes._cross(shapes._sub(b, a), shapes._sub(c, a))
                mid = [(a[k] + b[k] + c[k]) / 3 for k in range(3)]
                if name == "open tube":
                    continue   # its axis bends: the closed check above covers its winding
                self.assertGreater(n[0] * mid[0] + n[2] * mid[2], 0)

    def test_a_fully_rounded_loft_is_one_closed_surface(self):
        # the R34's sail panel: round 1 makes two corners of a narrow section meet in one point
        for fine in (False, True):
            m = shapes.loft([[0, 0.025, 0.0, 0.05], [0.5, 0.03, 0.0, 0.07, 0.02], [1, 0.025, 0.0, 0.05]], 1.0, fine)
            self.assertEqual(_edges(m.tris), (0, 0, 0))
            self.assertGreater(_volume(m.tris), 0)

    def test_an_extrude_closed_by_repeating_its_first_point(self):
        # the R34's door glass: a profile that ends where it starts has an edge of no length
        prof = [(0.7, 0.0), (-0.4, 0.0), (-0.45, 0.37), (0.3, 0.34), (0.7, 0.0)]
        m = shapes.extrude(prof, 0.006, "x")
        self.assertEqual(_edges(m.tris), (0, 0, 0))
        self.assertGreater(_volume(m.tris), 0)

    def test_a_mirrored_copy_is_wound_like_its_original(self):
        sc = {"format": "construct-scene", "version": 2, "id": "m", "title": "Mirror",
              "subject": {"category": "object", "summary": "two wings", "accuracy": "generic", "synthetic": True},
              "units": "m", "seed": 1, "sources": [], "facts": [],
              "parts": [{"id": "wing", "role": "mass", "certainty": "inferred", "stage": 0, "mirror": "x",
                         "at": [0.5, 0, 0], "rotate": [0, 20, 10],
                         "shape": {"type": "loft", "sections": [[0, 0.1, 0, 0.2], [0.6, 0.05, 0.02, 0.15]]}}]}
        g = scene.compile_scene(sc, solid=True)
        f = g["fills"]
        sides = {}
        for i in range(0, len(f), 15):
            t = [tuple(f[i + 5 * j + k] for k in range(3)) for j in range(3)]
            sides.setdefault(t[0][0] > 0, []).append(t)
        self.assertEqual(len(sides), 2)
        for right, tris in sides.items():
            self.assertGreater(_volume(tris), 0, "the %s copy is inside out" % ("first" if right else "mirrored"))


if __name__ == "__main__":
    unittest.main()
