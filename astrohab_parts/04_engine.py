# AstroHab part: 04_engine. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 4. المحرك: حالة المستخدمين والإنذار التلقائي
# ============================================================
class Engine:
    """يحتفظ بحالة كل مستخدم نشط ويحدّثها دورياً.

    الإنذار: يعمل تلقائياً عند مستوى الخطر، ويُطفأ تلقائياً بعد عدة قراءات
    طبيعية متتالية. الأمر اليدوي له أولوية لفترة محددة. الجهاز المادي واحد،
    لذلك يتبع آخر مستخدم نشط.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.sessions = {}
        self.outbox = queue.Queue(maxsize=50)  # أوامر في انتظار الإرسال للأردوينو
        self.alert_listeners = []              # دوال f(username, level, reason)
        self.exercise_listeners = []           # دوال f(username)
        self.active_user = None                # آخر مستخدم نشط: يُنسب إليه ضغط زر التمرين
        self.hw_buzzer = 0                     # آخر حالة أُرسلت للجهاز الفعلي
        self.help_calls = {}                   # المستخدم -> {"ts": وقت النداء}
        self.acks = {}                         # المستخدم في حالة طارئة -> مجموعة من أجابوا "أنا معه"
        self.pending_press = None              # ضغطة زر تمرين تنتظر من يقول "أنا": {ts, candidates}

    def start_session(self, username):
        with self.lock:
            session_ = self.sessions.get(username)
            if session_ is None:
                data = get_latest_vitals(username) or dict(DEFAULTS)
                level, reason, metric = evaluate_detail(data)
                session_ = self.sessions[username] = {
                    "vitals": data, "level": level, "reason": reason, "metric": metric, "buzzer": 0,
                    "calm_ticks": 0, "manual_until": 0.0, "ticks": 0, "last_seen": time.time(),
                    "bone_offset": 0.0, "demo": None, "dose": get_dose(username), "storm": 0}
            session_["last_seen"] = time.time()
            self.active_user = username
            return session_

    def snapshot(self, username):
        with self.lock:
            s = self.sessions.get(username)
            if s is None:
                return None
            s["last_seen"] = time.time()
            self.active_user = username
            telemetry = dict(s["vitals"])
            telemetry["bone_health"] = round(telemetry["bone_health"], 1)
            return {"telemetry": telemetry, "level": s["level"],
                    "reason": s["reason"], "buzzer": s["buzzer"]}

    # ---- العرض التجريبي: يقود القراءات عبر مراحل (طبيعي، تحذير، خطر، عودة) بقيم من الحدود المستوردة ----
    def start_demo(self, username):
        with self.lock:
            s = self.start_session(username)
            if demo_lead() is None:
                raise UserError("لا توجد حدود مرجعية تُشتق منها قيم العرض. حدّدها من بيانات ناسا أولاً.",
                                "There are no reference limits to build the demo from. Set them from NASA data first.")
            if s["demo"] is None:
                s["demo"] = {"tick": 0, "backup": dict(s["vitals"])}

    def stop_demo(self, username):
        with self.lock:
            s = self.sessions.get(username)
            if s and s["demo"]:
                self._end_demo(s)

    def _end_demo(self, s):
        s["vitals"].update(s["demo"]["backup"])  # نعيد القراءات الأصلية كما كانت قبل العرض
        s["demo"] = None
        s["calm_ticks"] = 0

    def demo_info(self, username, lang="ar"):
        with self.lock:
            s = self.sessions.get(username)
            d = s["demo"] if s else None
            if not d:
                return {"active": False, "phase": 0, "text": ""}
            phase = min(d["tick"] // Config.DEMO_PHASE_TICKS, len(DEMO_PHASES) - 1)
            return {"active": True, "phase": phase, "text": pick(DEMO_STEP_TEXT[phase], lang)}

    def _queue_command(self, command):
        try:
            self.outbox.put_nowait(command)
        except queue.Full:
            pass

    # الجهاز الفعلي واحد ومشترك: يعمل ما دام أي عضو في الطاقم حالته الإنذارية مفعّلة،
    # والإسكات اليدوي من أي حساب يُعدّ إقراراً للجميع (يُحترم المدة اليدوية ثم يعود التحكم التلقائي).
    def desired_buzzer(self):
        with self.lock:
            return 1 if any(s["buzzer"] for s in self.sessions.values()) else 0

    def _sync_hw(self):
        """يرسل أمراً للأردوينو فقط عند تغير الحالة المطلوبة للجهاز."""
        with self.lock:
            want = self.desired_buzzer()
            if want != self.hw_buzzer:
                self.hw_buzzer = want
                self._queue_command(b"BUZZER_ON\n" if want else b"BUZZER_OFF\n")

    def _set_buzzer(self, username, s, on):
        s["buzzer"] = 1 if on else 0
        self._sync_hw()

    def set_buzzer(self, username, on, manual=True):
        with self.lock:
            s = self.sessions.get(username)
            if s is None:
                return
            deadline = time.time() + Config.MANUAL_OVERRIDE_SECONDS
            if manual and not on:
                for other in self.sessions.values():  # الإسكات اليدوي يُقِرّ الإنذار للجميع
                    other["buzzer"] = 0
                    other["manual_until"] = deadline
            else:
                s["buzzer"] = 1 if on else 0
                if manual:
                    s["manual_until"] = deadline
            self._sync_hw()

    def touch(self, username):
        """يجدد "آخر ظهور" لجلسة قائمة دون أن يجعل صاحبها آخر مستخدم نشط."""
        with self.lock:
            s = self.sessions.get(username)
            if s is not None:
                s["last_seen"] = time.time()

    def start_storm(self, username):
        with self.lock:
            s = self.start_session(username)
            s["storm"] = Config.STORM_TICKS

    def register_exercise(self, user=None):
        """يُسجَّل التمرين لـ user، وبلا اسم لآخر مستخدم نشط (السلوك القديم)."""
        with self.lock:
            user = user or self.active_user
            s = self.sessions.get(user)
            if s is None:
                return
            if "bone_health" in reference.replay:
                s["bone_offset"] += 2.5  # القيمة المعاد تشغيلها تُستبدل كل دورة، فنحفظ التحسن كإزاحة
            s["vitals"]["bone_health"] = min(100.0, s["vitals"]["bone_health"] + 2.5)
        for listener in self.exercise_listeners:
            listener(user)

    def tick(self):
        now = time.time()
        to_save, alerts, doses = [], [], []
        with self.lock:
            for user in list(self.sessions):
                s = self.sessions[user]
                if now - s["last_seen"] > Config.SESSION_IDLE_SECONDS:
                    del self.sessions[user]
                    continue
                demo = s["demo"]
                if demo and demo["tick"] // Config.DEMO_PHASE_TICKS >= len(DEMO_PHASES):
                    self._end_demo(s)
                    demo = None
                if demo:
                    lead, phase = demo_lead(), demo["tick"] // Config.DEMO_PHASE_TICKS
                    for key in METRICS:
                        fake = demo_target(key, reference.current[key], phase, lead)
                        if fake is not None:
                            s["vitals"][key] = fake
                    demo["tick"] += 1
                else:
                    simulate_step(s["vitals"], reference.replay, s["ticks"])
                    if s["storm"] > 0:  # عاصفة شمسية محاكاة: قراءة الإشعاع ضمن مجال الارتفاع المعتاد في المحاكاة
                        s["vitals"]["radiation"] = round(random.uniform(0.55, 0.95), 2)
                        s["storm"] -= 1
                    s["dose"] += max(0.0, s["vitals"]["radiation"]) * Config.SIM_DAYS_PER_TICK
                if not demo and "bone_health" in reference.replay and s["bone_offset"]:
                    s["vitals"]["bone_health"] = round(
                        min(100.0, s["vitals"]["bone_health"] + s["bone_offset"]), 4)
                previous, previous_metric = s["level"], s["metric"]
                level, reason, metric = evaluate_detail(s["vitals"])
                s["level"], s["reason"], s["metric"] = level, reason, metric
                s["ticks"] += 1
                auto = now >= s["manual_until"]

                if level == "danger":
                    s["calm_ticks"] = 0
                    if auto:
                        self._set_buzzer(user, s, True)
                elif level in ("normal", "unconfigured"):
                    s["calm_ticks"] += 1
                    if auto and s["calm_ticks"] >= Config.CALM_TICKS_TO_SILENCE:
                        self._set_buzzer(user, s, False)
                else:
                    s["calm_ticks"] = 0

                # تنبيه جديد عند تغير المستوى أو عند تغير المؤشر المتسبب داخل المستوى نفسه
                if not demo and level not in ("normal", "unconfigured") and (level != previous or metric != previous_metric):
                    alerts.append((user, level, reason))
                if not demo and s["ticks"] % Config.HISTORY_EVERY_TICKS == 0:  # العرض لا يلوّث السجل
                    to_save.append((user, dict(s["vitals"]), level))
                    doses.append((user, s["dose"]))

        self._sync_hw()  # مثلاً: انتهت جلسة نشطة كان جرسها يعمل

        # الكتابة في القاعدة واستدعاء المستمعين خارج القفل لتجنب التعطيل
        for user, data, level in to_save:
            add_vitals(user, data, level)
        for user, msv in doses:
            save_dose(user, msv)
        for user, level, reason in alerts:
            for listener in self.alert_listeners:
                listener(user, level, reason)

    def _loop(self):
        while True:
            time.sleep(Config.TICK_SECONDS)
            try:
                self.tick()
            except Exception as exc:  # خطأ واحد لا يوقف المحرك
                print(f"[engine] خطأ: {exc}")

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="engine").start()


engine = Engine()
user_lang = {}  # لغة واجهة كل مستخدم (للرسائل التي يولدها النظام)
