import re
import unittest

from pet_tracker import i18n


class Tables(unittest.TestCase):
    def test_same_keys(self):
        self.assertEqual(set(i18n.VI) - set(i18n.EN), set())
        self.assertEqual(set(i18n.EN) - set(i18n.VI), set())

    def test_same_placeholders(self):
        for k in i18n.VI:
            self.assertEqual(set(re.findall(r"{(\w+)}", i18n.VI[k])), set(re.findall(r"{(\w+)}", i18n.EN[k])), k)

    def test_switch(self):
        i18n.set_lang("en")
        self.assertEqual(i18n.t("count", w=1, r=0, d=0, i=2), "1 needs you · 0 running · 0 done · 2 idle")
        i18n.set_lang("vi")
        self.assertEqual(i18n.t("lane.wait"), "Cần bạn")
        i18n.set_lang("xx")
        self.assertEqual(i18n.lang(), "en")
        i18n.set_lang("vi")


if __name__ == "__main__":
    unittest.main()
