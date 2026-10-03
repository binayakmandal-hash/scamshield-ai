import unittest

from services.schema import AnalysisFormatError, extract_json, normalize_analysis

MSG = "Your account will be blocked within 30 minutes. Verify now."


class SchemaTest(unittest.TestCase):
    def test_extract_json_from_code_fence(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_extract_json_rejects_garbage(self):
        with self.assertRaises(AnalysisFormatError):
            extract_json("not json at all")

    def test_fabricated_evidence_is_marked_and_discounted(self):
        out = normalize_analysis({
            "risk_score": 99,
            "red_flags": [{"title": "Invented", "evidence": "send your password", "severity": "high"}],
            "score_breakdown": [{"signal": "Urgency", "points": 20, "evidence": "within 30 minutes"},
                                {"signal": "Invented", "points": 30, "evidence": "send your password"}],
        }, MSG)
        self.assertFalse(out["red_flags"][0]["evidence_verified"])
        self.assertEqual(out["risk_score"], 35)          # 20 + 30 // 2, not the model's 99
        self.assertEqual(out["risk_level"], "Suspicious")  # level always follows the score

    def test_absolute_claims_softened_and_unsafe_actions_removed(self):
        out = normalize_analysis({
            "risk_score": 50, "red_flags": [], "summary": "This is definitely a scam.",
            "recommended_actions": ["Click the link to check it", "Don't click the link"],
        }, MSG)
        self.assertNotIn("definitely", out["summary"])
        self.assertEqual(out["recommended_actions"], ["Don't click the link"])

    def test_unknown_categories_dropped(self):
        out = normalize_analysis({"risk_score": 0, "red_flags": [], "categories": ["phishing", "Aliens"]}, MSG)
        self.assertEqual(out["categories"], ["Phishing"])


if __name__ == "__main__":
    unittest.main()
