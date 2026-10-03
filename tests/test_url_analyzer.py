import unittest

from services.url_analyzer import analyze_url, defang, extract_urls


class ExtractUrlsTest(unittest.TestCase):
    def test_finds_scheme_and_bare_domains(self):
        text = "Verify at http://sbi-kyc-verify.xyz/login or visit bit.ly/abc today."
        self.assertEqual(extract_urls(text), ["http://sbi-kyc-verify.xyz/login", "bit.ly/abc"])

    def test_ignores_email_addresses(self):
        self.assertEqual(extract_urls("Write to alerts.sbi.update@gmail.com now"), [])

    def test_strips_trailing_punctuation(self):
        self.assertEqual(extract_urls("Go to example.com."), ["example.com"])


class AnalyzeUrlTest(unittest.TestCase):
    def test_brand_lookalike_is_high_risk(self):
        r = analyze_url("http://sbi-kyc-verify.xyz/login")
        self.assertEqual(r["resembles_brand"], "SBI")
        self.assertFalse(r["uses_https"])
        self.assertEqual(r["risk"], "high")

    def test_official_domain_is_not_flagged_as_lookalike(self):
        r = analyze_url("https://www.onlinesbi.sbi/")
        self.assertIsNone(r["resembles_brand"])
        self.assertEqual(r["risk"], "low")

    def test_shortener_detected(self):
        self.assertTrue(analyze_url("https://bit.ly/3abc")["is_shortener"])

    def test_typosquat_detected(self):
        self.assertEqual(analyze_url("https://amazom.in/deal")["resembles_brand"], "Amazon")

    def test_defang_makes_link_unclickable(self):
        self.assertEqual(defang("https://a.com"), "hxxps://a[.]com")


if __name__ == "__main__":
    unittest.main()
