"""اختبارات AstroHab (بدون مكتبات إضافية).

التشغيل من مجلد المشروع:
    python -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp()
os.environ.update(DB_PATH=os.path.join(_TMP, "boot.db"), SERIAL_ENABLED="false",
                  VOICE_ENABLED="false", HTTPS_ENABLED="false")
_spec = importlib.util.spec_from_file_location("astrohab_under_test", ROOT / "astrohab.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["astrohab_under_test"] = m
_spec.loader.exec_module(m)

ARABIC = re.compile(r"[؀-ۿ]+")
REMOTE = {"REMOTE_ADDR": "10.0.0.5"}


def limits_for(**metrics):
    """حدود تجريبية: limits_for(bpm=(warn_low, warn_high, danger_low, danger_high))."""
    rows = {}
    for key, (wl, wh, dl, dh) in metrics.items():
        rows[key] = dict(metric=key, warn_low=wl, warn_high=wh, danger_low=dl, danger_high=dh,
                         scale_min=0, scale_max=200, unit="", source="test",
                         replay_file=None, replay_column=None)
    return m.ReferenceStore._build(rows, {})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        m.Config.DB_PATH = os.path.join(self.tmp, "t.db")
        m.Config.REGISTRATION_CODE = ""
        m.Config.ALLOW_REMOTE_FIRST_ADMIN = False
        m.init_db()
        m.engine = m.Engine()
        m.reference.current = limits_for()
        m.reference.replay = {}
        m.reference.checkin = m.ReferenceStore._build({}, {}, m.CHECKIN_INFO)
        for table in (m._login_fails, m._ip_fails, m._register_times, m._chat_times, m._last_message_at):
            table.clear()
        self._sim = m.simulate_step
        self.client = m.app.test_client()

    def tearDown(self):
        m.simulate_step = self._sim

    def freeze(self):
        m.simulate_step = lambda data, replay=None, index=0: None

    def login_page_csrf(self, client=None, **kw):
        client = client or self.client
        html = client.get("/login", **kw).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="(\w+)"', html).group(1)

    def post_login(self, user, password, action="login", extra=None, client=None, **kw):
        client = client or self.client
        data = {"username": user, "password": password, "action": action,
                "csrf_token": self.login_page_csrf(client, **kw)}
        data.update(extra or {})
        return client.post("/login", data=data, **kw)

    def admin_client(self):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user="admin", role="admin", csrf="tok")
        return c


class VitalsTests(Base):
    def test_unconfigured_never_declares_danger(self):
        self.assertEqual(m.evaluate(dict(m.DEFAULTS))[0], "unconfigured")

    def test_thresholds_both_directions(self):
        m.reference.current = limits_for(bpm=(50, 100, 40, 120))
        for value, expected in [(72, "normal"), (105, "warning"), (130, "danger"), (45, "warning"), (35, "danger")]:
            d = dict(m.DEFAULTS, bpm=value)
            self.assertEqual(m.evaluate(d)[0], expected, value)

    def test_reason_names_metric_and_source(self):
        m.reference.current = limits_for(bpm=(50, 100, 40, 120))
        level, reason, metric = m.evaluate_detail(dict(m.DEFAULTS, bpm=130))
        self.assertEqual((level, metric), ("danger", "bpm"))
        self.assertIn("source: test", reason["en"])

    def test_derive_limits(self):
        out = m.derive_limits(list(range(1, 101)), "both", 95, 99)
        self.assertEqual(out["warning"], [5.95, 95.05])
        with self.assertRaises(m.UserError):
            m.derive_limits(list(range(10)), "high", 95, 99)
        with self.assertRaises(m.UserError):
            m.derive_limits(list(range(100)), "high", 99, 95)

    def test_radiation_recovers_gradually(self):
        data = dict(m.DEFAULTS, radiation=0.9)
        seen = []
        with unittest.mock.patch.object(m.random, "random", return_value=0.5):  # لا قفزة جديدة
            for _ in range(4):
                m.simulate_step(data)
                seen.append(data["radiation"])
        self.assertTrue(0.9 > seen[0] > seen[1] > seen[2], seen)  # نزول تدريجي بدل قفزة واحدة
        self.assertGreater(seen[0], 0.4)
        self.assertLessEqual(seen[3], 0.4)  # ثم يعود للنطاق الطبيعي


class CommandTests(Base):
    COMMANDS = {
        "turn off the alarm": "off", "turn the alarm off": "off", "stop the alarm": "off",
        "please silence the buzzer": "off", "can you turn off the alarm?": "off",
        "أوقف الإنذار": "off", "اطفي الانذار": "off", "طفي الجرس": "off", "ممكن تطفي الانذار": "off",
        "turn on the alarm": "on", "sound the alarm": "on", "شغل الانذار": "on", "تشغيل الإنذار": "on",
        "فعّل الانذار": "on",
    }
    NOT_COMMANDS = [
        "why can't I turn off the alarm?", "هل الانذار مطفأ؟", "ليش الانذار ما انطفى", "don't stop the alarm",
        "is the alarm turned off?", "what is the alarm status", "الانذار شغال؟", "الانذار مطفي",
        "how do I turn off the alarm", "when will the alarm stop", "لا تطفي الانذار", "ما حالة الانذار؟",
        "الانذار توقف", "ما حالة المؤشرات؟", "stop and start the alarm", "turn off the lights",
    ]

    def test_real_commands(self):
        for text, expected in self.COMMANDS.items():
            self.assertEqual(m.detect_buzzer_command(text), expected, text)

    def test_questions_and_negations_do_nothing(self):
        for text in self.NOT_COMMANDS:
            self.assertIsNone(m.detect_buzzer_command(text), text)


class EngineTests(Base):
    def danger_engine(self):
        self.freeze()
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        return m.engine

    def commands(self, engine):
        out = []
        while not engine.outbox.empty():
            out.append(engine.outbox.get_nowait())
        return out

    def test_buzzer_follows_any_crew_member_in_danger(self):
        e = self.danger_engine()
        a, b = e.start_session("A"), e.start_session("B")  # B هو النشط الآن
        a["vitals"]["bpm"] = 140
        e.tick()
        self.assertEqual(self.commands(e), [b"BUZZER_ON\n"])
        self.assertEqual(e.desired_buzzer(), 1)
        a["vitals"]["bpm"] = 70  # A يتعافى بينما B هو المستخدم النشط (هذه كانت حالة الجرس العالق)
        for _ in range(m.Config.CALM_TICKS_TO_SILENCE):
            e.tick()
        self.assertEqual(self.commands(e), [b"BUZZER_OFF\n"])
        self.assertEqual((a["buzzer"], b["buzzer"], e.desired_buzzer()), (0, 0, 0))

    def test_manual_silence_acknowledges_everyone_then_auto_resumes(self):
        e = self.danger_engine()
        a, b = e.start_session("A"), e.start_session("B")
        a["vitals"]["bpm"] = 140
        e.tick()
        self.commands(e)
        e.set_buzzer("B", False, manual=True)
        self.assertEqual(a["buzzer"], 0)
        self.assertEqual(self.commands(e), [b"BUZZER_OFF\n"])
        e.tick()  # ما زال الإقرار اليدوي ساري
        self.assertEqual(e.desired_buzzer(), 0)
        a["manual_until"] = 0
        e.tick()  # انتهت المدة والخطر باقٍ
        self.assertEqual(self.commands(e), [b"BUZZER_ON\n"])

    def test_idle_session_expiry_silences_buzzer(self):
        e = self.danger_engine()
        a = e.start_session("A")
        a["vitals"]["bpm"] = 140
        e.tick()
        self.commands(e)
        a["last_seen"] = time.time() - m.Config.SESSION_IDLE_SECONDS - 1
        e.tick()
        self.assertNotIn("A", e.sessions)
        self.assertEqual(self.commands(e), [b"BUZZER_OFF\n"])

    def test_commands_are_not_repeated_without_state_change(self):
        e = self.danger_engine()
        a = e.start_session("A")
        a["vitals"]["bpm"] = 140
        for _ in range(5):
            e.tick()
        self.assertEqual(self.commands(e), [b"BUZZER_ON\n"])

    def test_alert_when_cause_changes_inside_same_level(self):
        self.freeze()
        m.reference.current = limits_for(bpm=(None, 100, None, 120), temp=(None, 38, None, 39))
        e = m.engine
        seen = []
        e.alert_listeners.append(lambda user, level, reason: seen.append((level, reason["en"])))
        s = e.start_session("A")
        s["vitals"]["bpm"] = 130
        e.tick()
        s["vitals"]["bpm"], s["vitals"]["temp"] = 70, 39.5  # ما زال danger لكن السبب تغيّر
        e.tick()
        self.assertEqual(len(seen), 2)
        self.assertIn("heart rate", seen[0][1].lower())
        self.assertIn("body temperature", seen[1][1].lower())

    def test_exercise_bonus_survives_nasa_replay(self):
        m.reference.replay = {"bone_health": [50.0] * 10}
        e = m.engine
        s = e.start_session("A")
        e.tick()
        self.assertEqual(s["vitals"]["bone_health"], 50.0)
        e.register_exercise()
        e.tick()
        self.assertEqual(s["vitals"]["bone_health"], 52.5)


class EnvTests(Base):
    def test_env_file_rules(self):
        work = Path(tempfile.mkdtemp())
        (work / ".env").write_text(
            'REAL=from-file\nEMPTY=from-file\nCOMMENTED=abc # note\nQUOTED="a # b"\nexport EXPORTED=yes\n',
            encoding="utf-8")
        for k in ("REAL", "EMPTY", "COMMENTED", "QUOTED", "EXPORTED"):
            os.environ.pop(k, None)
        os.environ["REAL"], os.environ["EMPTY"] = "from-env", "  "
        old = m.BASE_DIR
        m.BASE_DIR = work
        try:
            m._load_env_file()
        finally:
            m.BASE_DIR = old
        self.assertEqual(os.environ["REAL"], "from-env")       # متغير البيئة الحقيقي يغلب الملف
        self.assertEqual(os.environ["EMPTY"], "from-file")     # القيمة الفارغة لا تمنع الملف
        self.assertEqual(os.environ["COMMENTED"], "abc")       # التعليق لا يدخل القيمة
        self.assertEqual(os.environ["QUOTED"], "a # b")        # داخل الاقتباس يبقى كما هو
        self.assertEqual(os.environ["EXPORTED"], "yes")


class AccountTests(Base):
    def test_first_admin_only_from_this_computer(self):
        r = self.post_login("admin1", "password1", "register", environ_base=REMOTE)
        self.assertEqual(r.status_code, 200)  # رُفض: أُعيد عرض صفحة الدخول
        self.assertFalse(m.users_exist())
        r = self.post_login("admin1", "password1", "register")  # من localhost
        self.assertEqual(r.status_code, 302)
        self.assertEqual(m.list_users()[0]["role"], "admin")

    def test_remote_first_admin_flag(self):
        m.Config.ALLOW_REMOTE_FIRST_ADMIN = True
        r = self.post_login("admin1", "password1", "register", environ_base=REMOTE)
        self.assertEqual(r.status_code, 302)

    def test_later_users_are_commanders_and_invite_code(self):
        m.create_user("admin1", "password1")
        m.Config.REGISTRATION_CODE = "open-sesame"
        r = self.post_login("pilot1", "password1", "register", environ_base=REMOTE, extra={"invite_code": "nope"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("pilot1", [u["username"] for u in m.list_users()])
        c = m.app.test_client()
        r = self.post_login("pilot1", "password1", "register", environ_base=REMOTE, client=c,
                            extra={"invite_code": "open-sesame"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual({u["username"]: u["role"] for u in m.list_users()}["pilot1"], "commander")

    def test_invite_field_only_shown_when_needed(self):
        m.create_user("admin1", "password1")
        self.assertNotIn("invite_code", self.client.get("/login").get_data(as_text=True))
        m.Config.REGISTRATION_CODE = "x"
        self.assertIn("invite_code", self.client.get("/login").get_data(as_text=True))

    def test_password_and_username_rules(self):
        self.assertFalse(m.create_user("someone", "short7!")[0])
        self.assertTrue(m.create_user("someone", "longenough8")[0])
        self.assertFalse(m.create_user('bad"name', "longenough8")[0])
        self.assertFalse(m.create_user("someone", "longenough8")[0])  # مكرر

    def test_single_admin_even_if_two_first_registrations_race(self):
        import threading
        results = []
        barrier = threading.Barrier(2)

        def go(name):
            barrier.wait()
            results.append(m.create_user(name, "password123"))
        threads = [threading.Thread(target=go, args=(n,)) for n in ("first1", "first2")]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(u["role"] for u in m.list_users()), ["admin", "commander"])

    def test_login_lockout_after_failures(self):
        m.create_user("admin1", "password1")
        for _ in range(m.Config.LOGIN_MAX_FAILS):
            self.assertEqual(self.post_login("admin1", "wrong-password").status_code, 200)
        self.assertEqual(self.post_login("admin1", "password1").status_code, 429)  # حتى الصحيحة تُمنع مؤقتاً
        other = m.app.test_client()
        self.assertEqual(self.post_login("admin1", "password1", client=other,
                                         environ_base={"REMOTE_ADDR": "10.9.9.9"}).status_code, 302)

    def test_register_rate_limit(self):
        m.create_user("admin1", "password1")
        codes = [self.post_login(f"user{i}", "x", "register", client=m.app.test_client()).status_code
                 for i in range(m.Config.REGISTER_PER_HOUR + 3)]
        self.assertEqual(codes[:m.Config.REGISTER_PER_HOUR], [200] * m.Config.REGISTER_PER_HOUR)
        self.post_login("userX", "password1", "register", client=m.app.test_client())
        self.assertEqual(len(m.list_users()), 1)  # بعد الحد لا يُنشأ حساب حتى لو كانت البيانات صحيحة

    def test_logout_needs_post_and_token(self):
        m.create_user("admin1", "password1")
        self.post_login("admin1", "password1")
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.assertEqual(self.client.post("/logout").status_code, 400)
        with self.client.session_transaction() as s:
            token = s["csrf"]
        self.assertEqual(self.client.post("/logout", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(self.client.get("/api/data").status_code, 401)


class WebTests(Base):
    def test_security_headers(self):
        r = self.client.get("/login")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_dashboard_has_no_cdn_dependency(self):
        m.create_user("admin1", "password1")
        self.post_login("admin1", "password1")
        html = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("cdn.jsdelivr", html)
        self.assertIn("typeof Chart === 'undefined'", html)

    def test_english_pages_have_no_arabic(self):
        m.create_user("admin1", "password1")
        m.Config.REGISTRATION_CODE = "x"
        c = m.app.test_client()
        with c.session_transaction() as s:
            s["lang"] = "en"
        pages = [c.get("/login").get_data(as_text=True)]
        self.post_login("admin1", "password1", client=c)
        pages += [c.get(p).get_data(as_text=True) for p in ("/", "/history", "/nasa", "/admin", "/body", "/checkin", "/hazards", "/summary", "/crew", "/exercise")]
        for html in pages:
            html = re.sub(r"<style.*?</style>", "", html, flags=re.S)
            self.assertEqual(sorted(set(ARABIC.findall(html))), ["العربية"])  # زر تبديل اللغة فقط

    def test_export_filename_is_sanitised(self):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user='a"b\r\nx', role="commander", csrf="t")
        r = c.get("/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Disposition"], "attachment; filename=astrohab_a_b__x.csv")

    def test_oversized_body_rejected(self):
        c = self.admin_client()
        r = c.post("/api/send", data="x" * 200000, headers={"X-CSRF-Token": "tok", "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 413)


def checkin_limits(**metrics):
    rows = {}
    for key, (wl, wh, dl, dh) in metrics.items():
        rows[key] = dict(metric=key, warn_low=wl, warn_high=wh, danger_low=dl, danger_high=dh,
                         scale_min=0, scale_max=300, unit="", source="test",
                         replay_file=None, replay_column=None)
    return m.ReferenceStore._build(rows, {}, m.CHECKIN_INFO)


class CheckinTests(Base):
    def user_client(self, name="pilot1"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role="commander", csrf="tok")
        return c

    def post(self, c, body, **kw):
        return c.post("/api/checkin", json=body, headers={"X-CSRF-Token": "tok"}, **kw)

    def test_classify_value(self):
        m.reference.checkin = checkin_limits(bp_sys=(None, 129, None, 180))
        spec = m.reference.checkin["bp_sys"]
        self.assertEqual([m.classify_value(spec, v) for v in (None, 120, 135, 190)],
                         ["nodata", "normal", "warning", "danger"])
        self.assertEqual(m.classify_value(m.reference.checkin["sleep"], 6), "unconfigured")

    def test_parse_checkin_rules(self):
        ok = m.parse_checkin({"bp_sys": "120", "bp_dia": 80, "glucose": "", "sleep": "7.25", "mood": 3.4})
        self.assertEqual(ok, {"bp_sys": 120.0, "bp_dia": 80.0, "sleep": 7.2, "mood": 3.0})
        for bad in ({}, {"glucose": "abc"}, {"glucose": 9999}, {"bp_sys": 120}, {"bp_sys": 80, "bp_dia": 90},
                    {"mood": 6}, {"sleep": "nan"}, {"sleep": -1}):
            with self.assertRaises(m.UserError, msg=str(bad)):
                m.parse_checkin(bad)

    def test_escalation_rules(self):
        self.assertIsNone(m.escalation({"a": "unconfigured", "b": "nodata"})["tier"])
        self.assertEqual(m.escalation({"a": "normal", "b": "unconfigured"})["tier"], 0)
        self.assertEqual(m.escalation({"a": "normal", "b": "warning"})["tier"], 1)
        self.assertEqual(m.escalation({"a": "warning", "b": "warning", "c": "warning"})["tier"], 2)
        self.assertEqual(m.escalation({"a": "normal", "b": "danger"})["tier"], 2)

    def test_api_requires_login_and_csrf(self):
        self.assertEqual(self.client.post("/api/checkin", json={"sleep": 7}).status_code, 401)
        c = self.user_client()
        self.assertEqual(c.post("/api/checkin", json={"sleep": 7}).status_code, 400)
        self.assertEqual(self.post(c, {}).status_code, 400)

    def test_checkin_flow_results_alerts_and_history(self):
        m.reference.checkin = checkin_limits(bp_sys=(None, 129, None, 180), bp_dia=(None, 79, None, 120),
                                             sleep=(7, None, None, None))
        c = self.user_client()
        with c.session_transaction() as s:
            s["lang"] = "en"
        r = self.post(c, {"bp_sys": 150, "bp_dia": 95, "sleep": 8, "glucose": 90}).get_json()
        levels = {x["key"]: x["level"] for x in r["results"]}
        self.assertEqual(levels, {"bp_sys": "warning", "bp_dia": "warning", "glucose": "unconfigured", "sleep": "normal"})
        first = r["results"][0]
        self.assertIn("limit 129", first["message"])
        self.assertTrue(first["advice"])
        self.assertEqual(r["escalation"]["tier"], 1)
        r = self.post(c, {"bp_sys": 190, "bp_dia": 100}).get_json()
        self.assertEqual(r["escalation"]["tier"], 2)
        alerts = m.get_alerts("pilot1", 10, "en")
        self.assertEqual(sorted(a["level"] for a in alerts), ["danger", "warning", "warning", "warning"])
        self.assertTrue(any(a["level"] == "danger" for a in alerts))
        chat = m.get_chat("pilot1", 10, "en")
        self.assertTrue(any(x["sender"] == "system" and x["message"].startswith("Alert:") for x in chat))
        rows = c.get("/api/checkins").get_json()["rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["sleep"], rows[1]["sleep"]), (8.0, None))  # القياسات الجزئية تُحفظ كما هي

    def test_error_message_follows_language(self):
        c = self.user_client()
        with c.session_transaction() as s:
            s["lang"] = "en"
        self.assertEqual(self.post(c, {}).get_json()["error"], "Enter at least one measurement.")

    def test_users_are_isolated(self):
        a, b = self.user_client("a1"), self.user_client("b1")
        self.post(a, {"sleep": 6})
        self.assertEqual(len(b.get("/api/checkins").get_json()["rows"]), 0)
        self.assertEqual(len(a.get("/api/checkins").get_json()["rows"]), 1)

    def test_export_csv(self):
        c = self.user_client()
        self.post(c, {"sleep": 6.5, "mood": 4})
        r = c.get("/export_checkins.csv")
        lines = r.get_data(as_text=True).lstrip("\ufeff").splitlines()
        self.assertEqual(lines[0], "time,bp_sys,bp_dia,glucose,sleep,mood")
        self.assertTrue(lines[1].endswith(",,,,6.5,4.0"))
        self.assertIn("astrohab_checkins_pilot1.csv", r.headers["Content-Disposition"])


class BodyTests(Base):
    def setUp(self):
        super().setUp()
        self.c = m.app.test_client()
        with self.c.session_transaction() as s:
            s.update(user="pilot1", role="commander", csrf="tok")

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/body").status_code, 401)
        self.assertEqual(self.client.get("/body").status_code, 302)

    def test_state_covers_every_metric_in_order(self):
        d = self.c.get("/api/body").get_json()
        self.assertEqual(sorted(d["metrics"]), sorted(m.BODY_ORDER))  # JSON يرتب المفاتيح؛ الواجهة تستخدم BODY_ORDER
        self.assertEqual({k: v["kind"] for k, v in d["metrics"].items()},
                         {**{k: "live" for k in m.METRICS}, **{k: "manual" for k in m.CHECKIN_KEYS}})
        self.assertEqual(sorted(d["due"]), sorted(m.CHECKIN_KEYS))      # لا قياس يدوي بعد: الكل مستحق
        self.assertEqual(d["metrics"]["sleep"]["level"], "nodata")
        self.assertIsNone(d["escalation"]["tier"])                      # لا حدود بعد

    def test_levels_due_and_escalation_after_checkin(self):
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        m.engine.start_session("pilot1")["vitals"]["bpm"] = 130
        m.add_checkin("pilot1", {"sleep": 5.0, "mood": 4.0})
        d = self.c.get("/api/body").get_json()
        self.assertEqual(d["metrics"]["bpm"]["level"], "danger")
        self.assertEqual(d["metrics"]["sleep"]["level"], "warning")
        self.assertEqual(d["metrics"]["mood"]["level"], "unconfigured")
        self.assertNotIn("sleep", d["due"])
        self.assertIn("glucose", d["due"])
        self.assertEqual(d["escalation"]["tier"], 2)
        self.assertEqual(d["metrics"]["sleep"]["age_minutes"], 0)

    def test_old_manual_measurement_becomes_due(self):
        m.add_checkin("pilot1", {"glucose": 90.0})
        with m.db() as conn:
            conn.execute("UPDATE checkins SET ts = ?", (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 25 * 3600)),))
        d = self.c.get("/api/body").get_json()
        self.assertIn("glucose", d["due"])
        self.assertGreaterEqual(d["metrics"]["glucose"]["age_minutes"], 25 * 60 - 1)

    def test_content_is_complete_and_consistent(self):
        for key in m.BODY_ORDER:
            for part in ("what", "space", "action", "escalate"):
                for lang in ("ar", "en"):
                    self.assertTrue(m.pick(m.KNOWLEDGE[key][part], lang), (key, part, lang))
        ids = {r["id"] for r in m.BODY_REGIONS}
        covered = {k for r in m.BODY_REGIONS for k in r["metrics"]}
        self.assertEqual(covered, set(m.BODY_ORDER))                    # كل مؤشر ظاهر في جزء من الجسم
        for h in m.BODY_HAZARDS:
            self.assertTrue(set(h["regions"]) <= ids and set(h["metrics"]) <= set(m.BODY_ORDER), h["id"])
        self.assertEqual(len(m.BODY_HAZARDS), 5)                        # المخاطر الخمسة في التحدي
        html = self.c.get("/body").get_data(as_text=True)
        for rid in ids:
            self.assertIn(f'data-region="{rid}"', html)

    def test_limits_csv_import_covers_manual_metrics_only(self):
        nasa = Path(tempfile.mkdtemp())
        # قيم اختبار وهمية فقط؛ المشروع لا يشحن أي حدود
        (nasa / "limits.csv").write_text(
            "metric,warning_low,warning_high,danger_low,danger_high,unit,source\n"
            "bp_sys,,129,,180,,test\nbp_dia,,79,,120,,test\nglucose,69,125,53,,,test\n"
            "sleep,7,,,,,test\nmood,2.5,,1.5,,,test\n", encoding="utf-8")
        m.Config.NASA_DIR = nasa
        rows = m.parse_limits_csv()
        self.assertEqual({r["metric"] for r in rows}, {"bp_sys", "bp_dia", "glucose", "sleep", "mood"})
        self.assertTrue(all(r["source"] for r in rows))
        admin = m.app.test_client()
        with admin.session_transaction() as s:
            s.update(user="admin", role="admin", csrf="tok")
        self.assertEqual(admin.post("/api/reference/import", json={}, headers={"X-CSRF-Token": "tok"}).status_code, 200)
        self.assertTrue(m.reference.checkin["bp_sys"]["configured"])
        self.assertFalse(any(spec["configured"] for spec in m.reference.current.values()))  # الحية لم تتأثر
        self.assertEqual(m.classify_value(m.reference.checkin["bp_sys"], 135), "warning")
        self.assertEqual(m.classify_value(m.reference.checkin["glucose"], 50), "danger")
        self.assertEqual(m.classify_value(m.reference.checkin["glucose"], 65), "warning")
        self.assertEqual(m.classify_value(m.reference.checkin["sleep"], 6.5), "warning")
        self.assertEqual(m.classify_value(m.reference.checkin["mood"], 1), "danger")

    def test_deriving_limits_for_manual_metric_never_becomes_replay(self):
        nasa = Path(tempfile.mkdtemp())
        (nasa / "d.csv").write_text("x\n" + "\n".join(str(5 + i % 7) for i in range(60)), encoding="utf-8")
        m.Config.NASA_DIR = nasa
        admin = m.app.test_client()
        with admin.session_transaction() as s:
            s.update(user="admin", role="admin", csrf="tok")
        r = admin.post("/api/reference/save", headers={"X-CSRF-Token": "tok"}, json={
            "metric": "sleep", "file": "d.csv", "column": "x", "direction": "low",
            "warn_pct": 95, "danger_pct": 99, "replay": True})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(m.reference.checkin["sleep"]["configured"])
        self.assertNotIn("sleep", m.reference.replay)
        self.assertNotIn("sleep", m.reference.current)


class DemoAndTrendTests(Base):
    def user_client(self, name="pilot1"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role="commander", csrf="tok", lang="en")
        return c

    def post(self, c, url, body):
        return c.post(url, json=body, headers={"X-CSRF-Token": "tok"})

    def test_demo_value_lands_in_requested_level_for_any_limit_shape(self):
        shapes = [(None, 129, None, 180), (7, None, None, None), (69, 125, 53, None), (2.5, None, 1.5, None),
                  (None, 100, None, 120), (60, 100, 50, 120), (None, None, 10, None)]
        for wl, wh, dl, dh in shapes:
            spec = checkin_limits(glucose=(wl, wh, dl, dh))["glucose"]
            for level in ("normal", "warning", "danger"):
                v = m.demo_value(spec, level)
                if v is not None:
                    self.assertEqual(m.classify_value(spec, v), level, (wl, wh, dl, dh, level, v))
            self.assertIsNotNone(m.demo_value(spec, "normal"))
        self.assertIsNone(m.demo_value(m.reference.checkin["sleep"], "danger"))  # بلا حدود لا قيمة
        self.assertIsNone(m.demo_value(checkin_limits(sleep=(7, None, None, None))["sleep"], "danger"))

    def test_demo_needs_limits(self):
        c = self.user_client()
        r = self.post(c, "/api/demo", {"action": "start"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("no reference limits", r.get_json()["error"].lower())
        self.assertEqual(self.post(c, "/api/demo", {"action": "x"}).status_code, 400)
        self.assertEqual(c.post("/api/demo", json={"action": "start"}).status_code, 400)  # بلا CSRF

    def run_ticks(self, n):
        for _ in range(n):
            m.engine.tick()

    def test_demo_walks_phases_rings_buzzer_and_leaves_no_trace(self):
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        c = self.user_client()
        m.engine.start_session("pilot1")["vitals"]["bpm"] = 72.0
        self.assertEqual(self.post(c, "/api/demo", {"action": "start"}).status_code, 200)
        n = m.Config.DEMO_PHASE_TICKS
        seen = []
        for _ in range(n * 4):
            m.engine.tick()
            s = m.engine.sessions["pilot1"]
            seen.append((s["level"], s["buzzer"]))
        levels = [seen[i * n + n - 1][0] for i in range(4)]
        self.assertEqual(levels, ["normal", "warning", "danger", "normal"])
        self.assertEqual(seen[3 * n - 1][1], 1)                       # الجرس يعمل في مرحلة الخطر
        self.run_ticks(1)                                              # بعد المراحل الأربع ينتهي العرض وحده
        self.assertFalse(m.engine.demo_info("pilot1")["active"])
        self.assertLess(abs(m.engine.sessions["pilot1"]["vitals"]["bpm"] - 72.0), 15)  # عادت المحاكاة العادية بعد العرض
        self.assertEqual(m.get_alerts("pilot1", 10, "en"), [])         # لا تنبيهات في السجل
        with m.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM vitals").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM checkins").fetchone()[0], 0)

    def test_demo_moves_one_lead_metric_so_recommendation_steps_up(self):
        m.reference.current = limits_for(bpm=(None, 100, None, 120), oxygen=(94, None, 90, None))
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None), bp_sys=(None, 129, None, 180))
        self.assertEqual(m.demo_lead(), "bpm")
        c = self.user_client()
        self.post(c, "/api/demo", {"action": "start"})
        n, tiers = m.Config.DEMO_PHASE_TICKS, []
        for _ in range(n * 4):
            m.engine.tick()
            d = c.get("/api/body").get_json()
            tiers.append((d["escalation"]["tier"], sorted(k for k, v in d["metrics"].items() if v["level"] in ("warning", "danger"))))
        self.assertEqual([tiers[i * n + n - 1] for i in range(4)],
                         [(0, []), (1, ["bpm"]), (2, ["bpm"]), (0, [])])

    def test_demo_overlays_manual_metrics_without_saving_and_banner_shows(self):
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        c = self.user_client()
        self.post(c, "/api/demo", {"action": "start"})
        self.run_ticks(m.Config.DEMO_PHASE_TICKS + 1)                  # المرحلة الثانية: تحذير
        d = c.get("/api/body").get_json()
        self.assertTrue(d["demo"]["active"])
        self.assertEqual(d["metrics"]["sleep"]["level"], "warning")
        self.assertNotIn("sleep", d["due"])
        html = c.get("/body").get_data(as_text=True)
        self.assertIn("Demo mode:", html)
        self.assertIn('action="/demo/stop"', html)
        with m.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM checkins").fetchone()[0], 0)
        r = c.post("/demo/stop", data={"csrf_token": "tok", "next": "//evil.example"})
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/"))   # لا إعادة توجيه خارجية
        self.assertFalse(m.engine.demo_info("pilot1")["active"])
        self.assertNotIn("Demo mode:", c.get("/body").get_data(as_text=True))

    def test_demo_stop_requires_csrf(self):
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        c = self.user_client()
        self.post(c, "/api/demo", {"action": "start"})
        c.post("/demo/stop", data={"csrf_token": "wrong"})
        self.assertTrue(m.engine.demo_info("pilot1")["active"])

    def test_trend_detection_rules(self):
        spec = checkin_limits(sleep=(7, None, None, None))["sleep"]
        spec["scale"] = [0, 12]
        t = m.compute_trend(spec, [8, 7.5, 7, 6.5], "en")
        self.assertEqual((t["direction"], t["readings"], t["from"], t["to"]), ("down", 4, 8, 6.5))
        self.assertIn("from 8 to 6.5", t["message"])
        self.assertFalse(t["toward_limit"])                            # 6.5 تجاوز الحد أصلاً
        t = m.compute_trend(spec, [10, 9, 8], "en")
        self.assertTrue(t["toward_limit"])                             # ما زال طبيعياً لكنه يقترب من الحد
        self.assertIsNone(m.compute_trend(spec, [8, 8.1, 8.2], "en"))   # تغير أقل من 10% من المدى
        self.assertIsNone(m.compute_trend(spec, [8, 7, 7.5, 7.2], "en"))  # ليس اتجاهاً متصلاً
        self.assertIsNone(m.compute_trend(spec, [8, 7], "en"))
        self.assertEqual(m.compute_trend(spec, [8, None, 7.5, 7, 6], "ar")["direction"], "down")
        free = m.reference.checkin["glucose"]                           # بلا حدود: اتجاه محايد فقط
        t = m.compute_trend(free, [80, 100, 130], "en")
        self.assertEqual((t["direction"], t["toward_limit"]), ("up", False))

    def test_trends_reach_api_and_body_but_not_recommendation(self):
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        m.reference.checkin["sleep"]["scale"] = [0, 12]
        c = self.user_client()
        for hours in (10, 9, 8):
            r = self.post(c, "/api/checkin", {"sleep": hours}).get_json()
        self.assertIn("sleep", r["trends"])
        self.assertEqual(r["escalation"]["tier"], 0)                    # الاتجاه لا يرفع التوصية
        self.assertIn("sleep", c.get("/api/checkins").get_json()["trends"])
        self.assertIn("moving toward", c.get("/api/body").get_json()["metrics"]["sleep"]["trend"])


class HazardsAndSummaryTests(Base):
    def user_client(self, name="pilot1", lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role="commander", csrf="tok", lang=lang)
        return c

    def test_pages_require_login(self):
        for url in ("/hazards", "/summary", "/summary.csv"):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_hazard_content_complete_and_numberless(self):
        self.assertEqual({h["id"] for h in m.BODY_HAZARDS}, set(m.HAZARD_DETAILS))
        for hid, d in m.HAZARD_DETAILS.items():
            for part in ("effects", "prevent", "escalate"):
                for lang in ("ar", "en"):
                    text = m.pick(d[part], lang)
                    self.assertTrue(text, (hid, part, lang))
                    self.assertFalse(re.search(r"\d", text), f"medical numbers are not allowed: {hid}/{part}/{lang}")
        page = m.build_summary  # الدالة موجودة
        c = self.user_client()
        html = c.get("/hazards").get_data(as_text=True)
        for h in m.BODY_HAZARDS:
            self.assertIn(m.pick(h["name"], "en"), html)
        self.assertIn("Five hazards", html)

    def test_body_page_accepts_hazard_deep_link(self):
        html = self.user_client().get("/body?hazard=radiation").get_data(as_text=True)
        self.assertIn("URLSearchParams(location.search).get('hazard')", html)

    def test_summary_stats_counts_sources_and_limits(self):
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        for bpm in (80, 110, 130, 90):
            data = dict(m.DEFAULTS); data["bpm"] = bpm
            m.add_vitals("pilot1", data, "normal")
        m.add_checkin("pilot1", {"sleep": 6.0}); m.add_checkin("pilot1", {"sleep": 8.0})
        m.add_alert("pilot1", "danger", m.bi("خطر", "Danger test")); m.add_alert("pilot1", "warning", m.bi("تحذير", "Warn test"))
        s = m.build_summary("pilot1", 7, "en")
        bpm = next(x for x in s["metrics"] if x["key"] == "bpm")
        self.assertEqual((bpm["n"], bpm["min"], bpm["max"], bpm["mean"], bpm["last"]), (4, 80, 130, 102.5, 90))
        self.assertEqual((bpm["warning_n"], bpm["danger_n"]), (1, 1))
        self.assertEqual(bpm["reading_source"], "Simulated")
        self.assertEqual(bpm["limits"], "warning: above 100; danger: above 120")
        sleep = next(x for x in s["metrics"] if x["key"] == "sleep")
        self.assertEqual((sleep["n"], sleep["warning_n"], sleep["reading_source"]), (2, 1, "Entered by the user"))
        self.assertEqual(s["alert_counts"], {"danger": 1, "warning": 1})
        self.assertEqual([a["reason"] for a in s["alerts"]], ["Warn test", "Danger test"])
        self.assertEqual(s["tier"], 0)                                   # آخر القيم طبيعية
        glucose = next(x for x in s["metrics"] if x["key"] == "glucose")
        self.assertEqual((glucose["n"], glucose["limits"], glucose["mean"]), (0, "No limits set", None))

    def test_summary_period_and_user_isolation_and_demo_excluded(self):
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        m.add_checkin("pilot1", {"sleep": 7.0}); m.add_checkin("other", {"sleep": 3.0})
        with m.db() as conn:
            conn.execute("UPDATE checkins SET ts = '2000-01-01 00:00:00' WHERE username = 'pilot1'")
        self.assertEqual(m.build_summary("pilot1", 7, "en")["checkins"], 0)       # خارج الفترة
        self.assertEqual(m.build_summary("other", 7, "en")["checkins"], 1)
        self.assertEqual(m.build_summary("pilot1", 9999, "en")["days"], 90)       # الحد الأقصى
        c = self.user_client()
        m.engine.start_session("pilot1"); m.engine.start_demo("pilot1")
        m.engine.tick()
        self.assertEqual(m.build_summary("pilot1", 7, "en")["readings"], 0)       # العرض لا يظهر في الملخص

    def test_summary_page_and_csv(self):
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        m.add_checkin("pilot1", {"sleep": 5.0})
        c = self.user_client()
        html = c.get("/summary?days=30").get_data(as_text=True)
        for text in ("Summary for the flight surgeon", "Last 30 days", "Entered by the user", "below 7", "Download PDF"):
            self.assertIn(text, html)
        ar = self.user_client(lang="ar").get("/summary").get_data(as_text=True)
        self.assertIn("ملخص لطبيب الطيران", ar)
        r = c.get("/summary.csv?days=7")
        lines = r.get_data(as_text=True).lstrip("\ufeff").splitlines()
        self.assertTrue(lines[0].startswith("metric,unit,kind,reading_source,readings"))
        self.assertEqual(len(lines), 1 + len(m.BODY_ORDER))
        self.assertIn("astrohab_summary_pilot1.csv", r.headers["Content-Disposition"])
        self.assertTrue(any(l.startswith("Hours of sleep,h,manual,Entered by the user,1,5.0") for l in lines))


class CrewTests(Base):
    def setUp(self):
        super().setUp()
        m.create_user("boss1", "password1"); m.create_user("pilot1", "password1"); m.create_user("pilot2", "password1")
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        m.reference.checkin = checkin_limits(sleep=(7, None, None, None))
        m.engine.start_session("boss1"); m.engine.start_session("pilot1")
        m.engine.sessions["boss1"]["vitals"]["bpm"] = 72.0
        m.engine.sessions["pilot1"]["vitals"]["bpm"] = 130.0

    def client_as(self, name, role, lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role=role, csrf="tok", lang=lang)
        return c

    def test_requires_login(self):
        self.assertEqual(self.client.get("/crew").status_code, 302)
        self.assertEqual(self.client.get("/api/crew").status_code, 401)

    def test_members_levels_order_and_aggregate(self):
        d = self.client_as("boss1", "admin").get("/api/crew").get_json()
        by = {x["name"]: x for x in d["members"]}
        self.assertEqual((by["boss1"]["level"], by["pilot1"]["level"]), ("normal", "danger"))
        self.assertEqual(d["members"][0]["name"], "pilot1")                 # الأخطر أولاً
        self.assertEqual((d["tier"], d["active"], d["total"]), (2, 2, 3))
        self.assertEqual(d["counts"], {"danger": 1, "warning": 0, "normal": 1})
        self.assertEqual(by["pilot1"]["metric"], "Heart rate")
        self.assertTrue(by["boss1"]["me"] and by["boss1"]["role"] == "admin")

    def test_inactive_member_uses_last_saved_reading(self):
        data = dict(m.DEFAULTS); data["bpm"] = 110
        m.add_vitals("pilot2", data, "warning")
        by = {x["name"]: x for x in self.client_as("boss1", "admin").get("/api/crew").get_json()["members"]}
        self.assertEqual((by["pilot2"]["active"], by["pilot2"]["level"], by["pilot2"]["buzzer"]), (False, "warning", 0))
        self.assertEqual(by["pilot2"]["seen_minutes"], 0)

    def test_new_user_without_readings(self):
        by = {x["name"]: x for x in self.client_as("boss1", "admin").get("/api/crew").get_json()["members"]}
        self.assertEqual((by["pilot2"]["level"], by["pilot2"]["seen_minutes"], by["pilot2"]["checkin_minutes"]), ("nodata", None, None))

    def test_manual_checkin_raises_member_level(self):
        m.add_checkin("boss1", {"sleep": 4.0})
        by = {x["name"]: x for x in self.client_as("boss1", "admin").get("/api/crew").get_json()["members"]}
        self.assertEqual((by["boss1"]["level"], by["boss1"]["metric"]), ("warning", "Hours of sleep"))
        self.assertEqual(by["boss1"]["checkin_minutes"], 0)

    def test_numbers_only_for_admin_and_owner(self):
        m.add_checkin("pilot1", {"sleep": 6.0})
        member = self.client_as("pilot2", "commander").get("/api/crew").get_json()
        by = {x["name"]: x for x in member["members"]}
        self.assertNotIn("values", by["pilot1"])                              # لا أرقام لزميل
        self.assertNotIn("values", by["boss1"])
        self.assertIn("values", by["pilot2"])                                 # أرقامه هو
        own = self.client_as("pilot1", "commander").get("/api/crew").get_json()
        vals = {x["name"]: x for x in own["members"]}["pilot1"]["values"]
        self.assertEqual((vals["bpm"]["value"], vals["sleep"]["value"]), (130.0, 6.0))
        admin = {x["name"]: x for x in self.client_as("boss1", "admin").get("/api/crew").get_json()["members"]}
        self.assertIn("values", admin["pilot1"])
        self.assertNotIn("130", json.dumps({k: v for k, v in member.items() if k != "members"}))  # لا تسرب في الملخص

    def test_demo_shows_real_readings_to_the_crew(self):
        m.engine.start_demo("boss1")
        for _ in range(m.Config.DEMO_PHASE_TICKS * 3):                         # حتى مرحلة الخطر
            m.engine.tick()
        self.assertEqual(m.engine.sessions["boss1"]["level"], "danger")        # العرض نفسه في خطر
        by = {x["name"]: x for x in self.client_as("pilot1", "commander").get("/api/crew").get_json()["members"]}
        self.assertEqual(by["boss1"]["level"], "normal")                        # لكن الطاقم يرى حالته الحقيقية
        self.assertTrue(by["boss1"]["demo"])

    def test_shared_buzzer_flag_and_member_flag(self):
        m.engine.tick()
        d = self.client_as("boss1", "admin").get("/api/crew").get_json()
        by = {x["name"]: x for x in d["members"]}
        self.assertEqual((d["buzzer"], by["pilot1"]["buzzer"], by["boss1"]["buzzer"]), (1, 1, 0))

    def test_pages_in_both_languages(self):
        en = self.client_as("boss1", "admin").get("/crew").get_data(as_text=True)
        self.assertIn("Crew status", en)
        ar = self.client_as("boss1", "admin", "ar").get("/crew").get_data(as_text=True)
        self.assertIn("حالة الطاقم", ar)


class NasaTests(Base):
    def setUp(self):
        super().setUp()
        self.nasa = Path(tempfile.mkdtemp())
        m.Config.NASA_DIR = self.nasa
        m._dataset_cache.clear()
        (self.nasa / "data.csv").write_text("t,hr\n" + "\n".join(f"{i},{60 + i}" for i in range(40)), encoding="utf-8")
        (self.nasa / "limits.csv").write_text(
            "metric,warning_low,warning_high,danger_low,danger_high,unit,source\nbpm,50,100,40,120,bpm,test\n",
            encoding="utf-8")

    def test_limits_csv_is_not_a_dataset(self):
        self.assertEqual([d["file"] for d in m.list_datasets()], ["data.csv"])
        self.assertIsNone(m.read_column("limits.csv", "warning_low"))

    def test_dataset_listing_is_cached_until_file_changes(self):
        first = m.list_datasets()
        self.assertIs(m.list_datasets()[0], first[0])
        time.sleep(0.01)
        (self.nasa / "data.csv").write_text("t,hr\n1,2\n", encoding="utf-8")
        self.assertEqual(m.list_datasets()[0]["rows"], 1)

    def test_path_traversal_blocked(self):
        self.assertIsNone(m.read_column("../astrohab.py", "x"))
        self.assertIsNone(m.read_column("..", "x"))

    def test_import_keeps_replay_source(self):
        m.save_reference_row("bpm", warn_low=None, warn_high=90.0, danger_low=None, danger_high=99.0,
                             scale_min=0, scale_max=200, unit="", source="old",
                             replay_file="data.csv", replay_column="hr")
        c = self.admin_client()
        r = c.post("/api/reference/import", json={}, headers={"X-CSRF-Token": "tok"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        row = {x["metric"]: x for x in m.get_reference_rows()}["bpm"]
        self.assertEqual((row["warn_high"], row["source"]), (100.0, "test"))
        self.assertEqual((row["replay_file"], row["replay_column"]), ("data.csv", "hr"))


class AssistantTests(Base):
    def setUp(self):
        super().setUp()
        self.prompts = []
        self._worker = m._ai_worker
        m._ai_worker = lambda username, prompt, speak_here=False: self.prompts.append(prompt)
        self._keys = m.Config.API_KEYS
        m.Config.API_KEYS = ["fake-key"]
        m.engine.start_session("pilot")

    def tearDown(self):
        m._ai_worker = self._worker
        m.Config.API_KEYS = self._keys
        super().tearDown()

    def ask(self, text):
        m._last_message_at.clear()
        result = m.ask_assistant("pilot", text)
        time.sleep(0.05)  # الخيط الذي يستدعي _ai_worker
        return result

    def test_followup_gets_conversation_context(self):
        self.ask("What is my heart rate?")
        m.add_chat("pilot", "assistant", "Your heart rate is 72 bpm.")
        self.ask("and why?")
        self.assertIn("Commander: What is my heart rate?", self.prompts[-1])
        self.assertIn("Assistant: Your heart rate is 72 bpm.", self.prompts[-1])
        self.assertIn("not a medical device", self.prompts[-1])

    def test_only_real_commands_touch_the_buzzer(self):
        m.engine.set_buzzer("pilot", True, manual=True)
        self.ask("why can't I turn off the alarm?")
        self.assertEqual(m.engine.sessions["pilot"]["buzzer"], 1)
        self.ask("turn off the alarm")
        self.assertEqual(m.engine.sessions["pilot"]["buzzer"], 0)

    def test_per_user_message_limit(self):
        m.Config.CHAT_PER_10MIN = 3
        try:
            results = [self.ask(f"hello {i}") for i in range(5)]
        finally:
            m.Config.CHAT_PER_10MIN = 30
        self.assertEqual([ok for ok, _ in results], [True, True, True, False, False])

    def test_busy_error_classification(self):
        self.assertTrue(m._is_busy_error(Exception("503 UNAVAILABLE")))
        self.assertFalse(m._is_busy_error(Exception("prompt of 1500 chars is invalid")))

    def test_empty_reply_is_reported_to_user(self):
        m._ai_worker = self._worker
        orig = m._generate
        m._generate = lambda prompt: ""
        try:
            m._ai_worker("pilot", "hi")
        finally:
            m._generate = orig
        self.assertEqual(m.get_chat("pilot", 5, "en")[-1]["sender"], "system")


class LocalAssistantTests(Base):
    """المساعد المحلي: يجيب عند غياب Gemini فقط، ولا يخترع حدوداً أو أرقاماً."""

    def setUp(self):
        super().setUp()
        self._keys = m.Config.API_KEYS
        self._gen = m._generate
        m.engine.start_session("pilot")
        m.user_lang["pilot"] = "en"
        m.reference.current = limits_for(bpm=(50, 100, 40, 120), oxygen=(94, 101, 90, 101))
        m.reference.checkin = checkin_limits(glucose=(70, 140, 55, 200))

    def tearDown(self):
        m.Config.API_KEYS = self._keys
        m._generate = self._gen
        super().tearDown()

    def ask(self, text, wait=0.4):
        m._last_message_at.clear()
        result = m.ask_assistant("pilot", text)
        time.sleep(wait)
        return result

    def last(self, sender="assistant", lang="en"):
        rows = [r for r in m.get_chat("pilot", 20, lang) if r["sender"] == sender]
        return rows[-1]["message"] if rows else ""

    def reply(self, text):
        return m.local_reply("pilot", text)

    def test_no_keys_answers_locally_and_is_tagged(self):
        m.Config.API_KEYS = []
        self.ask("what is my status?", wait=0.05)
        msg = self.last()
        self.assertTrue(msg.startswith("(Local reply)"), msg)
        self.assertTrue(self.last(lang="ar").startswith("(رد محلي)"))

    def test_gemini_failure_falls_back_to_local(self):
        m.Config.API_KEYS = ["fake-key"]

        def boom(prompt):
            raise ConnectionError("Name or service not known")
        m._generate = boom
        self.ask("explain heart rate")
        self.assertIn("(Local reply)", self.last())
        self.assertEqual([r for r in m.get_chat("pilot", 20, "en") if r["sender"] == "system"], [])

    def test_gemini_success_is_not_replaced(self):
        m.Config.API_KEYS = ["fake-key"]
        m._generate = lambda prompt: "Gemini says hello."
        self.ask("what is my status?")
        replies = [r["message"] for r in m.get_chat("pilot", 20, "en") if r["sender"] == "assistant"]
        self.assertEqual(replies, ["Gemini says hello."])

    def test_busy_failure_after_retries_falls_back(self):
        m.Config.API_KEYS = ["fake-key"]

        def busy(prompt):
            raise RuntimeError("503 UNAVAILABLE")
        m._generate = busy
        self.ask("status")
        self.assertIn("(Local reply)", self.last())

    def test_automatic_prompts_do_not_post_local_replies(self):
        m.Config.API_KEYS = []
        m.ask_assistant("pilot", "Tell the commander well done", user_initiated=False)
        time.sleep(0.05)
        self.assertEqual(self.last(), "")

    def test_buzzer_command_still_executes_and_is_confirmed(self):
        m.Config.API_KEYS = []
        m.engine.set_buzzer("pilot", True, manual=True)
        self.ask("turn off the alarm", wait=0.05)
        self.assertEqual(m.engine.sessions["pilot"]["buzzer"], 0)
        self.assertIn("Buzzer turned off", self.last())

    def test_question_about_alarm_does_not_touch_buzzer(self):
        m.Config.API_KEYS = []
        m.engine.set_buzzer("pilot", True, manual=True)
        self.ask("why can't I turn off the alarm?", wait=0.05)
        self.assertEqual(m.engine.sessions["pilot"]["buzzer"], 1)

    def test_status_reports_real_levels(self):
        m.engine.sessions["pilot"]["vitals"]["bpm"] = 130.0
        text, understood = self.reply("how am I doing?")
        self.assertTrue(understood)
        self.assertIn("130", text["en"])
        self.assertIn("danger", text["en"])
        self.assertIn("130", text["ar"])

    def test_metric_value_and_explanation(self):
        m.engine.sessions["pilot"]["vitals"]["bpm"] = 72.0
        text, _ = self.reply("what is my heart rate")
        self.assertIn("72", text["en"])
        text, _ = self.reply("explain heart rate")
        self.assertIn(m.pick(m.KNOWLEDGE["bpm"]["what"], "en"), text["en"])

    def test_arabic_questions_are_understood(self):
        for q in ("وش حالتي؟", "اشرح لي النبض", "ما حدود الأكسجين؟", "متى أتواصل مع الطبيب؟",
                  "ما هي مخاطر الإشعاع؟", "لماذا انطلق الإنذار؟", "ليش الجاذبية خطر"):
            _, ok = self.reply(q)
            self.assertTrue(ok, q)

    def test_limits_come_only_from_loaded_data(self):
        text, _ = self.reply("what are the oxygen limits?")
        self.assertIn("94", text["en"])
        self.assertIn("test", text["en"])
        m.reference.current = limits_for()  # لا حدود
        text, _ = self.reply("what are the oxygen limits?")
        self.assertIn("no limits set", text["en"])
        self.assertNotRegex(text["en"], r"\b9[0-9]\b")

    def test_unconfigured_metric_never_gets_judgement(self):
        m.reference.current = limits_for()
        m.reference.checkin = checkin_limits()
        text, _ = self.reply("how is my heart rate")
        self.assertIn("no limits set", text["en"])
        self.assertNotIn("danger", text["en"].lower().replace("no limits", ""))

    def test_escalation_uses_current_tier(self):
        m.engine.sessions["pilot"]["vitals"]["bpm"] = 130.0
        text, _ = self.reply("when should I contact the flight surgeon?")
        self.assertIn(m.pick(m.ESCALATION[2], "en"), text["en"])

    def test_hazard_answers_use_hazard_texts(self):
        text, _ = self.reply("tell me about the isolation hazard")
        self.assertIn(m.pick(m.HAZARD_DETAILS["isolation"]["effects"], "en"), text["en"])
        text, _ = self.reply("what are the five hazards")
        self.assertIn("Gravity fields", text["en"])

    def test_alarm_reason_matches_snapshot(self):
        text, _ = self.reply("why did the alarm go off?")
        reason = m.pick(m.engine.snapshot("pilot")["reason"], "en")
        self.assertIn(reason, text["en"])

    def test_checkin_due_and_trend_questions(self):
        text, ok = self.reply("what check-in is due?")
        self.assertTrue(ok)
        self.assertIn("Blood glucose", text["en"])
        text, ok = self.reply("any trends?")
        self.assertTrue(ok)

    def test_unknown_question_says_so_and_lists_examples(self):
        text, understood = self.reply("blorf wibble")
        self.assertFalse(understood)
        self.assertIn("did not understand", text["en"])
        self.assertIn("Try:", text["en"])

    def test_english_page_has_no_arabic_in_local_reply_text(self):
        text, _ = self.reply("help")
        self.assertNotRegex(text["en"], "[\u0600-\u06FF]")


class EarlyWarningTests(Base):
    def setUp(self):
        super().setUp()
        m.reference.checkin = checkin_limits(sleep=(7, None, 5, None))

    def trends(self, values):
        m.reference.checkin["sleep"]["scale"] = [0, 12]  # مدى عرض واقعي حتى يُعلن الاتجاه
        for v in values:
            m.add_checkin("pilot", {"sleep": v})
        return m.checkin_trends("pilot", "en")

    def test_early_warning_when_limit_is_near(self):
        t = self.trends([9.0, 8.4, 7.8, 7.4])["sleep"]
        self.assertIsNotNone(t["early"])
        self.assertEqual(t["early"]["kind"], "warning")
        self.assertIn("7", t["early"]["message"])
        self.assertIn(t["early"]["message"], t["message"])

    def test_no_early_warning_when_limit_is_far(self):
        t = self.trends([12.0, 11.4, 10.8, 10.2])["sleep"]
        self.assertIsNone(t["early"])

    def test_no_early_warning_without_limits(self):
        m.reference.checkin = checkin_limits()
        t = self.trends([9.0, 8.4, 7.8, 7.4])["sleep"]
        self.assertIsNone(t["early"])

    def test_no_early_warning_after_limit_is_crossed(self):
        t = self.trends([9.0, 8.0, 7.0, 6.5])["sleep"]
        self.assertIsNone(t["early"])


class CrewAlertTests(Base):
    def setUp(self):
        super().setUp()
        m.create_user("boss1", "password1"); m.create_user("pilot1", "password1"); m.create_user("pilot2", "password1")
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        for u in ("boss1", "pilot1", "pilot2"):
            m.engine.start_session(u)
            m.engine.sessions[u]["vitals"]["bpm"] = 72.0

    def client_as(self, name, role="commander", lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role=role, csrf="tok", lang=lang)
        return c

    def post(self, c, url, body):
        return c.post(url, json=body, headers={"X-CSRF-Token": "tok"})

    def alerts(self, name):
        return self.client_as(name).get("/api/crew/alerts").get_json()

    def test_requires_login_and_csrf(self):
        self.assertEqual(self.client.get("/api/crew/alerts").status_code, 401)
        c = self.client_as("pilot1")
        self.assertEqual(c.post("/api/crew/help", json={"action": "call"}).status_code, 400)
        self.assertEqual(c.post("/api/crew/ack", json={"target": "x"}).status_code, 400)

    def test_quiet_when_everyone_is_fine(self):
        self.assertEqual(self.alerts("boss1")["alerts"], [])

    def test_member_in_danger_is_visible_to_the_others_without_numbers(self):
        m.engine.sessions["pilot1"]["vitals"]["bpm"] = 140.0
        d = self.alerts("pilot2")
        self.assertEqual([(a["user"], a["kind"], a["metric"]) for a in d["alerts"]], [("pilot1", "danger", "Heart rate")])
        self.assertNotIn("140", str(d))

    def test_inactive_member_in_danger_does_not_alert(self):
        data = dict(m.DEFAULTS); data["bpm"] = 150
        m.add_vitals("pilot3", data, "danger")
        m.create_user("pilot3", "password1")
        self.assertEqual(self.alerts("boss1")["alerts"], [])

    def test_help_call_flow(self):
        c1 = self.client_as("pilot1")
        self.assertTrue(self.post(c1, "/api/crew/help", {"action": "call"}).get_json()["help_active"])
        seen = self.alerts("pilot2")["alerts"]
        self.assertEqual([(a["user"], a["kind"], a["acks"]) for a in seen], [("pilot1", "help", [])])
        self.assertEqual(m.get_alerts("pilot1")[0]["level"], "danger")
        mine = self.alerts("pilot1")
        self.assertTrue(mine["help_active"] and mine["alerts"][0]["me"])
        self.assertFalse(self.post(c1, "/api/crew/help", {"action": "cancel"}).get_json()["help_active"])
        self.assertEqual(self.alerts("pilot2")["alerts"], [])

    def test_repeated_call_does_not_duplicate_the_alert_record(self):
        c1 = self.client_as("pilot1")
        for _ in range(3):
            self.post(c1, "/api/crew/help", {"action": "call"})
        self.assertEqual(len(m.get_alerts("pilot1")), 1)

    def test_ack_is_recorded_and_cleared_when_the_call_ends(self):
        self.post(self.client_as("pilot1"), "/api/crew/help", {"action": "call"})
        self.assertEqual(self.post(self.client_as("pilot2"), "/api/crew/ack", {"target": "pilot1"}).status_code, 200)
        a = self.alerts("boss1")["alerts"][0]
        self.assertEqual(a["acks"], ["pilot2"])
        self.assertTrue(self.alerts("pilot2")["alerts"][0]["acked"])
        self.post(self.client_as("pilot1"), "/api/crew/help", {"action": "cancel"})
        self.alerts("boss1")
        self.post(self.client_as("pilot1"), "/api/crew/help", {"action": "call"})
        self.assertEqual(self.alerts("boss1")["alerts"][0]["acks"], [])

    def test_cannot_ack_yourself_or_a_healthy_member(self):
        self.post(self.client_as("pilot1"), "/api/crew/help", {"action": "call"})
        self.assertEqual(self.post(self.client_as("pilot1"), "/api/crew/ack", {"target": "pilot1"}).status_code, 404)
        self.assertEqual(self.post(self.client_as("pilot2"), "/api/crew/ack", {"target": "boss1"}).status_code, 404)

    def test_help_call_expires(self):
        self.post(self.client_as("pilot1"), "/api/crew/help", {"action": "call"})
        m.engine.help_calls["pilot1"]["ts"] -= m.Config.HELP_CALL_MINUTES * 60 + 5
        self.assertEqual(self.alerts("pilot2")["alerts"], [])

    def test_pages_carry_the_sos_button_in_both_languages(self):
        for lang, word in (("en", "Call for help"), ("ar", "نداء مساعدة")):
            html = self.client_as("pilot1", lang=lang).get("/").get_data(as_text=True)
            self.assertIn(word, html)


class PdfTests(Base):
    def client_as(self, name="pilot", lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role="commander", csrf="tok", lang=lang)
        return c

    def test_requires_login(self):
        self.assertEqual(self.client.get("/summary.pdf").status_code, 302)

    def test_download_in_both_languages(self):
        m.engine.start_session("pilot")
        m.add_checkin("pilot", {"sleep": 6.5})
        for lang in ("en", "ar"):
            r = self.client_as(lang=lang).get("/summary.pdf?days=7")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.mimetype, "application/pdf")
            self.assertTrue(r.data.startswith(b"%PDF"))
            self.assertIn("attachment", r.headers["Content-Disposition"])
            self.assertIn(".pdf", r.headers["Content-Disposition"])

    def test_summary_page_links_to_the_pdf(self):
        html = self.client_as().get("/summary?days=30").get_data(as_text=True)
        self.assertIn("/summary.pdf?days=30", html)
        self.assertIn("Download PDF", html)
        self.assertNotIn("printBtn", html)

    def test_arabic_letters_are_joined(self):
        self.assertEqual(m.shape_arabic("لا"), "\ufefb")
        self.assertEqual(m.shape_arabic("بب"), "\ufe91\ufe90")  # بداية ثم نهاية
        self.assertEqual(m.shape_arabic("سلام"), "\ufeb3\ufefc\ufee1")  # لام-ألف في النهاية
        self.assertEqual(m.shape_arabic("ء"), "\ufe80")
        self.assertEqual(m.shape_arabic("يغيّران"), m.shape_arabic("يغيران"))  # التشكيل يُحذف

    def test_bidi_keeps_latin_and_numbers_left_to_right(self):
        self.assertEqual(m.bidi_visual("abc 12.5", False), "abc 12.5")
        out = m.bidi_visual("ab \u0628\u0628 12.5", True)
        self.assertIn("12.5", out)
        self.assertIn("ab", out)
        self.assertTrue(out.index("12.5") < out.index("ab"))  # الأرقام تأتي أولاً يسار الصفحة في سياق RTL
        self.assertEqual(m.bidi_visual("(\u0628)", True), "(\u0628)")  # الأقواس تنعكس مع الاتجاه

    def test_missing_reportlab_is_reported_not_crashing(self):
        original = m.build_summary_pdf
        def boom(s, lang):
            raise ImportError("reportlab")
        m.build_summary_pdf = boom
        try:
            r = self.client_as().get("/summary.pdf")
        finally:
            m.build_summary_pdf = original
        self.assertEqual(r.status_code, 503)
        self.assertIn(b"reportlab", r.data)


class RoleTests(Base):
    def setUp(self):
        super().setUp()
        m.create_user("boss1", "password1"); m.create_user("pilot1", "password1"); m.create_user("doc1", "password1")
        m.set_user_role("doc1", "doctor")
        m.reference.current = limits_for(bpm=(None, 100, None, 120))
        m.engine.start_session("boss1"); m.engine.start_session("pilot1")
        m.engine.sessions["pilot1"]["vitals"]["bpm"] = 130.0

    def client_as(self, name, role, lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role=role, csrf="tok", lang=lang)
        return c

    def post(self, c, url, body):
        return c.post(url, json=body, headers={"X-CSRF-Token": "tok"})

    def test_set_user_role_rules(self):
        self.assertEqual(m.set_user_role("pilot1", "doctor"), (True, ""))
        self.assertEqual(m.get_role("pilot1"), "doctor")
        self.assertEqual(m.set_user_role("pilot1", "commander"), (True, ""))
        self.assertEqual(m.set_user_role("boss1", "doctor"), (False, "admin"))
        self.assertEqual(m.set_user_role("pilot1", "admin"), (False, "bad_role"))
        self.assertEqual(m.set_user_role("nobody", "doctor"), (False, "no_user"))

    def test_only_admin_can_change_roles(self):
        self.assertEqual(self.post(self.client_as("pilot1", "commander"), "/api/admin/role",
                                   {"username": "pilot1", "role": "doctor"}).status_code, 403)
        self.assertEqual(self.post(self.client_as("doc1", "doctor"), "/api/admin/role",
                                   {"username": "pilot1", "role": "doctor"}).status_code, 403)
        c = self.client_as("boss1", "admin")
        self.assertEqual(c.post("/api/admin/role", json={"username": "pilot1", "role": "doctor"}).status_code, 400)  # بلا CSRF
        self.assertEqual(self.post(c, "/api/admin/role", {"username": "pilot1", "role": "doctor"}).status_code, 200)
        self.assertEqual(m.get_role("pilot1"), "doctor")
        self.assertEqual(self.post(c, "/api/admin/role", {"username": "boss1", "role": "doctor"}).status_code, 400)
        self.assertEqual(self.post(c, "/api/admin/role", {"username": "ghost", "role": "doctor"}).status_code, 404)

    def test_admin_page_lists_roles_in_both_languages(self):
        html = self.client_as("boss1", "admin").get("/admin").get_data(as_text=True)
        self.assertIn("Flight surgeon", html)
        ar = self.client_as("boss1", "admin", "ar").get("/admin").get_data(as_text=True)
        self.assertIn("طبيب طيران", ar)

    def test_role_change_applies_to_an_open_session(self):
        c = self.client_as("pilot1", "commander")
        self.assertEqual(c.get("/body").status_code, 200)
        m.set_user_role("pilot1", "doctor")
        r = c.get("/body")
        self.assertEqual((r.status_code, r.headers["Location"].endswith("/crew")), (302, True))

    def test_doctor_is_read_only(self):
        c = self.client_as("doc1", "doctor")
        for path in ("/", "/body", "/checkin", "/history", "/exercise", "/admin"):
            r = c.get(path)
            self.assertEqual((path, r.status_code), (path, 302))
            self.assertTrue(r.headers["Location"].endswith("/crew"))
        for url, body in (("/api/buzzer", {"state": True}), ("/api/checkin", {"sleep": 6}), ("/api/send", {"prompt": "hi"}),
                          ("/api/demo", {"action": "start"}), ("/api/exercise", {"minutes": 20}), ("/api/crew/help", {"action": "call"})):
            self.assertEqual(self.post(c, url, body).status_code, 403, url)
        for path in ("/crew", "/summary", "/hazards", "/nasa", "/api/crew", "/api/crew/alerts"):
            self.assertEqual(c.get(path).status_code, 200, path)
        self.assertNotIn("doc1", m.engine.sessions)

    def test_doctor_sees_values_but_is_not_crew(self):
        d = self.client_as("doc1", "doctor").get("/api/crew").get_json()
        self.assertEqual(sorted(x["name"] for x in d["members"]), ["boss1", "pilot1"])
        self.assertEqual(d["total"], 2)
        pilot = next(x for x in d["members"] if x["name"] == "pilot1")
        self.assertEqual(pilot["values"]["bpm"]["value"], 130.0)
        other = self.client_as("pilot1", "commander").get("/api/crew").get_json()
        self.assertNotIn("values", next(x for x in other["members"] if x["name"] == "boss1"))

    def test_doctor_sees_alerts_but_cannot_acknowledge_or_call(self):
        d = self.client_as("doc1", "doctor").get("/api/crew/alerts").get_json()
        item = d["alerts"][0]
        self.assertEqual((item["user"], item["kind"], item["can_ack"]), ("pilot1", "danger", False))
        self.assertEqual(self.post(self.client_as("doc1", "doctor"), "/api/crew/ack", {"target": "pilot1"}).status_code, 404)
        self.assertTrue(self.client_as("boss1", "admin").get("/api/crew/alerts").get_json()["alerts"][0]["can_ack"])

    def test_doctor_summary_of_a_crew_member(self):
        m.add_checkin("pilot1", {"sleep": 6.5})
        c = self.client_as("doc1", "doctor")
        html = c.get("/summary?user=pilot1").get_data(as_text=True)
        self.assertIn("<strong>Account:</strong> pilot1", html)
        self.assertIn('id="memberSel"', html)
        self.assertIn("user=pilot1", html)
        default = c.get("/summary").get_data(as_text=True)
        self.assertIn("<strong>Account:</strong> boss1", default)  # أول فرد من الطاقم
        pdf = c.get("/summary.pdf?user=pilot1")
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("astrohab_summary_pilot1", pdf.headers["Content-Disposition"])
        csv_ = c.get("/summary.csv?user=pilot1")
        self.assertIn("astrohab_summary_pilot1", csv_.headers["Content-Disposition"])

    def test_commander_cannot_open_someone_elses_summary(self):
        html = self.client_as("pilot1", "commander").get("/summary?user=boss1").get_data(as_text=True)
        self.assertIn("<strong>Account:</strong> pilot1", html)
        self.assertNotIn('id="memberSel"', html)

    def test_doctor_pages_in_english_have_no_arabic(self):
        import re as _re
        c = self.client_as("doc1", "doctor")
        for path in ("/crew", "/summary?user=pilot1", "/hazards"):
            text = _re.sub(r"العربية", "", c.get(path).get_data(as_text=True))
            self.assertIsNone(_re.search("[\u0600-\u06FF]", text), path)


class ExerciseTests(Base):
    """زر التمرين يؤكد الجلسة، ثم يسجّل المستخدم مدتها ونوعها؛ لا إدخال يدوي مستقل."""
    def setUp(self):
        super().setUp()
        m.engine.start_session("pilot")

    def client_as(self, role="commander", lang="en", user="pilot"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=user, role=role, csrf="tok", lang=lang)
        return c

    def post(self, c, body):
        return c.post("/api/exercise", json=body, headers={"X-CSRF-Token": "tok"})

    def test_button_press_is_logged_and_waits_for_details(self):
        m._on_exercise("pilot")
        d = self.client_as().get("/api/exercise").get_json()
        self.assertEqual([r["kind"] for r in d["recent"]], ["button"])
        self.assertEqual(len(d["pending"]), 1)
        self.assertEqual(d["week"]["sessions"], 1)

    def test_details_complete_the_button_session(self):
        m._on_exercise("pilot")
        c = self.client_as()
        pid = c.get("/api/exercise").get_json()["pending"][0]["id"]
        d = self.post(c, {"id": pid, "minutes": 35, "activities": ["treadmill_continuous", "back_squat"], "note": " easy pace "}).get_json()
        self.assertEqual(d["pending"], [])
        self.assertEqual((d["week"]["sessions"], d["week"]["minutes"], d["week"]["days_active"]), (1, 35, 1))
        self.assertEqual((d["recent"][0]["minutes"], d["recent"][0]["activity"], d["recent"][0]["note"]),
                         (35, "Treadmill (T2): continuous, Back squat", "easy pace"))

    def test_no_standalone_manual_entry(self):
        c = self.client_as()
        self.assertEqual(self.post(c, {"minutes": 30, "activities": ["deadlift"]}).status_code, 400)
        self.assertEqual(self.post(c, {"id": 999, "minutes": 30, "activities": ["deadlift"]}).status_code, 404)
        self.assertEqual(c.get("/api/exercise").get_json()["recent"], [])

    def test_validation_and_csrf(self):
        m._on_exercise("pilot")
        c = self.client_as()
        pid = c.get("/api/exercise").get_json()["pending"][0]["id"]
        ok = ["deadlift"]
        for bad in (0, 301, "abc", None, -5):
            self.assertEqual(self.post(c, {"id": pid, "minutes": bad, "activities": ok}).status_code, 400, bad)
        for bad in ([], ["swim"], ["deadlift", "deadlift"], "deadlift", None, ["deadlift", "swim"]):
            self.assertEqual(self.post(c, {"id": pid, "minutes": 10, "activities": bad}).status_code, 400, bad)
        self.assertEqual(self.post(c, {"id": pid, "minutes": 10, "activities": ok, "note": "x" * 121}).status_code, 400)
        self.assertEqual(c.post("/api/exercise", json={"id": pid, "minutes": 10, "activities": ok}).status_code, 400)
        self.assertEqual(len(c.get("/api/exercise").get_json()["pending"]), 1)  # لم يتغير شيء

    def test_session_is_completed_once_and_only_by_its_owner(self):
        m._on_exercise("pilot")
        c = self.client_as()
        pid = c.get("/api/exercise").get_json()["pending"][0]["id"]
        other = self.client_as(user="someone")
        self.assertEqual(self.post(other, {"id": pid, "minutes": 10, "activities": ["heel_raise"]}).status_code, 404)
        self.assertEqual(self.post(c, {"id": pid, "minutes": 10, "activities": ["heel_raise"]}).status_code, 200)
        self.assertEqual(self.post(c, {"id": pid, "minutes": 50, "activities": ["bench_press"]}).status_code, 404)  # مرة واحدة

    def test_pending_expires_after_details_window(self):
        m._on_exercise("pilot")
        old = m.Config.EXERCISE_DETAILS_HOURS
        try:
            m.Config.EXERCISE_DETAILS_HOURS = 0
            time.sleep(1.1)
            self.assertEqual(m.pending_exercises("pilot"), [])
        finally:
            m.Config.EXERCISE_DETAILS_HOURS = old

    def test_alert_strip_shows_log_prompt_until_details_saved(self):
        m._on_exercise("pilot")
        c = self.client_as()
        kinds = lambda: [a["kind"] for a in c.get("/api/crew/alerts").get_json()["alerts"]]
        self.assertIn("log", kinds())
        pid = c.get("/api/exercise").get_json()["pending"][0]["id"]
        self.post(c, {"id": pid, "minutes": 20, "activities": ["sumo_squat"]})
        self.assertNotIn("log", kinds())

    def test_doctor_sees_log_but_gets_no_prompt(self):
        for name in ("boss9", "pilot", "doc9"):
            m.create_user(name, "password1")
        m.set_user_role("doc9", "doctor")
        m.add_exercise("pilot", 25, "button", "cycle_interval,deadlift", "legs")
        m.add_exercise("pilot", None, "button")
        s = m.build_summary("pilot", 7, "en")
        self.assertEqual(s["exercise"]["sessions"], 2)
        self.assertEqual(s["exercise"]["minutes"], 25)
        self.assertEqual([(e["minutes"], e["activity"], e["note"]) for e in s["exercise"]["log"]],
                         [(None, "", ""), (25, "Cycle ergometer (CEVIS): interval, Deadlift", "legs")])
        d = self.client_as(role="doctor", user="doc9")
        self.assertNotIn("log", [a["kind"] for a in d.get("/api/crew/alerts").get_json()["alerts"]])
        html = d.get("/summary?user=pilot").get_data(as_text=True)
        self.assertIn("Cycle ergometer (CEVIS): interval, Deadlift", html)
        self.assertIn("legs", html)
        self.assertIn("Details not logged", html)

    def test_exercise_appears_in_summary_and_pdf(self):
        m.add_exercise("pilot", 30, "button", "cycle_continuous"); m.add_exercise("pilot", None, "button")
        s = m.build_summary("pilot", 7, "en")
        self.assertEqual({k: s["exercise"][k] for k in ("sessions", "minutes", "days_active")},
                         {"sessions": 2, "minutes": 30, "days_active": 1})
        html = self.client_as().get("/summary").get_data(as_text=True)
        self.assertIn("Exercise: 2 sessions confirmed by the button (30 minutes logged)", html)
        self.assertTrue(m.build_summary_pdf(s, "en").startswith(b"%PDF"))
        sa = m.build_summary("pilot", 7, "ar")
        self.assertTrue(m.build_summary_pdf(sa, "ar").startswith(b"%PDF"))

    def test_exercise_is_per_user(self):
        m.add_exercise("someone", 40, "button", "cycle_continuous")
        d = self.client_as().get("/api/exercise").get_json()
        self.assertEqual((d["recent"], d["pending"]), ([], []))

    def test_old_database_gets_new_columns(self):
        import sqlite3
        path = m.Config.DB_PATH
        con = sqlite3.connect(path)
        con.execute("DROP TABLE exercises")
        con.execute("CREATE TABLE exercises (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, ts TEXT NOT NULL, "
                    "minutes INTEGER, kind TEXT NOT NULL DEFAULT 'manual')")
        con.commit(); con.close()
        m.init_db()
        self.assertEqual(m.add_exercise("pilot", 5, "button", "deadlift", "x") > 0, True)

    def test_exercise_names_are_english_only_nasa_names(self):
        names = set(m.EXERCISE_TYPES.values())
        for must in ("Back squat", "Front squat", "Single-leg squat", "Sumo squat", "Deadlift", "Romanian deadlift",
                     "Sumo deadlift", "Heel raise", "Single-leg heel raise", "Bench press", "Shoulder press",
                     "Bent-over row", "Upright row", "Single leg knee extension"):
            self.assertIn(must, names)
        self.assertTrue(all(n.isascii() for n in names))
        d = self.client_as(lang="ar").get("/api/exercise").get_json()
        self.assertEqual([g["key"] for g in d["groups"]], ["aerobic", "resistance"])
        self.assertEqual([g["label"] for g in d["groups"]], ["هوائي", "مقاومة (ARED)"])
        self.assertEqual(sum(len(g["items"]) for g in d["groups"]), len(m.EXERCISE_TYPES))

    def test_page_renders_in_both_languages(self):
        self.assertIn("Exercise log", self.client_as().get("/exercise").get_data(as_text=True))
        self.assertIn("سجل التمارين", self.client_as(lang="ar").get("/exercise").get_data(as_text=True))


class NasaRiskTests(Base):
    """ربط المخاطر والمؤشرات بصفحات برنامج أبحاث الإنسان في ناسا (عناوينها إنجليزية رسمية)."""
    def client_as(self, lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user="pilot", role="commander", csrf="tok", lang=lang)
        m.engine.start_session("pilot")
        return c

    def test_seventeen_official_risks_in_three_groups(self):
        self.assertEqual(len(m.NASA_RISK), 17)
        groups = [r["group"] for r in m.NASA_RISK.values()]
        self.assertEqual((groups.count("physiology"), groups.count("behavioral"), groups.count("radiation")), (11, 5, 1))
        for r in m.NASA_RISK.values():
            self.assertTrue(r["url"].startswith("https://www.nasa.gov/reference/") and r["url"].endswith("/"), r)
            self.assertTrue(r["name"].startswith("Risk of") or r["name"].startswith("Risk from"), r)
            self.assertTrue(r["name"].isascii())

    def test_metric_pairing_only_uses_known_risks(self):
        self.assertTrue(set(m.METRIC_RISK.values()) <= set(m.NASA_RISK))
        self.assertTrue(set(m.METRIC_RISK) <= set(m.ALL_INFO))
        self.assertIsNone(m.risk_of("glucose"))
        self.assertIsNone(m.risk_of("temp"))
        self.assertEqual(m.risk_of("bone_health")["name"], "Risk of Spaceflight-Induced Bone Changes")
        self.assertEqual(m.risk_of("bpm"), m.risk_of("bp_sys"))

    def test_hazard_urls_and_facts(self):
        self.assertEqual(set(m.NASA_HAZARD_URL), {h["id"] for h in m.BODY_HAZARDS})
        page = m._hazard_page("en")
        by = {h["id"]: h for h in page}
        self.assertEqual(by["radiation"]["nasa_url"], "https://www.nasa.gov/hrp/hazard-space-radiation/")
        self.assertIn("140 million miles", by["distance"]["facts"])
        self.assertIn("three-eighths", by["gravity"]["facts"])
        self.assertEqual(by["isolation"]["facts"], "")
        self.assertEqual([r["name"] for r in by["radiation"]["risks"]], ["Risk of Radiation-Induced Cancers"])

    def test_knowledge_and_checkin_results_carry_the_risk(self):
        k = m._knowledge("ar")
        self.assertEqual(k["bpm"]["risk"]["name"], "Risk of Cardiovascular Adaptations")
        self.assertNotIn("risk", k["glucose"])
        c = self.client_as()
        r = c.post("/api/checkin", json={"sleep": 7, "glucose": 90}, headers={"X-CSRF-Token": "tok"}).get_json()
        by = {i["key"]: i for i in r["results"]}
        self.assertEqual(by["sleep"]["risk"]["name"], "Risk of Inadequate Sleep and Irregular Schedules")
        self.assertIsNone(by["glucose"]["risk"])

    def test_hazards_page_lists_all_risks_and_marks_watched_ones(self):
        for lang in ("en", "ar"):
            html = self.client_as(lang).get("/hazards").get_data(as_text=True)
            for r in m.NASA_RISK.values():
                self.assertIn(r["url"], html)
            self.assertIn("https://www.nasa.gov/hrp/hazard-gravity-fields/", html)
            self.assertIn('rel="noopener noreferrer"', html)
        en = self.client_as("en").get("/hazards").get_data(as_text=True)
        self.assertEqual(en.count("<li class=watched>"), len(set(m.METRIC_RISK.values()) | {"fitness"}))

    def test_exercise_page_links_the_fitness_risk(self):
        html = self.client_as().get("/exercise").get_data(as_text=True)
        self.assertIn("Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness", html)


class DoseTests(Base):
    """الجرعة التراكمية: تُجمع القراءات، وحدّها من limits.csv فقط، وعاصفة المحاكاة ترفعها."""

    def test_dose_accumulates_and_persists(self):
        m.engine.start_session("pilot")
        for _ in range(4):
            m.engine.tick()
        d = m.dose_state("pilot")
        self.assertGreater(d["dose"], 0)
        self.assertFalse(d["configured"])
        self.assertEqual(d["level"], "unconfigured")  # بلا حد لا يُحكم بشيء
        m.save_dose("pilot", 12.5)
        self.assertEqual(m.get_dose("pilot"), 12.5)

    def test_limit_comes_only_from_the_limits_file(self):
        self.addCleanup(lambda: setattr(m.reference, "dose", m.ReferenceStore().dose))
        m.save_reference_row(m.DOSE_KEY, danger_high=10.0, source="test source")
        m.reference.reload()
        m.engine.start_session("pilot")
        m.engine.sessions["pilot"]["dose"] = 9.0
        self.assertEqual(m.dose_state("pilot")["level"], "normal")
        m.engine.sessions["pilot"]["dose"] = 10.0
        d = m.dose_state("pilot")
        self.assertEqual((d["level"], d["limit"], d["source"]), ("danger", 10.0, "test source"))

    def test_storm_raises_readings_then_ends(self):
        m.engine.start_session("pilot")
        m.engine.start_storm("pilot")
        before = m.dose_state("pilot")["dose"]
        m.engine.tick()
        self.assertGreaterEqual(m.engine.sessions["pilot"]["vitals"]["radiation"], 0.55)
        self.assertGreater(m.dose_state("pilot")["dose"], before)
        for _ in range(m.Config.STORM_TICKS):
            m.engine.tick()
        self.assertEqual(m.engine.sessions["pilot"]["storm"], 0)

    def test_csv_accepts_radiation_total(self):
        import pathlib, tempfile
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "limits.csv").write_text("metric,danger_high,unit,source\nradiation_total,600,mSv,test\n", encoding="utf-8")
        old = m._nasa_dir
        m._nasa_dir = lambda: d
        try:
            rows = m.parse_limits_csv()
        finally:
            m._nasa_dir = old
        self.assertEqual((rows[0]["metric"], rows[0]["danger_high"]), ("radiation_total", 600.0))

    def test_dose_api_and_storm_api(self):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user="pilot", role="commander", csrf="tok", lang="en")
        self.assertEqual(c.get("/api/dose").status_code, 200)
        r = c.post("/api/storm", json={}, headers={"X-CSRF-Token": "tok"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.get_json()["storm"], 0)
        self.assertEqual(c.post("/api/storm", json={}).status_code, 400)

    def test_english_hazards_page_has_no_arabic_dose_text(self):
        import re
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user="pilot", role="commander", csrf="tok", lang="en")
        html = c.get("/hazards").get_data(as_text=True)
        self.assertIn("Cumulative radiation dose", html)
        body = re.sub(r"<a class=\"langsw\".*?</a>", "", re.sub(r"<script.*?</script>", "", html, flags=re.S))
        self.assertIsNone(re.search("[\u0600-\u06FF]", body))
        script = "".join(re.findall(r"<script>.*?</script>", html, flags=re.S))
        self.assertIsNone(re.search("[\u0600-\u06FF]", script))

    def test_no_dose_limit_value_in_code(self):
        self.assertFalse(m.reference.dose["configured"])


class LimitsFileTests(Base):
    """ملف الحدود الجاهز (خارج المشروع) يُستورد، ونص المصدر يُترجم بلا أرقام جديدة."""
    READY = __import__("pathlib").Path(__file__).resolve().parent.parent / "data" / "nasa" / "limits.csv"

    def test_source_text_is_localized(self):
        spec = {"source": "Derived from NASA data: warning = 95th percentile of heart rate (1,546 windows, 17 subjects, NASA Crew State Monitoring dataset)."}
        self.assertIn("مشتق من بيانات ناسا", m.src(spec, "ar"))
        self.assertEqual(m.src(spec, "en"), spec["source"])

    def test_us_government_sources_are_translated(self):
        import csv
        for r in csv.DictReader(open(self.READY, encoding="utf-8-sig")):
            if r["metric"] in ("oxygen", "glucose", "temp"):
                ar = m.src({"source": r["source"]}, "ar")
                self.assertTrue(ar.startswith("مرجع حكومي أمريكي"), r["metric"])
                self.assertNotIn("US government reference", ar)

    def test_derived_phrase_shown_on_pages_and_alerts(self):
        m.save_reference_row("bpm", warn_high=83.0, danger_high=130.0, danger_low=30.0, unit="bpm",
                             source="Derived from NASA data: test")
        self.addCleanup(lambda: m.reference.reload())
        m.reference.reload()
        ar = m._limits_for("ar")["bpm"]["source"]
        en = m._limits_for("en")["bpm"]["source"]
        self.assertTrue(ar.startswith("مشتق من بيانات ناسا"))
        self.assertTrue(en.startswith("Derived from NASA data"))

    def test_ready_limits_file_imports_if_present(self):
        if not self.READY.is_file():
            self.skipTest("limits.csv not in this copy")
        import pathlib, shutil, tempfile
        d = pathlib.Path(tempfile.mkdtemp())
        shutil.copy(self.READY, d / "limits.csv")
        old = m._nasa_dir
        m._nasa_dir = lambda: d
        try:
            rows = {r["metric"]: r for r in m.parse_limits_csv()}
        finally:
            m._nasa_dir = old
        self.assertEqual(set(rows), {"bpm", "bp_sys", "bp_dia", "oxygen", "glucose", "temp", "bone_health", "radiation_total"})
        self.assertEqual((rows["bpm"]["warn_high"], rows["bpm"]["danger_high"], rows["bpm"]["danger_low"]), (83.0, 130.0, 30.0))
        self.assertTrue(all(r["source"] for r in rows.values()))


class StressTrendTests(Base):
    """اتجاه التوتر يظهر بلا حدود مرجعية، ولا يرفع المستوى."""

    def _fill(self, values):
        for v in values:
            row = dict(m.DEFAULTS); row["stress"] = v
            m.add_vitals("pilot", row, "normal")

    def test_rising_stress_gives_trend_without_limits(self):
        self._fill([1.0 + i * 0.15 for i in range(60)])
        t = m.live_trends("pilot", "en")
        self.assertEqual(t["stress"]["direction"], "up")
        self.assertFalse(t["stress"]["toward_limit"])
        st = m.body_state("pilot", "en")["metrics"]["stress"]
        self.assertEqual(st["level"], "unconfigured")
        self.assertIn("risen", st["trend"])

    def test_flat_stress_gives_no_trend(self):
        self._fill([3.0] * 60)
        self.assertEqual(m.live_trends("pilot", "en"), {})

    def test_unset_label_wording(self):
        self.assertEqual(m._ui("ar")["lv_unconfigured"], "الحدود غير محددة")
        self.assertEqual(m._ui("en")["lv_unconfigured"], "Limits not set")


class QuietVoiceTests(Base):
    """التنبيهات والردود التلقائية لا تنطق من مكبر الحاسوب افتراضياً."""

    def setUp(self):
        super().setUp()
        self.spoken = []
        self._old = m.speak
        m.speak = lambda text: self.spoken.append(text)

    def tearDown(self):
        m.speak = self._old
        super().tearDown()

    def test_danger_alert_is_not_spoken_by_default(self):
        self.assertFalse(m.Config.SPEAK_AUTO)
        m._on_alert("pilot", "danger", m.bi("تنبيه تجريبي", "test alert"))
        self.assertEqual(self.spoken, [])
        self.assertTrue(any(c["sender"] == "system" for c in m.get_chat("pilot")))

    def test_automatic_assistant_reply_is_not_spoken_but_shown(self):
        old = m._generate
        m._generate = lambda prompt: "رد تجريبي"
        try:
            m._ai_worker("pilot", "x", True)
        finally:
            m._generate = old
        self.assertEqual(self.spoken, [])
        self.assertTrue(any(c["message"] == "رد تجريبي" for c in m.get_chat("pilot")))

    def test_speaks_when_explicitly_enabled(self):
        m.Config.SPEAK_AUTO = True
        self.addCleanup(lambda: setattr(m.Config, "SPEAK_AUTO", False))
        m._on_alert("pilot", "danger", m.bi("تنبيه تجريبي", "test alert"))
        self.assertEqual(len(self.spoken), 1)

    def test_alert_reason_uses_short_source(self):
        long_src = "Derived from NASA data: warning = 95th percentile of heart rate (1,546 windows, 17 subjects, NASA Crew State Monitoring dataset)"
        self.assertLessEqual(len(m.src_short({"source": long_src}, "en")), 72)
        self.assertEqual(m.src_short({"source": "NASA V1 4027"}, "en"), "NASA V1 4027")

    def test_default_serial_port(self):
        self.assertEqual(m.Config.SERIAL_PORT, "COM7")


class SleepNoteTests(Base):
    def test_checkin_page_shows_nasa_sleep_recommendation(self):
        for lang, word in (("en", "8.5 hours"), ("ar", "8.5 ساعات")):
            c = m.app.test_client()
            with c.session_transaction() as s:
                s.update(user="pilot", role="commander", csrf="tok", lang=lang)
            html = c.get("/checkin").get_data(as_text=True)
            self.assertIn(word, html)
            self.assertIn("NASA-STD-3001", html)
            if lang == "en":
                import re
                self.assertIsNone(re.search("[\u0600-\u06FF]", re.sub(r"<a class=\"langsw\".*?</a>", "", re.sub(r"<script.*?</script>", "", html, flags=re.S))))


class StreakTests(Base):
    """الستريك: أيام متتالية فيها نشاط؛ اليوم يُحسب مرة واحدة مهما كثرت الإرسالات."""
    D = staticmethod(lambda n: (__import__("datetime").date(2026, 11, 20) - __import__("datetime").timedelta(days=n)).isoformat())

    def test_counts_days_not_submissions(self):
        today = __import__("datetime").date(2026, 11, 20)
        dates = [self.D(0)] * 5 + [self.D(1), self.D(2)]
        self.assertEqual(m._streak(dates, today), {"current": 3, "best": 3, "today": True})

    def test_streak_stays_alive_until_the_day_is_missed(self):
        today = __import__("datetime").date(2026, 11, 20)
        self.assertEqual(m._streak([self.D(1), self.D(2)], today), {"current": 2, "best": 2, "today": False})
        self.assertEqual(m._streak([self.D(2), self.D(3)], today)["current"], 0)  # فاته أمس
        self.assertEqual(m._streak([], today), {"current": 0, "best": 0, "today": False})

    def test_best_streak_survives_a_break(self):
        today = __import__("datetime").date(2026, 11, 20)
        dates = [self.D(0), self.D(1), self.D(5), self.D(6), self.D(7), self.D(8)]
        self.assertEqual(m._streak(dates, today), {"current": 2, "best": 4, "today": True})

    def test_exercise_and_checkin_streaks_are_separate_and_per_user(self):
        m.engine.start_session("pilot")
        m.add_exercise("pilot", None, "button"); m.add_exercise("pilot", None, "button")
        m.add_exercise("other", None, "button")
        self.assertEqual(m.exercise_streak("pilot")["current"], 1)
        self.assertEqual(m.checkin_streak("pilot")["current"], 0)
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user="pilot", role="commander", csrf="tok", lang="en")
        self.assertEqual(c.get("/api/exercise").get_json()["streak"], {"current": 1, "best": 1, "today": True})
        self.assertEqual(c.get("/api/checkins").get_json()["streak"]["current"], 0)
        r = c.post("/api/checkin", json={"sleep": 7, "mood": 4}, headers={"X-CSRF-Token": "tok"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(c.get("/api/checkins").get_json()["streak"], {"current": 1, "best": 1, "today": True})
        c.post("/api/checkin", json={"sleep": 8, "mood": 5}, headers={"X-CSRF-Token": "tok"})
        self.assertEqual(c.get("/api/checkins").get_json()["streak"]["current"], 1)  # إرسالان في اليوم = يوم واحد

    def test_pages_show_the_streak_card(self):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user="pilot", role="commander", csrf="tok", lang="en")
        for url in ("/exercise", "/checkin"):
            html = c.get(url).get_data(as_text=True)
            self.assertIn('id="streak"', html, url)
            self.assertIn("days in a row", html, url)


class ExercisePressTests(Base):
    """زر التمرين واحد للجميع: من ضغطه؟ مستخدم نشط واحد يُنسب له فوراً، وأكثر من واحد يقول أحدهم \"أنا\"."""
    NOW = 10_000.0

    def setUp(self):
        super().setUp()
        for n in ("ali", "bo", "cy"):
            m.create_user(n, "password1")
        m.engine.pending_press = None
        m.engine.exercise_listeners.append(lambda u: m.add_exercise(u, None, "button"))  # كما يفعل _on_exercise

    def active(self, *names):
        for n in names:
            m.engine.start_session(n)
            m.engine.sessions[n]["last_seen"] = self.NOW

    def count(self, user):
        return m.exercise_summary(user, "2000-01-01 00:00:00")["sessions"]

    def client_as(self, name, role="commander", lang="en"):
        c = m.app.test_client()
        with c.session_transaction() as s:
            s.update(user=name, role=role, csrf="tok", lang=lang)
        return c

    def test_single_active_user_is_credited_at_once(self):
        self.active("ali")
        m.exercise_pressed(self.NOW)
        self.assertEqual((self.count("ali"), self.count("bo")), (1, 0))
        self.assertIsNone(m.engine.pending_press)

    def test_stale_sessions_are_not_candidates(self):
        self.active("ali", "bo")
        m.engine.sessions["bo"]["last_seen"] = self.NOW - m.Config.EXERCISE_ACTIVE_SECONDS - 5
        m.exercise_pressed(self.NOW)
        self.assertEqual((self.count("ali"), self.count("bo")), (1, 0))

    def test_two_active_users_wait_for_a_claim(self):
        self.active("ali", "bo")
        m.exercise_pressed(self.NOW)
        self.assertEqual((self.count("ali"), self.count("bo")), (0, 0))
        self.assertEqual(m.engine.pending_press["candidates"], ["ali", "bo"])
        self.assertTrue(m.claim_exercise("bo", self.NOW + 5))
        self.assertEqual((self.count("ali"), self.count("bo")), (0, 1))
        self.assertIsNone(m.engine.pending_press)
        self.assertFalse(m.claim_exercise("ali", self.NOW + 6))  # سبقه غيره

    def test_press_while_waiting_is_ignored(self):
        self.active("ali", "bo")
        m.exercise_pressed(self.NOW); first = dict(m.engine.pending_press)
        m.exercise_pressed(self.NOW + 10)
        self.assertEqual(m.engine.pending_press, first)

    def test_only_candidates_can_claim(self):
        self.active("ali", "bo")
        m.exercise_pressed(self.NOW)
        self.assertFalse(m.claim_exercise("cy", self.NOW + 1))
        self.assertIsNotNone(m.engine.pending_press)

    def test_unclaimed_press_expires_with_a_note(self):
        self.active("ali", "bo")
        m.exercise_pressed(self.NOW)
        later = self.NOW + m.Config.EXERCISE_CLAIM_SECONDS + 1
        self.assertFalse(m.claim_exercise("ali", later))
        self.assertEqual((self.count("ali"), self.count("bo")), (0, 0))
        self.assertIsNone(m.engine.pending_press)
        for n in ("ali", "bo"):
            self.assertIn("nobody claimed", " ".join(r["message"] for r in m.get_chat(n, lang="en")))

    def test_no_active_user_does_nothing(self):
        m.exercise_pressed(self.NOW)
        self.assertEqual((self.count("ali"), self.count("bo")), (0, 0))

    def test_banner_goes_only_to_candidates(self):
        self.active("ali", "bo")
        m.engine.sessions["ali"]["last_seen"] = m.time.time(); m.engine.sessions["bo"]["last_seen"] = m.time.time()
        m.exercise_pressed()
        for n in ("ali", "bo"):
            alerts = self.client_as(n).get("/api/crew/alerts").get_json()["alerts"]
            press = [a for a in alerts if a["kind"] == "press"]
            self.assertEqual(len(press), 1, n)
            self.assertTrue(press[0]["can_claim"])
            self.assertLessEqual(press[0]["seconds"], m.Config.EXERCISE_CLAIM_SECONDS)
        self.assertEqual([a for a in self.client_as("cy").get("/api/crew/alerts").get_json()["alerts"] if a["kind"] == "press"], [])
        m.create_user("doc2", "password1"); m.set_user_role("doc2", "doctor")
        self.assertEqual([a for a in self.client_as("doc2", "doctor").get("/api/crew/alerts").get_json()["alerts"] if a["kind"] == "press"], [])

    def test_claim_route_credits_the_claimant_and_clears_the_banner(self):
        self.active("ali", "bo")
        for n in ("ali", "bo"):
            m.engine.sessions[n]["last_seen"] = m.time.time()
        m.exercise_pressed()
        h = {"X-CSRF-Token": "tok"}
        self.assertEqual(self.client_as("ali").post("/api/crew/claim", json={}).status_code, 400)  # بلا CSRF
        self.assertEqual(self.client_as("cy").post("/api/crew/claim", json={}, headers=h).status_code, 404)
        self.assertEqual(self.client_as("ali").post("/api/crew/claim", json={}, headers=h).status_code, 200)
        self.assertEqual((self.count("ali"), self.count("bo")), (1, 0))
        self.assertEqual([a for a in self.client_as("bo").get("/api/crew/alerts").get_json()["alerts"] if a["kind"] == "press"], [])
        self.assertEqual(self.client_as("bo").post("/api/crew/claim", json={}, headers=h).status_code, 404)

    def test_doctor_cannot_claim(self):
        m.create_user("doc3", "password1"); m.set_user_role("doc3", "doctor")
        self.assertEqual(self.client_as("doc3", "doctor").post("/api/crew/claim", json={}, headers={"X-CSRF-Token": "tok"}).status_code, 403)

    def test_alert_poll_keeps_a_session_active(self):
        m.engine.start_session("ali")
        m.engine.sessions["ali"]["last_seen"] = m.time.time() - 500
        self.client_as("ali").get("/api/crew/alerts")
        self.assertLess(m.time.time() - m.engine.sessions["ali"]["last_seen"], 5)

    def test_banner_text_in_both_languages_without_leaks(self):
        en = self.client_as("ali").get("/body").get_data(as_text=True)
        self.assertIn("The exercise button was pressed. Was it you?", en)
        ar = self.client_as("ali", lang="ar").get("/body").get_data(as_text=True)
        self.assertIn(m.json.dumps(m.TOP_UI["press"]["ar"]), ar)  # يُدرج كـ JSON بحروف مهرّبة


if __name__ == "__main__":
    unittest.main()


class NoShippedLimitsTests(unittest.TestCase):
    def test_shipped_limits_file_has_only_sourced_nasa_limits(self):
        """يجوز شحن limits.csv بشرط أن كل حد فيه له مصدر مكتوب (ناسا أو مرجع حكومي أمريكي)، وفي المؤشرات المعتمدة فقط."""
        self.assertFalse((ROOT / "data" / "nasa" / "limits.example.csv").exists())
        path = ROOT / "data" / "nasa" / "limits.csv"
        if not path.exists():
            return
        import csv
        rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
        self.assertTrue(rows)
        allowed = {"bpm", "bp_sys", "bp_dia", "oxygen", "glucose", "temp", "bone_health", "radiation_total"}
        for r in rows:
            self.assertIn(r["metric"], allowed)
            self.assertTrue("NASA" in r["source"] or "US government reference" in r["source"], r["metric"])
            self.assertTrue(any((r.get(k) or "").strip() for k in ("warning_low", "warning_high", "danger_low", "danger_high")))
