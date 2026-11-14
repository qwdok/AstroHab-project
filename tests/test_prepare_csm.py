"""اختبارات محوّل بيانات NASA (tools/prepare_csm.py) ببيانات مصطنعة. تُتخطى إن لم يكن numpy وscipy مثبتين."""
import csv
import importlib.util
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import numpy  # noqa: F401
    import scipy  # noqa: F401
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

_spec = importlib.util.spec_from_file_location("prepare_csm_under_test", ROOT / "tools" / "prepare_csm.py")
pc = importlib.util.module_from_spec(_spec)
sys.modules["prepare_csm_under_test"] = pc
_spec.loader.exec_module(pc)

HEADER = ["", "TimeSecs", "EEG_FP1", "ECG", "R", "GSR", "Event"]


def make_file(path, seconds=120, bpm=72.0, breaths=15.0, ecg_sign=1, ecg_flat=False, event=None, gsr=700.0, seed=1):
    """تسجيل مصطنع بمعدل 256 هرتز: نبضات ECG منتظمة، تنفس جيبي، وGSR ثابت، وحدث اختياري (بداية، نهاية، رمز)."""
    rnd = random.Random(seed)
    period = 60.0 / bpm
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for i in range(int(seconds * 256)):
            t = i / 256
            phase = (t % period)
            pulse = 400 * math.exp(-((phase - 0.2) ** 2) / (2 * 0.012 ** 2))
            ecg = 0.0 if ecg_flat else -8000 + ecg_sign * (pulse + rnd.gauss(0, 15))
            resp = 800 + 5 * math.sin(2 * math.pi * (breaths / 60) * t) + rnd.gauss(0, 0.2)
            ev = event[2] if event and event[0] <= t < event[1] else 0
            w.writerow([i, f"{t:.6f}", rnd.gauss(0, 20), f"{ecg:.3f}", f"{resp:.3f}", gsr + rnd.gauss(0, 1), ev])


@unittest.skipUnless(HAVE_SCIPY, "numpy and scipy are not installed")
class PrepareCsmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def analyse(self, **kw):
        p = self.tmp / "7_CA.csv"
        make_file(p, **kw)
        return pc.analyse(pc.read_signals(p), 30.0, 10.0)

    def test_file_names(self):
        self.assertEqual(pc.parse_name("26_CA.csv"), (26, "CA"))
        self.assertEqual(pc.parse_name("1f2a3b4c-26_SS.csv"), (26, "SS"))
        self.assertEqual(pc.parse_name("5_Loft.csv"), (5, "LOFT"))
        self.assertIsNone(pc.parse_name("limits.csv"))
        self.assertIsNone(pc.parse_name("26_XX.csv"))

    def test_heart_and_breathing_rates_are_recovered(self):
        rows, notes = self.analyse(bpm=72, breaths=15)
        hr = [r["hr"] for r in rows if r["hr"] is not None]
        br = [r["resp"] for r in rows if r["resp"] is not None]
        self.assertGreaterEqual(len(hr), len(rows) - 1)
        self.assertTrue(all(abs(x - 72) <= 2 for x in hr), hr)
        self.assertTrue(all(abs(x - 15) <= 2 for x in br), br)
        self.assertEqual(notes, [])

    def test_other_rates_and_inverted_ecg(self):
        for bpm, sign in ((55, 1), (95, 1), (64, -1)):
            rows, _ = self.analyse(bpm=bpm, ecg_sign=sign)
            hr = [r["hr"] for r in rows if r["hr"] is not None]
            self.assertTrue(hr and all(abs(x - bpm) <= 2 for x in hr), (bpm, sign, hr))

    def test_flat_ecg_gives_no_heart_rate_but_keeps_breathing(self):
        rows, notes = self.analyse(ecg_flat=True)
        self.assertTrue(all(r["hr"] is None for r in rows))
        self.assertTrue(any(r["resp"] is not None for r in rows))
        self.assertTrue(any("ECG" in n for n in notes))

    def test_pure_noise_does_not_invent_a_heart_rate_in_range(self):
        p = self.tmp / "8_CA.csv"
        rnd = random.Random(3)
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(HEADER)
            for i in range(60 * 256):
                w.writerow([i, f"{i / 256:.6f}", 0, f"{-8000 + rnd.gauss(0, 200):.2f}", 800 + rnd.gauss(0, 1), 700, 0])
        rows, _ = pc.analyse(pc.read_signals(p), 30.0, 10.0)
        good = [r["hr"] for r in rows if r["hr"] is not None]
        self.assertEqual(good, [], "random noise has no regular beats, so no window should pass the regularity check")

    def test_event_codes_become_state_names(self):
        rows, _ = self.analyse(seconds=120, event=(60, 100, 1))
        by_t = {r["t0"]: r["state"] for r in rows}
        self.assertEqual(by_t[0.0], "none")
        self.assertEqual(by_t[70.0], "startle")
        self.assertEqual({r["state"] for r in rows}, {"none", "startle"})
        rows, _ = self.analyse(seconds=60, event=(0, 60, 5))
        self.assertEqual({r["state"] for r in rows}, {"diverted"})
        rows, _ = self.analyse(seconds=60, event=(0, 60, 3))  # الرمز 3 يُعامل كلا حدث حسب الوصف
        self.assertEqual({r["state"] for r in rows}, {"none"})

    def test_short_recording_is_reported_not_crashing(self):
        rows, notes = self.analyse(seconds=10)
        self.assertEqual(rows, [])
        self.assertTrue(notes)

    def test_end_to_end_output_and_sources(self):
        src = self.tmp / "raw"; src.mkdir()
        make_file(src / "3_CA.csv", bpm=60, gsr=600)
        make_file(src / "3_SS.csv", bpm=62, gsr=900, event=(30, 90, 1))
        make_file(src / "4_DA.csv", bpm=80, gsr=500, seed=2)
        make_file(src / "3_Loft.csv", seconds=40)
        (src / "notes.csv").write_text("a,b\n1,2\n")
        out = self.tmp / "out" / "csm_vitals.csv"
        self.assertEqual(pc.main([str(src), "-o", str(out)]), 0)
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(list(rows[0].keys()), pc.OUT_COLUMNS)
        self.assertEqual({r["subject"] for r in rows}, {"3", "4"})  # LOFT وnotes لا يدخلان افتراضياً
        self.assertNotIn("LOFT", {r["recording"] for r in rows})
        sub3 = [float(r["gsr_vs_subject_median"]) for r in rows if r["subject"] == "3"]
        self.assertAlmostEqual(sorted(sub3)[len(sub3) // 2], 1.0, delta=0.01)
        self.assertAlmostEqual(max(sub3) / min(sub3), 900 / 600, delta=0.05)  # الفرق بين التسجيلين محفوظ نسبياً
        text = (out.with_name("csm_vitals_SOURCES.txt")).read_text()
        self.assertIn("data.nasa.gov/dataset/flight-crew-physiological-data-for-crew-state-monitoring", text)
        self.assertIn("no health limits", text)
        self.assertIn("3_CA.csv", text)
        # مع --with-loft يُعالج ملف المحاكاة أيضاً
        out2 = self.tmp / "out2.csv"
        pc.main([str(src), "-o", str(out2), "--with-loft"])
        with open(out2, newline="") as f:
            self.assertIn("LOFT", {r["recording"] for r in csv.DictReader(f)})

    def test_no_matching_files_exits(self):
        empty = self.tmp / "empty"; empty.mkdir()
        with self.assertRaises(SystemExit):
            pc.main([str(empty), "-o", str(self.tmp / "x.csv")])

    def test_output_is_readable_by_the_app_and_no_limits_are_added(self):
        src = self.tmp / "raw2"; src.mkdir()
        make_file(src / "9_CA.csv", seconds=400, bpm=70)
        out = self.tmp / "nasa" / "csm_vitals.csv"
        pc.main([str(src), "-o", str(out)])
        os.environ.setdefault("DB_PATH", str(self.tmp / "app.db"))
        os.environ.update(SERIAL_ENABLED="false", VOICE_ENABLED="false", HTTPS_ENABLED="false")
        spec = importlib.util.spec_from_file_location("astrohab_for_csm", ROOT / "astrohab.py")
        app = importlib.util.module_from_spec(spec); sys.modules["astrohab_for_csm"] = app; spec.loader.exec_module(app)
        app.Config.NASA_DIR = out.parent
        ds = app.list_datasets()
        self.assertEqual([d["file"] for d in ds], ["csm_vitals.csv"])  # ملف المصادر txt لا يظهر كمجموعة بيانات
        labels, values = app.read_column("csm_vitals.csv", "heart_rate_bpm")
        self.assertTrue(values and all(abs(v - 70) <= 2 for v in values))
        lim = app.derive_limits(values, "both", 95, 99)  # الحدود تُشتق من البيانات فقط
        self.assertLessEqual(lim["warning"][0], lim["warning"][1])
        self.assertFalse((out.parent / "limits.csv").exists())


if __name__ == "__main__":
    unittest.main()
