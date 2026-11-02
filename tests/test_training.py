import random
import re
import unittest

try:
    from scipy import stats as sp
except ImportError:
    sp = None

from training_register import core, create_app
from training_register.core import certificate_code, clean_code, gain_label, learning_gain, new_secret, outcome, paired_summary, reach, t_cdf, verify


class TestCertificates(unittest.TestCase):
    K = "k" * 64

    def test_repeatable(self):
        self.assertEqual(certificate_code(self.K, "Rahima", "Excel", "2026-11-02"), certificate_code(self.K, "Rahima", "Excel", "2026-11-02"))

    def test_any_change_breaks_it(self):
        c = certificate_code(self.K, "Rahima", "Excel", "2026-11-02")
        self.assertTrue(verify(self.K, c, "Rahima", "Excel", "2026-11-02"))
        self.assertFalse(verify(self.K, c, "Rahima B", "Excel", "2026-11-02"))
        self.assertFalse(verify(self.K, c, "Rahima", "Word", "2026-11-02"))
        self.assertFalse(verify(self.K, c, "Rahima", "Excel", "2026-11-03"))

    def test_another_key_cannot_make_it(self):
        self.assertNotEqual(certificate_code(new_secret(), "a", "b", "c"), certificate_code(new_secret(), "a", "b", "c"))

    def test_fields_cannot_run_together(self):
        self.assertNotEqual(certificate_code(self.K, "ab", "c", "d"), certificate_code(self.K, "a", "bc", "d"))

    def test_case_and_spaces_do_not_matter(self):
        self.assertEqual(certificate_code(self.K, " RAHIMA ", "excel", "d"), certificate_code(self.K, "rahima", "Excel ", "d"))

    def test_typed_codes_are_forgiving(self):
        c = certificate_code(self.K, "a", "b", "c")
        self.assertTrue(verify(self.K, c.lower().replace("-", " "), "a", "b", "c"))

    def test_codes_avoid_confusing_letters(self):
        self.assertFalse(set(clean_code("O0I1LU")))
        self.assertTrue(re.fullmatch(r"[2-9A-Z]{4}-[2-9A-Z]{4}-[2-9A-Z]{4}", certificate_code(self.K, "a", "b", "c")))


class TestGain(unittest.TestCase):
    def test_hake(self):
        self.assertEqual(learning_gain(50, 75), 0.5)
        self.assertEqual(learning_gain(80, 90), 0.5)
        self.assertEqual(learning_gain(50, 40), -0.2)
        self.assertIsNone(learning_gain(100, 100))
        with self.assertRaises(ValueError):
            learning_gain(120, 10)

    def test_labels(self):
        self.assertEqual([gain_label(x) for x in (0.8, 0.5, 0.1, None)], ["high", "medium", "low", "n/a"])

    def test_summary(self):
        s = paired_summary([(40, 70), (50, 60), (60, 90), (30, 30)])
        self.assertEqual((s["n"], s["pre"], s["post"], s["change"], s["improved"]), (4, 45, 62.5, 17.5, 0.75))
        self.assertIn("p", s)
        self.assertIsNone(paired_summary([]))

    def test_no_variation_gives_no_p_value(self):
        self.assertNotIn("p", paired_summary([(10, 20), (30, 40)]))

    def test_one_person(self):
        self.assertNotIn("p", paired_summary([(10, 20)]))

    @unittest.skipIf(sp is None, "SciPy is not installed")
    def test_p_value_against_scipy(self):
        rng = random.Random(1)
        for _ in range(50):
            pairs = [(rng.uniform(20, 60), rng.uniform(30, 80)) for _ in range(rng.randint(3, 30))]
            a, b = zip(*pairs)
            self.assertAlmostEqual(paired_summary(pairs)["p"], sp.ttest_rel(b, a).pvalue, places=4)

    def test_t_cdf_known(self):
        self.assertAlmostEqual(t_cdf(2.228, 10), 0.975, places=3)
        self.assertEqual(t_cdf(0, 5), 0.5)


class TestOutcome(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(outcome(5, 5, 70), (True, "completed"))
        self.assertFalse(outcome(3, 5, 70)[0])
        self.assertTrue(outcome(4, 5, 60)[0])
        self.assertIn("below 60", outcome(5, 5, 59)[1])
        self.assertIn("no final", outcome(5, 5, None)[1])
        self.assertFalse(outcome(0, 0, 90)[0])

    def test_reach(self):
        r = reach([{"sex": "F"}, {"sex": "F"}, {"sex": ""}])
        self.assertEqual(r["by_sex"], {"F": 2, "unknown": 1})


class TestApp(unittest.TestCase):
    def setUp(self):
        self.a = create_app(":memory:", "Test Org")
        self.url = self.a.post("/new", title="Excel basics", day="2026-11-02", sessions=5).headers["Location"]
        self.a.post(self.url, name="Rahima", sex="F", pre=40, post=80, attended=5)
        self.a.post(self.url, name="Karim", sex="M", pre=50, post=70, attended=2)
        self.a.post(self.url, name="Nila", sex="F", pre=30, post=55, attended=5)

    def text(self, url):
        return self.a.get(url).body.decode()

    def code(self):
        return self.a.one("SELECT code FROM certificates")

    def test_only_those_who_completed_are_certified(self):
        self.a.post(self.url + "/issue")
        self.assertEqual([r["name"] for r in self.a.rows("SELECT name FROM certificates")], ["Rahima"])
        self.assertIn("Test Org", self.text(self.url + "/certificates"))

    def test_issuing_twice_changes_nothing(self):
        self.a.post(self.url + "/issue")
        self.a.post(self.url + "/issue")
        self.assertEqual(self.a.one("SELECT COUNT(*) FROM certificates"), 1)

    def test_verification(self):
        self.a.post(self.url + "/issue")
        ok = self.a.post("/verify", code=self.code()).body.decode()
        self.assertIn("Valid: Rahima", ok)
        self.assertIn("Valid", self.a.post("/verify", code=self.code().lower().replace("-", "")).body.decode())
        self.assertIn("No certificate", self.a.post("/verify", code="ABCD-EFGH-JKMN").body.decode())

    def test_tampered_record_fails_the_check(self):
        self.a.post(self.url + "/issue")
        self.a.run("UPDATE certificates SET name = 'Someone Else'")
        self.assertIn("No certificate", self.a.post("/verify", code=self.code()).body.decode())

    def test_withdrawn(self):
        self.a.post(self.url + "/issue")
        self.a.run("UPDATE certificates SET revoked = 1")
        self.assertIn("withdrawn", self.a.post("/verify", code=self.code()).body.decode())

    def test_summary_and_caveat_show(self):
        page = self.text(self.url)
        self.assertIn("Learning gain", page)
        self.assertIn("cannot show that the course caused", page)

    def test_scores_stay_in_range(self):
        self.assertEqual(self.a.post(self.url, name="X", pre=500).status, 400)

    def test_update_keeps_one_row(self):
        self.a.post(self.url, name="Rahima", pre=41, post=81, attended=5)
        self.assertEqual(self.a.one("SELECT COUNT(*) FROM people"), 3)


if __name__ == "__main__":
    unittest.main()
