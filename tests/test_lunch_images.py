"""Regression guard: restaurant photo scraping was intentionally removed."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RemovedRestaurantImagesTests(unittest.TestCase):
    def test_removed_image_api_does_not_reappear(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn('@app.post("/api/lunch/images")', app_source)
        self.assertNotIn("@app.post('/api/lunch/images')", app_source)

    def test_no_restaurant_photo_scraping_module(self):
        self.assertFalse((ROOT / 'collector/lunch_images.py').exists())


if __name__ == '__main__':
    unittest.main()
