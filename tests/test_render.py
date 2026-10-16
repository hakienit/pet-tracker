import unittest

from pet_tracker import mascots, theme, vector


class Contrast(unittest.TestCase):
    """Chữ chính và chữ phụ phải đạt 4.5:1 trên nền panel và nền card ở cả hai theme."""

    def test_text_contrast(self):
        for P in (theme.DARK, theme.LIGHT):
            for bg in ("bg", "surf"):
                for fg in ("fg", "fg2", "mut"):
                    self.assertGreaterEqual(theme.contrast(P[fg], P[bg]), 4.5, f"{P['name']} {fg} trên {bg}")

    def test_state_colors_on_tinted_cards(self):
        for P in (theme.DARK, theme.LIGHT):
            for k in ("wait", "run", "done"):
                self.assertGreaterEqual(theme.contrast(P[k], P[k + "Bg"]), 3.0, f"{P['name']} {k}")


class Vector(unittest.TestCase):
    def test_square_coverage(self):
        rows = vector.rasterize(vector.parse('<rect x="1" y="1" width="2" height="2" fill="#ff0000"/>'), 4, 4)
        self.assertEqual(rows[1][1], (255, 0, 0, 255))
        self.assertEqual(rows[0][0][3], 0)

    def test_half_pixel_edge(self):
        rows = vector.rasterize(vector.parse('<rect x="0" y="0" width="1.5" height="4" fill="#000000"/>'), 3, 4)
        self.assertAlmostEqual(rows[2][1][3], 128, delta=2)

    def test_hue_rotate_identity_and_gray(self):
        self.assertEqual(vector.hue_rotate((10, 20, 30), 0), (10, 20, 30))
        self.assertEqual(vector.hue_rotate((128, 128, 128), 90), (128, 128, 128))

    def test_arc_path_closes(self):
        subs = vector.path_points("M10 10a5 5 0 0 1 10 0z")
        self.assertTrue(subs[0][1])
        self.assertAlmostEqual(subs[0][0][-2][0], 20, delta=0.01)


class Mascots(unittest.TestCase):
    def test_every_mascot_and_mood_draws(self):
        for m in mascots.all_mascots():
            for mood in mascots.MOODS:
                rows = mascots.rows(m["id"], mood, 20)
                self.assertTrue(any(px[3] for row in rows for px in row), f"{m['id']} {mood} trống")
        self.assertEqual(len(mascots.all_mascots()), 40)


if __name__ == "__main__":
    unittest.main()
