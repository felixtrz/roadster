"""Offline checks for the approval and billing guards; never calls Tripo."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("roadster_tripo", Path(__file__).with_name("client.py"))
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


class ApprovalGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "car.png"
        self.image.write_bytes(b"offline image fixture")
        self.report = self.root / "review.md"
        self.report.write_text("Independent image review fixture")
        self.manifest_path = self.root / "manifest.json"
        self.manifest = {
            "approved": True,
            "images": {view: {"path": str(self.image), "sha256": client.sha256(self.image)}
                       for view in ("front", "back")},
            "judgments": [
                {"judge": "judge-a", "score": 9.2, "report": str(self.report)},
                {"judge": "judge-b", "score": 9.0, "report": str(self.report)},
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def validate(self):
        self.manifest_path.write_text(json.dumps(self.manifest))
        return client.validate_manifest(self.manifest_path, require_approval=True)

    def test_approved_input_produces_semantic_slots(self):
        manifest, params = self.validate()
        payload = client.payload_for(manifest, params, {"front": "token-a", "back": "token-b"})
        self.assertEqual(payload["inputs"], [{"front": "token-a"}, {"back": "token-b"}])
        self.assertEqual(client.estimated_credits(params), 60)

    def test_changed_image_rejected(self):
        self.image.write_bytes(b"changed after judging")
        with self.assertRaises(client.TripoError):
            self.validate()

    def test_missing_approval_rejected(self):
        self.manifest["approved"] = False
        with self.assertRaises(client.TripoError):
            self.validate()

    def test_same_judge_twice_rejected(self):
        self.manifest["judgments"][1]["judge"] = "judge-a"
        with self.assertRaises(client.TripoError):
            self.validate()

    def test_score_below_nine_rejected(self):
        self.manifest["judgments"][1]["score"] = 8.9
        with self.assertRaises(client.TripoError):
            self.validate()

    def test_front_required(self):
        self.manifest["images"]["right"] = self.manifest["images"].pop("front")
        with self.assertRaises(client.TripoError):
            self.validate()

    def test_v3_endpoint_cannot_be_overridden(self):
        offline = client.Client.__new__(client.Client)
        for endpoint in ("https://example.com", "/../../steal", "//example.com"):
            with self.assertRaises(client.TripoError):
                offline.api(endpoint)

    def test_output_download_rejects_external_host_before_egress(self):
        with self.assertRaises(client.TripoError):
            client.download_outputs({"output": {"model_url": "https://example.com/model.glb"}}, self.root)


if __name__ == "__main__":
    unittest.main()
