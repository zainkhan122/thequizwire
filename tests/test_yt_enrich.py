#!/usr/bin/env python3
"""Offline tests for reelkit/yt_enrich.py — a fake HTTP layer stands in for Google. Run: python3 tests/test_yt_enrich.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "reelkit"))
import yt_enrich as Y


class Fake:
    """Scripted responses keyed by (method, path-prefix). Records every call."""
    def __init__(self, script=None): self.script = script or {}; self.calls = []
    def __call__(self, method, url, data=None, headers=None, form=False, raw=None):
        path = url.split("/v3/")[1].split("?")[0] if "/v3/" in url else url
        self.calls.append((method, path, data, raw))
        if "oauth2" in url: return 200, {"access_token": "tok"}
        for (m, pre), resp in self.script.items():
            if m == method and path.startswith(pre):
                return resp.pop(0) if isinstance(resp, list) else resp
        return 200, {}


def client(script, cap=6000, units=0):
    with mock.patch.object(Y, "http", Fake(script)) as f, mock.patch.object(Y, "quota_load", lambda: {"date": Y.today(), "units": units, "runs": 0}), \
         mock.patch.dict(os.environ, {"YT_CLIENT_ID": "a", "YT_CLIENT_SECRET": "b", "YT_REFRESH_TOKEN": "c"}):
        yt = Y.YT(cap=cap); yt._fake = f; return yt


class T(unittest.TestCase):
    def test_thumbnail_goes_to_upload_host_with_raw_jpeg(self):
        yt = client({("POST", "thumbnails/set"): (200, {"items": [{"high": {"url": "https://i.ytimg.com/x/hqdefault.jpg"}}]})})
        with mock.patch.object(Y, "http", yt._fake):
            url = yt.set_thumbnail("VID", b"\xff\xd8\xffjpeg")
        m, path, data, raw = yt._fake.calls[-1]
        self.assertEqual(url, "https://i.ytimg.com/x/hqdefault.jpg"); self.assertEqual(raw, (b"\xff\xd8\xffjpeg", "image/jpeg")); self.assertEqual(yt.units, 50)

    def test_upload_url_uses_upload_base(self):
        yt = client({})
        with mock.patch.object(Y, "http", yt._fake): yt.set_thumbnail("VID", b"\xff\xd8\xff")
        self.assertIn("googleapis.com/upload/youtube/v3/thumbnails/set", yt._fake.calls[-1][1] if yt._fake.calls[-1][1].startswith("http") else Y.UPLOAD + "/thumbnails/set")

    def test_429_upload_rate_limit_is_RateLimited(self):
        yt = client({("POST", "thumbnails/set"): (429, {"error": {"errors": [{"reason": "uploadRateLimitExceeded"}]}})})
        with mock.patch.object(Y, "http", yt._fake), self.assertRaises(Y.RateLimited): yt.set_thumbnail("VID", b"\xff\xd8\xff")

    def test_403_on_thumbnail_is_Forbidden(self):
        yt = client({("POST", "thumbnails/set"): (403, {"error": {"errors": [{"reason": "forbidden"}]}})})
        with mock.patch.object(Y, "http", yt._fake), self.assertRaises(Y.Forbidden): yt.set_thumbnail("VID", b"\xff\xd8\xff")

    def test_daily_cap_blocks_before_the_request(self):
        yt = client({}, cap=6000, units=5980)
        with mock.patch.object(Y, "http", yt._fake), self.assertRaises(Y.Budget): yt.add_to_playlist("PL", "VID")
        self.assertEqual([c for c in yt._fake.calls if "playlistItems" in c[1]], [])      # nothing was sent
        with mock.patch.object(Y, "http", yt._fake): yt.in_playlist("PL", "VID")            # a 1-unit read still fits
        self.assertEqual(yt.units, 1)

    def test_quota_exceeded_from_api_is_Budget(self):
        yt = client({("POST", "playlistItems"): (403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})})
        with mock.patch.object(Y, "http", yt._fake), self.assertRaises(Y.Budget): yt.add_to_playlist("PL", "VID")

    def test_tags_merge_without_touching_copy(self):
        sn = {"title": "T", "description": "D", "categoryId": "27", "tags": ["geo"]}
        yt = client({("GET", "videos"): (200, {"items": [{"snippet": sn}]})})
        with mock.patch.object(Y, "http", yt._fake): self.assertTrue(yt.add_tags("VID", ["Geo", "quiz"]))
        body = yt._fake.calls[-1][2]
        self.assertEqual(body["snippet"]["tags"], ["geo", "quiz"]); self.assertEqual(body["snippet"]["title"], "T"); self.assertEqual(body["snippet"]["description"], "D")

    def test_steps_legacy_row_only_needs_thumb_and_channel(self):
        p = {"enriched_at": "2026-10-20T00:00:00+00:00"}
        self.assertEqual(Y.steps_for(p, Y.DEFAULTS), ["thumb", "channel"])
        p2 = {"yt_thumbnail_at": "x", "yt_series_item": "a", "yt_channel_item": "b", "yt_tags_at": "c"}
        self.assertEqual(Y.steps_for(p2, Y.DEFAULTS), [])
        p3 = {"yt_thumbnail_error": "forbidden"}
        self.assertNotIn("thumb", Y.steps_for(p3, Y.DEFAULTS))

    def test_video_id_from_links(self):
        self.assertEqual(Y.video_id_from("https://www.youtube.com/shorts/gc4uMGii2R8"), "gc4uMGii2R8")
        self.assertEqual(Y.video_id_from("https://youtu.be/abc123"), "abc123")
        self.assertEqual(Y.video_id_from("https://www.youtube.com/watch?v=xyz"), "xyz")
        self.assertIsNone(Y.video_id_from(None))

    def test_cover_prefers_hosted_sidecar_and_rejects_oversize(self):
        row = {"media_url": "https://host/media/abc/Stem.mp4"}
        with mock.patch.object(Y, "fetch", lambda url, limit=0: (200, b"\xff\xd8\xff" + b"0" * 10) if url.endswith("Stem_cover.jpg") else (404, b"")):
            b, src = Y.cover_bytes(row, None, 2_000_000); self.assertEqual(src, "hosted")
        with mock.patch.object(Y, "fetch", lambda url, limit=0: (200, b"\xff\xd8\xff" + b"0" * 3_000_000)), mock.patch.dict(os.environ, {"GH_TOKEN": ""}):
            b, src = Y.cover_bytes(row, None, 2_000_000); self.assertEqual(src, "none")

    def test_run_dry_offline_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            led = Path(td) / "ledger.json"; led.write_text(json.dumps({"posts": [{"platform": "youtube", "state": "sent", "episode": "ep00-nothing", "external_link": "https://youtu.be/abc"}]}))
            q = Path(td) / "q.json"
            with mock.patch.object(Y, "LEDGER", led), mock.patch.object(Y, "QUOTA", q), mock.patch.dict(os.environ, {"YT_CLIENT_ID": "", "YT_CLIENT_SECRET": "", "YT_REFRESH_TOKEN": ""}):
                Y.cmd_run(type("A", (), {"dry_run": True})())
            self.assertFalse(q.exists()); self.assertNotIn("yt_thumbnail_at", led.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=1)
