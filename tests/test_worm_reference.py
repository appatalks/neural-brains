import io
import sys
import unittest
from pathlib import Path

from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from worm_reference import composite_reference_frame


class WormReferenceTests(unittest.TestCase):
    def test_composite_retains_raw_frame_and_marks_tracked_mask_edge(self):
        raw = Image.new("L", (9, 9), 100)
        mask = Image.new("L", (9, 9), 0)
        for y in range(3, 6):
            for x in range(3, 6):
                mask.putpixel((x, y), 255)

        payload = composite_reference_frame(raw, mask)
        image = Image.open(io.BytesIO(payload)).convert("RGB")

        self.assertEqual(image.size, (9, 9))
        self.assertEqual(image.getpixel((0, 0)), (100, 100, 100))
        self.assertGreater(image.getpixel((3, 4))[1], image.getpixel((3, 4))[0])
        self.assertEqual(image.getpixel((4, 4)), (100, 100, 100))

    def test_composite_rejects_mismatched_source_dimensions(self):
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            composite_reference_frame(Image.new("L", (8, 8)), Image.new("L", (9, 9)))


if __name__ == "__main__":
    unittest.main()
