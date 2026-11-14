# AstroHab part: 03_database. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 3. قاعدة البيانات
# ============================================================
_COLS = ", ".join(METRICS)
_MARKS = ", ".join("?" for _ in METRICS)
_VITAL_COLUMNS = "".join(f"{m} REAL, " for m in METRICS)
_CHECKIN_COLUMNS = ", ".join(f"{k} REAL" for k in CHECKIN_KEYS)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'commander',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ts TEXT NOT NULL,
    {_VITAL_COLUMNS}level TEXT
);
CREATE INDEX IF NOT EXISTS idx_vitals_user ON vitals(username, id);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ts TEXT NOT NULL,
    sender TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat(username, id);
CREATE TABLE IF NOT EXISTS dose (
    username TEXT PRIMARY KEY,
    msv REAL NOT NULL,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS reference (
    metric TEXT PRIMARY KEY,
    warn_low REAL, warn_high REAL, danger_low REAL, danger_high REAL,
    scale_min REAL, scale_max REAL,
    unit TEXT, source TEXT, replay_file TEXT, replay_column TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ts TEXT NOT NULL,
    {_CHECKIN_COLUMNS}
);
CREATE INDEX IF NOT EXISTS idx_checkins_user ON checkins(username, id);
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ts TEXT NOT NULL,
    minutes INTEGER,
    kind TEXT NOT NULL DEFAULT 'manual',
    activity TEXT,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_exercises_user ON exercises(username, id);
"""


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def db():
    conn = sqlite3.connect(Config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        have = {r["name"] for r in conn.execute("PRAGMA table_info(exercises)")}
        for col in ("activity", "note"):  # قواعد بيانات قديمة بلا هذين العمودين
            if col not in have:
                conn.execute(f"ALTER TABLE exercises ADD COLUMN {col} TEXT")


def create_user(username, password):
    """ينشئ مستخدماً. أول مستخدم يصبح مديراً. يرجع (نجح، رسالة خطأ)."""
    username = (username or "").strip()
    if not 3 <= len(username) <= 32:
        return False, "اسم المستخدم يجب أن يكون بين 3 و32 حرفاً."
    if not re.fullmatch(r"[\w.\-@ ]+", username):
        return False, "اسم المستخدم يقبل الحروف والأرقام والرموز . _ - @ فقط."
    if len(password or "") < Config.MIN_PASSWORD:
        return False, f"كلمة المرور يجب ألا تقل عن {Config.MIN_PASSWORD} أحرف."
    try:
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")  # قفل الكتابة: لا يصبح حسابان مديرين عند تسجيلين متزامنين
            if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                return False, "اسم المستخدم مستخدم مسبقاً."
            is_first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, generate_password_hash(password), "admin" if is_first else "commander", _now()))
    except sqlite3.IntegrityError:
        return False, "اسم المستخدم مستخدم مسبقاً."
    return True, ""


def users_exist():
    with db() as conn:
        return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def verify_user(username, password):
    """يرجع دور المستخدم عند صحة البيانات، وإلا None."""
    with db() as conn:
        row = conn.execute("SELECT password_hash, role FROM users WHERE username = ?",
                           ((username or "").strip(),)).fetchone()
    if row and check_password_hash(row["password_hash"], password or ""):
        return row["role"]
    return None


ASSIGNABLE_ROLES = ("commander", "doctor")
ROLE_LABEL = {"admin": bi("مدير", "Admin"), "commander": bi("قائد", "Commander"),
              "doctor": bi("طبيب طيران", "Flight surgeon")}


def get_role(username):
    """دور المستخدم الحالي من قاعدة البيانات، أو None إن لم يوجد."""
    with db() as conn:
        row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    return row["role"] if row else None


def set_user_role(username, role):
    """المدير يحوّل حساباً بين قائد وطبيب طيران. لا يُغيَّر دور المدير. يرجع (نجح، سبب الفشل)."""
    if role not in ASSIGNABLE_ROLES:
        return False, "bad_role"
    with db() as conn:
        row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return False, "no_user"
        if row["role"] == "admin":
            return False, "admin"
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
    return True, ""


# Names as written in NASA sources (see RESOURCES.md): ARED lifts and the T2 / CEVIS aerobic work. English only on purpose.
EXERCISE_GROUPS = [
    ("aerobic", bi("هوائي", "Aerobic"), [
        ("treadmill_continuous", "Treadmill (T2): continuous"),
        ("treadmill_interval", "Treadmill (T2): interval"),
        ("cycle_continuous", "Cycle ergometer (CEVIS): continuous"),
        ("cycle_interval", "Cycle ergometer (CEVIS): interval"),
    ]),
    ("resistance", bi("مقاومة (ARED)", "Resistance (ARED)"), [
        ("back_squat", "Back squat"), ("front_squat", "Front squat"),
        ("single_leg_squat", "Single-leg squat"), ("sumo_squat", "Sumo squat"),
        ("deadlift", "Deadlift"), ("romanian_deadlift", "Romanian deadlift"), ("sumo_deadlift", "Sumo deadlift"),
        ("heel_raise", "Heel raise"), ("single_leg_heel_raise", "Single-leg heel raise"),
        ("bench_press", "Bench press"), ("shoulder_press", "Shoulder press"),
        ("bent_over_row", "Bent-over row"), ("upright_row", "Upright row"),
        ("single_leg_knee_extension", "Single leg knee extension"),
    ]),
]
EXERCISE_TYPES = {key: label for _g, _t, items in EXERCISE_GROUPS for key, label in items}
EXERCISE_NOTE_MAX = 120


def add_exercise(username, minutes, kind, activity=None, note=None):
    with db() as conn:
        cur = conn.execute("INSERT INTO exercises (username, ts, minutes, kind, activity, note) VALUES (?, ?, ?, ?, ?, ?)",
                           (username, _now(), minutes, kind, activity, note))
        return cur.lastrowid


def _details_since():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - Config.EXERCISE_DETAILS_HOURS * 3600))


def pending_exercises(username):
    """جلسات الزر التي لم تُسجَّل تفاصيلها بعد (الأقدم أولاً)، خلال مهلة التفاصيل."""
    with db() as conn:
        rows = conn.execute("SELECT id, ts FROM exercises WHERE username = ? AND kind = 'button' AND minutes IS NULL "
                            "AND ts >= ? ORDER BY id", (username, _details_since())).fetchall()
    return [{"id": r["id"], "ts": r["ts"]} for r in rows]


def complete_exercise(username, ex_id, minutes, activity, note):
    """يحفظ المدة ونوع التمرين على جلسة زر تخص المستخدم ولم تُكمَل. يرجع True عند النجاح."""
    with db() as conn:
        cur = conn.execute("UPDATE exercises SET minutes = ?, activity = ?, note = ? WHERE id = ? AND username = ? "
                           "AND kind = 'button' AND minutes IS NULL", (minutes, activity, note or None, ex_id, username))
        return cur.rowcount == 1


def exercise_summary(username, since):
    """عدد الجلسات ومجموع الدقائق المسجلة وعدد الأيام النشطة منذ وقت معين (نص بصيغة قاعدة البيانات)."""
    with db() as conn:
        rows = conn.execute("SELECT ts, minutes FROM exercises WHERE username = ? AND ts >= ?",
                            (username, since)).fetchall()
    return {"sessions": len(rows), "minutes": sum(r["minutes"] or 0 for r in rows),
            "days_active": len({r["ts"][:10] for r in rows})}


def _activity_label(keys, lang):
    """نص الأنشطة المحفوظة (مفاتيح مفصولة بفاصلة) كأسماء إنجليزية؛ مفتاح غير معروف يظهر كما هو."""
    return ", ".join(EXERCISE_TYPES.get(k, k) for k in (keys or "").split(",") if k)


def exercise_log(username, since, lang, limit=50):
    """سجل الجلسات للطبيب: الوقت والمدة والنوع والملاحظة (الأحدث أولاً)."""
    with db() as conn:
        rows = conn.execute("SELECT ts, minutes, activity, note FROM exercises WHERE username = ? AND ts >= ? "
                            "ORDER BY id DESC LIMIT ?", (username, since, limit)).fetchall()
    return [{"ts": r["ts"], "minutes": r["minutes"], "activity": _activity_label(r["activity"], lang),
             "note": r["note"] or ""} for r in rows]


def _streak(dates, today=None):
    """الأيام المتتالية التي فيها نشاط. اليوم الواحد يُحسب مرة واحدة مهما كثر ما أُرسل فيه.
    السلسلة الحالية تبقى حية إن كان آخر يوم نشاط هو أمس (يمكنه التسجيل اليوم)."""
    import datetime as _dt
    days = sorted({_dt.date.fromisoformat(d) for d in dates})
    today = today or _dt.date.today()
    have = set(days)
    cur, d = 0, today if today in have else today - _dt.timedelta(days=1)
    while d in have:
        cur += 1
        d -= _dt.timedelta(days=1)
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        best, prev = max(best, run), d
    return {"current": cur, "best": best, "today": today in have}


def exercise_streak(username):
    with db() as conn:
        rows = conn.execute("SELECT DISTINCT substr(ts, 1, 10) AS d FROM exercises WHERE username = ?", (username,)).fetchall()
    return _streak([r["d"] for r in rows])


def checkin_streak(username):
    with db() as conn:
        rows = conn.execute("SELECT DISTINCT substr(ts, 1, 10) AS d FROM checkins WHERE username = ?", (username,)).fetchall()
    return _streak([r["d"] for r in rows])


def exercise_overview(username, lang, days=14):
    """بيانات صفحة سجل التمارين: عدد الجلسات في كل يوم، آخر الجلسات، الجلسات المنتظرة للتفاصيل، وكثافة العظام."""
    now = time.time()
    day_keys = [time.strftime("%Y-%m-%d", time.localtime(now - i * 86400)) for i in range(days - 1, -1, -1)]
    with db() as conn:
        rows = conn.execute("SELECT ts, minutes, kind FROM exercises WHERE username = ? AND ts >= ? ORDER BY id",
                            (username, day_keys[0] + " 00:00:00")).fetchall()
        recent = conn.execute("SELECT ts, minutes, kind, activity, note FROM exercises WHERE username = ? "
                              "ORDER BY id DESC LIMIT 10", (username,)).fetchall()
        bone_rows = conn.execute("SELECT ts, bone_health FROM vitals WHERE username = ? ORDER BY id DESC LIMIT 300",
                                 (username,)).fetchall()
    per_day = {d: {"date": d, "sessions": 0, "minutes": 0} for d in day_keys}
    for r in rows:
        d = per_day.get(r["ts"][:10])
        if d:
            d["sessions"] += 1
            d["minutes"] += r["minutes"] or 0
    series = [{"ts": r["ts"], "value": round(r["bone_health"], 1)} for r in reversed(bone_rows)
              if r["bone_health"] is not None]
    if len(series) > 60:
        step = len(series) / 60
        series = [series[int(i * step)] for i in range(60)] + [series[-1]]
    snap = engine.snapshot(username)
    week = day_keys[-7:]
    return {"days": list(per_day.values()),
            "week": {"sessions": sum(per_day[d]["sessions"] for d in week),
                     "minutes": sum(per_day[d]["minutes"] for d in week),
                     "days_active": sum(1 for d in week if per_day[d]["sessions"])},
            "recent": [{"ts": r["ts"], "minutes": r["minutes"], "kind": r["kind"],
                        "activity": _activity_label(r["activity"], lang), "note": r["note"] or ""} for r in recent],
            "pending": pending_exercises(username),
            "groups": [{"key": g, "label": pick(t, lang), "items": [{"key": k, "label": n} for k, n in items]}
                       for g, t, items in EXERCISE_GROUPS],
            "streak": exercise_streak(username),
            "note_max": EXERCISE_NOTE_MAX,
            "bone": {"current": snap["telemetry"]["bone_health"] if snap else None, "series": series,
                     "configured": reference.current["bone_health"]["configured"]}}


def list_users():
    with db() as conn:
        rows = conn.execute(
            """SELECT u.username, u.role, u.created_at,
                      (SELECT COUNT(*) FROM vitals v WHERE v.username = u.username) AS readings
               FROM users u ORDER BY u.created_at""").fetchall()
    return [dict(r) for r in rows]


def add_vitals(username, data, level):
    with db() as conn:
        conn.execute(
            f"INSERT INTO vitals (username, ts, {_COLS}, level) VALUES (?, ?, {_MARKS}, ?)",
            (username, _now(), *(data[m] for m in METRICS), level))


def get_latest_vitals(username):
    with db() as conn:
        row = conn.execute(f"SELECT {_COLS} FROM vitals WHERE username = ? ORDER BY id DESC LIMIT 1",
                           (username,)).fetchone()
    return dict(row) if row else None


def latest_vitals_ts(username):
    with db() as conn:
        row = conn.execute("SELECT ts FROM vitals WHERE username = ? ORDER BY id DESC LIMIT 1", (username,)).fetchone()
    return row[0] if row else None


def get_history(username, limit=300):
    with db() as conn:
        rows = conn.execute(
            f"SELECT ts, {_COLS}, level FROM vitals WHERE username = ? ORDER BY id DESC LIMIT ?",
            (username, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def add_alert(username, level, reason):
    with db() as conn:
        conn.execute("INSERT INTO alerts (username, ts, level, reason) VALUES (?, ?, ?, ?)",
                     (username, _now(), level, pack(reason)))


def get_alerts(username=None, limit=50, lang="ar"):
    with db() as conn:
        if username:
            rows = conn.execute("SELECT username, ts, level, reason FROM alerts "
                                "WHERE username = ? ORDER BY id DESC LIMIT ?", (username, limit)).fetchall()
        else:
            rows = conn.execute("SELECT username, ts, level, reason FROM alerts "
                                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = [dict(r) for r in rows]
    for row in out:
        row["reason"] = localize_text(row["reason"], lang)
    return out


def add_chat(username, sender, message):
    """sender: commander أو assistant أو system."""
    with db() as conn:
        conn.execute("INSERT INTO chat (username, ts, sender, message) VALUES (?, ?, ?, ?)",
                     (username, _now(), sender, pack(message)))


def add_checkin(username, values):
    """يحفظ قياسات الفحص الذاتي (أي مجموعة جزئية من CHECKIN_KEYS)."""
    cols = [k for k in CHECKIN_KEYS if k in values]
    with db() as conn:
        conn.execute(
            f"INSERT INTO checkins (username, ts, {', '.join(cols)}) VALUES (?, ?, {', '.join('?' for _ in cols)})",
            (username, _now(), *(values[k] for k in cols)))


def get_checkins(username, limit=60):
    with db() as conn:
        rows = conn.execute(
            f"SELECT ts, {', '.join(CHECKIN_KEYS)} FROM checkins WHERE username = ? ORDER BY id DESC LIMIT ?",
            (username, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def latest_checkin(username):
    """آخر قيمة مسجلة لكل مؤشر يدوي: {المؤشر: (القيمة، الوقت)}."""
    out = {}
    with db() as conn:
        for key in CHECKIN_KEYS:
            row = conn.execute(
                f"SELECT {key}, ts FROM checkins WHERE username = ? AND {key} IS NOT NULL ORDER BY id DESC LIMIT 1",
                (username,)).fetchone()
            if row:
                out[key] = (row[0], row[1])
    return out


REFERENCE_FIELDS = ("warn_low", "warn_high", "danger_low", "danger_high", "scale_min",
                    "scale_max", "unit", "source", "replay_file", "replay_column")


def get_reference_rows():
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM reference").fetchall()]


def save_reference_row(metric, **fields):
    cols = ", ".join(REFERENCE_FIELDS)
    marks = ", ".join("?" for _ in REFERENCE_FIELDS)
    with db() as conn:
        conn.execute(f"INSERT OR REPLACE INTO reference (metric, {cols}, updated_at) VALUES (?, {marks}, ?)",
                     (metric, *(fields.get(f) for f in REFERENCE_FIELDS), _now()))


def get_dose(username):
    with db() as conn:
        row = conn.execute("SELECT msv FROM dose WHERE username = ?", (username,)).fetchone()
    return float(row["msv"]) if row else 0.0


def save_dose(username, msv):
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO dose (username, msv, updated_at) VALUES (?, ?, ?)",
                     (username, float(msv), _now()))


def delete_reference_row(metric):
    with db() as conn:
        conn.execute("DELETE FROM reference WHERE metric = ?", (metric,))


def get_chat(username, limit=100, lang="ar"):
    with db() as conn:
        rows = conn.execute("SELECT id, substr(ts, 12) AS time, sender, message FROM chat "
                            "WHERE username = ? ORDER BY id DESC LIMIT ?", (username, limit)).fetchall()
    out = [dict(r) for r in reversed(rows)]
    for row in out:
        if row["sender"] == "system":
            row["message"] = localize_text(row["message"], lang)
        elif row["sender"] == "assistant":  # ردود Gemini تبقى بلغتها؛ الرد المحلي مخزن بلغتين
            row["message"] = pick(row["message"], lang)
    return out
