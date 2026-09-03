from django.test import SimpleTestCase

from life.templatetags.life_ui import get_importance_level


class ImportanceLevelTests(SimpleTestCase):
    def test_importance_bands_cover_the_full_zero_to_one_hundred_range(self):
        cases = {
            0: 1,
            20: 1,
            21: 2,
            50: 2,
            51: 3,
            80: 3,
            81: 4,
            100: 4,
        }

        for importance, expected_level in cases.items():
            with self.subTest(importance=importance):
                self.assertEqual(get_importance_level(importance), expected_level)

    def test_invalid_value_uses_the_lowest_level(self):
        self.assertEqual(get_importance_level(None), 1)
        self.assertEqual(get_importance_level("invalid"), 1)
