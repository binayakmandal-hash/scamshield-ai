import unittest

from services import rule_engine
from services.schema import normalize_analysis
from services.sender_analyzer import analyze_sender
from services.url_analyzer import analyze_urls

BANK = ("From: SBI Alerts <alerts.sbi.update@gmail.com>\nDear Customer, your SBI account will be BLOCKED within "
        "30 minutes. Verify immediately at http://sbi-kyc-verify.xyz/login and enter your account number and OTP.")
NOTICE = ("Dear students, the CA2 internal assessment for BCA Semester V will be held from 10 November. "
          "The timetable is on the college notice board.")


def run(text):
    return normalize_analysis(rule_engine.analyze(text, analyze_urls(text), analyze_sender(text)), text)


class RuleEngineTest(unittest.TestCase):
    def test_bank_scam_scores_very_high(self):
        r = run(BANK)
        self.assertEqual(r["risk_level"], "Very High Risk")
        self.assertIn("Phishing", r["categories"])

    def test_normal_notice_scores_low(self):
        r = run(NOTICE)
        self.assertEqual(r["risk_level"], "Low Risk")
        self.assertEqual(r["red_flags"], [])

    def test_every_evidence_quote_is_in_the_message(self):
        r = run(BANK)
        self.assertTrue(all(f["evidence_verified"] for f in r["red_flags"]))

    def test_score_equals_sum_of_breakdown(self):
        r = run("Congratulations! You have won a lottery. Pay a processing fee to claim your prize today only.")
        self.assertEqual(r["risk_score"], min(100, sum(b["points"] for b in r["score_breakdown"])))

    def test_hindi_message_detected(self):
        r = run("प्रिय ग्राहक, आपका बिजली कनेक्शन आज रात काट दिया जाएगा। तुरंत संपर्क करें।")
        self.assertGreaterEqual(r["risk_score"], 25)

    def test_family_note_languages(self):
        r = run(BANK)
        for lang in ("en", "hi", "bn"):
            note = rule_engine.family_note(r, lang)
            self.assertIn("ScamShield", note)
            self.assertNotIn("http", note)


if __name__ == "__main__":
    unittest.main()
