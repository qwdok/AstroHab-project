# AstroHab part: 06_assistant. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 7. المساعد (Gemini)
# ============================================================
SYSTEM_INSTRUCTION = (
    "You are 'AstroHab AI', an advanced bilingual (Arabic & English) space habitat AI companion. "
    "Always respond in the SAME language used by the user or event. "
    "Keep responses concise, intelligent, scientific, and limited to 1-2 sentences. "
    "Use the live station data provided and never invent readings. "
    "You are not a medical device: do not diagnose or prescribe; for worrying readings advise the crew "
    "to follow station procedures and contact the flight surgeons on Earth.")

_ai_lock = threading.Lock()
_key_index = 0
_clients = {}
_last_message_at = {}
_chat_times = {}

_WHY_WORDS = ("لماذا", "سبب", "ليش", "why")
_DIACRITICS = re.compile("[ً-ْـ]")

# أوامر الجرس لا تُنفَّذ إلا إذا جاءت بصيغة أمر صريحة. الأسئلة ("هل الإنذار مطفأ؟"،
# "why can't I turn off the alarm?") والنفي ("don't stop the alarm") لا تغيّر حالة الجرس أبداً.
_BUZZER_STEMS = ("انذار", "بزر", "جرس", "صافر", "buzzer", "alarm", "siren")
_OFF_TOKENS = {"اطف", "اطفي", "اطفئ", "اطفيه", "اطفها", "طفي", "طفيه", "طفها", "اوقف", "اوقفه", "اوقفها",
               "وقف", "وقفه", "وقفها", "اسكت", "سكت", "سكتها", "اسكات", "ايقاف", "اطفاء",
               "stop", "silence", "mute", "disable", "deactivate"}
_ON_TOKENS = {"شغل", "شغله", "شغلها", "فعل", "فعله", "فعلها", "تشغيل", "تفعيل",
              "enable", "activate", "start", "trigger"}
# صيغ المخاطب (تطفي، توقف...) تُقبل فقط مع صيغة طلب مهذب مثل "ممكن تطفي الإنذار"
_OFF_POLITE = {"تطفي", "تطفيه", "تطفئ", "توقف", "توقفه", "توقفها", "تسكت"}
_ON_POLITE = {"تشغل", "تشغله", "تشغلها", "تفعل", "تفعله"}
_POLITE = ("ممكن", "لو سمحت", "من فضلك", "الرجاء", "تقدر", "تكدر",
           "please", "can you", "could you", "would you", "will you")
_QUESTION_START = {"هل", "ليش", "لماذا", "لما", "كيف", "متى", "وش", "ايش", "شو", "ماذا", "ما", "اين", "وين",
                   "كم", "why", "what", "how", "when", "where", "is", "are", "does", "did", "was", "who",
                   "which"}
_NEGATIONS = {"لا", "ما", "مو", "ليس", "لن", "not", "never", "dont", "cant", "cannot", "without", "no"}
_OFF_PHRASE = re.compile(r"\b(?:turn|switch|shut)\b(?:\s+\w+){0,2}?\s+off\b")
_ON_PHRASE = re.compile(r"\b(?:turn|switch)\b(?:\s+\w+){0,2}?\s+on\b|\bsound\s+(?:the\s+)?(?:alarm|buzzer|siren)\b")


def _normalize(text):
    text = _DIACRITICS.sub("", text.lower())
    for ch in "أإآ":
        text = text.replace(ch, "ا")
    for ch in "'’`":
        text = text.replace(ch, "")  # don't -> dont
    return text.replace("ى", "ي")


def detect_buzzer_command(text):
    """يرجع 'on' أو 'off' إذا كان النص أمراً صريحاً للجرس، وإلا None (أسئلة ونفي وغموض = لا تنفيذ)."""
    t = _normalize(text)
    tokens = re.findall(r"\w+", t)
    if not tokens or not any(stem in t for stem in _BUZZER_STEMS):
        return None
    if any(tok in _NEGATIONS for tok in tokens):
        return None
    polite = any(p in t for p in _POLITE)
    if tokens[0] in _QUESTION_START and not polite:
        return None
    words = set(tokens)
    off = bool(words & _OFF_TOKENS) or bool(_OFF_PHRASE.search(t)) or (polite and bool(words & _OFF_POLITE))
    on = bool(words & _ON_TOKENS) or bool(_ON_PHRASE.search(t)) or (polite and bool(words & _ON_POLITE))
    if off == on:  # لا أمر، أو أمران متعارضان
        return None
    return "off" if off else "on"


def _client():
    from google import genai
    with _ai_lock:
        key = Config.API_KEYS[_key_index % len(Config.API_KEYS)]
        if key not in _clients:
            try:
                _clients[key] = genai.Client(api_key=key, http_options={"timeout": Config.GEMINI_TIMEOUT_MS})
            except TypeError:  # نسخة مكتبة لا تقبل المهلة
                _clients[key] = genai.Client(api_key=key)
        return _clients[key]


def _rotate_key():
    global _key_index
    with _ai_lock:
        _key_index = (_key_index + 1) % len(Config.API_KEYS)
        print(f"[ai] التبديل إلى المفتاح الاحتياطي رقم {_key_index}")


def _live_context(username):
    snap = engine.snapshot(username)
    if not snap:
        return "لا توجد بيانات حية."
    t = snap["telemetry"]
    parts = ", ".join(f"{k}={t[k]}" for k in METRICS)
    return f"{parts}; status={snap['level']}; alarm_reason={pick(snap['reason'], 'en')}; buzzer={'ON' if snap['buzzer'] else 'OFF'}"


def _is_busy_error(exc):
    text = str(exc)
    return bool(re.search(r"\b(?:500|503|504)\b|UNAVAILABLE|INTERNAL|DEADLINE", text))


def _generate(prompt):
    """يطلب الرد من Gemini.

    - تجاوز الحصة (429): ينتقل للمفتاح التالي.
    - ضغط على الخدمة (503 وما شابه): يعيد المحاولة عدة مرات بانتظار متزايد،
      ثم يجرب النموذج الاحتياطي إن حددته في GEMINI_FALLBACK_MODEL.
    """
    last_error = None
    models = [Config.GEMINI_MODEL]
    if Config.GEMINI_FALLBACK_MODEL and Config.GEMINI_FALLBACK_MODEL != Config.GEMINI_MODEL:
        models.append(Config.GEMINI_FALLBACK_MODEL)
    for model in models:
        busy_attempts = 0
        quota_attempts = 0
        while busy_attempts < 4 and quota_attempts < len(Config.API_KEYS) * 2:
            try:
                response = _client().models.generate_content(model=model, contents=prompt)
                return (response.text or "").strip()
            except Exception as exc:
                last_error = exc
                if ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
                        or "API_KEY_INVALID" in str(exc) or "API key not valid" in str(exc)):
                    quota_attempts += 1
                    _rotate_key()
                    time.sleep(1)
                elif _is_busy_error(exc):
                    busy_attempts += 1
                    wait = 2 ** busy_attempts  # 2، 4، 8، 16 ثانية
                    print(f"[ai] الخدمة مشغولة ({model})، إعادة المحاولة بعد {wait} ثوان ({busy_attempts}/4)")
                    time.sleep(wait)
                else:
                    raise
    raise last_error or RuntimeError("تعذر الحصول على رد")


def _ai_worker(username, prompt, speak_here=False):
    """speak_here: النطق من مكبر الحاسوب (للردود التلقائية فقط).
    ردود المستخدم تُنطق في المتصفح الذي أرسل الرسالة.
    يرجع False فقط إذا تعذر الوصول إلى Gemini (فيجيب المساعد المحلي بدلاً منه)."""
    try:
        reply = _generate(prompt)
    except Exception as exc:
        print(f"[ai] Gemini غير متاح، يتحول النظام للمساعد المحلي: {exc}")
        return False
    if reply:
        add_chat(username, "assistant", reply)
        if speak_here and Config.SPEAK_AUTO:
            speak(reply)
    else:
        add_chat(username, "system", "لم يصل رد من المساعد (قد يكون حُجب لأسباب الأمان). أعد صياغة السؤال.")
    return True


def _answer(username, prompt, text, action, user_initiated):
    """Gemini أولاً؛ إذا تعذر (انقطاع النت، حصة، ضغط، مفتاح خاطئ) يجيب المساعد المحلي."""
    ok = _ai_worker(username, prompt, not user_initiated)
    if ok is False and user_initiated:
        post_local_reply(username, text, action)


# ---- المساعد المحلي: يعمل بدون إنترنت وبدون Gemini، بقواعد وكلمات مفتاحية ----
# لا يشخّص ولا يخترع أرقاماً: يقرأ القيم الحية واليدوية والحدود المعتمدة ونصوص الشرح الموجودة في النظام فقط.
LOCAL_TAG = bi("(رد محلي) ", "(Local reply) ")

_LOCAL_METRIC_WORDS = {
    "bpm": ("نبض", "قلب", "heart", "pulse", "bpm", "hr"),
    "bp": ("ضغط", "pressure", "bp"),
    "oxygen": ("اكسجين", "اوكسجين", "اكسجن", "oxygen", "spo2", "o2"),
    "temp": ("حرار", "سخون", "حمي", "temperature", "temp", "fever"),
    "glucose": ("سكر", "glucose", "sugar"),
    "stress": ("اجهاد", "توتر", "ضغط نفسي", "stress"),
    "radiation": ("اشعاع", "radiation", "dose", "جرعه"),
    "bone_health": ("عظام", "عظم", "bone"),
    "sleep": ("نوم", "نام", "sleep"),
    "mood": ("مزاج", "mood"),
}
_LOCAL_HAZARD_WORDS = {
    "isolation": ("عزل", "isolation", "confine", "انغلاق", "وحد", "lonel"),
    "distance": ("البعد عن الارض", "بعد عن الارض", "بعيد عن الارض", "distance", "far from earth", "delay", "تاخر الاتصال"),
    "gravity": ("جاذبي", "gravity", "microgravity", "weightless"),
    "closed": ("بيئه مغلقه", "البيئه المغلقه", "closed environment", "hostile", "مغلقه", "cabin air"),
}
_LOCAL_HAZARD_GENERIC = ("المخاطر الخمس", "مخاطر الفضاء", "five hazards", "space hazards", "hazards")
_LOCAL_RISK_WORDS = ("خطر", "مخاطر", "hazard", "risk")
_LOCAL_HELP = ("مساعده", "ساعدني", "help", "وش تقدر", "ماذا تستطيع", "what can you", "commands", "اوامر")
_LOCAL_STATUS = ("حالتي", "وضعي", "كيف", "status", "how am", "how are", "summary", "ملخص", "الوضع", "حالة", "overall",
                 "مرحبا", "اهلا", "هلا", "hello", "hi", "hey")
_LOCAL_LIMITS = ("حدود", "limit", "threshold", "نطاق", "range", "مصدر", "source", "ليميت")
_LOCAL_ESCALATE = ("طبيب", "doctor", "surgeon", "اتصل", "اتواصل", "contact", "escalat", "طوارئ", "emergency", "ابلغ",
                   "اخبر", "report", "tell the crew")
_LOCAL_DUE = ("موعد", "due", "next check", "checkin", "check-in", "الفحص الذاتي", "فحص ذاتي", "مستحق")
_LOCAL_TREND = ("اتجاه", "trend", "تغير", "changing")
_LOCAL_EXPLAIN = ("ما هو", "ما هي", "شرح", "اشرح", "وش يعني", "يعني", "what is", "explain", "mean", "تاثير", "space", "فضاء",
                  "ليش مهم", "why important")
_LOCAL_ADVICE = ("اسوي", "افعل", "نصيح", "ماذا افعل", "what should", "what do", "advice", "prevent", "تجنب", "اقلل",
                 "lower", "improve", "تحسين", "كيف احسن", "كيف اخفض")
_LOCAL_ALARM_WORDS = _BUZZER_STEMS + ("تنبيه", "alert", "reason")

_LEVEL_WORDS = {
    "normal": bi("ضمن النطاق", "within range"),
    "warning": bi("تحذير", "warning"),
    "danger": bi("خطر", "danger"),
    "unconfigured": bi("لا حدود محددة", "no limits set"),
    "nodata": bi("لا قراءة مسجلة", "no reading recorded"),
}


def _words_hit(t, tokens, words):
    """هل ظهرت إحدى الكلمات؟ الكلمات اللاتينية القصيرة تُطابَق ككلمة كاملة، والباقي كجزء من النص."""
    for w in words:
        if w.isascii() and len(w) <= 4 and " " not in w:
            if w in tokens:
                return True
        elif w in t:
            return True
    return False


def _local_metrics(t, tokens):
    found = []
    for name, words in _LOCAL_METRIC_WORDS.items():
        if name == "bp" and ("ضغط نفسي" in t or "ضغط الدم" not in t and "stress" in tokens and "blood" not in tokens):
            continue
        if _words_hit(t, tokens, words):
            found.extend(["bp_sys", "bp_dia"] if name == "bp" else [name])
    return found


def _local_answer(username, text, action, lang):
    """يرجع (النص، هل فُهم السؤال). النص بلغة واحدة؛ post_local_reply يبنيه باللغتين."""
    def L(ar, en):
        return en if lang == "en" else ar

    t = _normalize(text)
    tokens = set(re.findall(r"[\w-]+", t))
    state = body_state(username, lang)
    ms = state["metrics"]

    def value_line(key):
        m_ = ms[key]
        word = pick(_LEVEL_WORDS[m_["level"]], lang)
        if m_["value"] is None:
            return f"{m_['label']}: {word}."
        line = f"{m_['label']}: {m_['value']:g} {m_['unit']} ({word})"
        if m_["level"] == "unconfigured":
            line += L("، الحدود تأتي من بيانات ناسا فقط", ", limits come only from NASA data")
        if m_.get("trend"):
            line += f" - {m_['trend']}"
        return line + "."

    def examples():
        return L("جرّب: «وش حالتي؟» أو «لماذا انطلق الإنذار؟» أو «اشرح لي النبض» أو «كيف أخفض الإجهاد؟» "
                 "أو «متى أتواصل مع الطبيب؟» أو «ما حدود الأكسجين؟» أو «ما خطر الإشعاع؟» أو «إيقاف الجرس».",
                 "Try: \"what is my status?\", \"why did the alarm sound?\", \"explain heart rate\", "
                 "\"how can I lower stress?\", \"when should I contact the doctor?\", \"what are the oxygen limits?\", "
                 "\"what is the radiation hazard?\" or \"turn off the buzzer\".")

    asked_why = any(w in t for w in _WHY_WORDS)
    snap = engine.snapshot(username)

    def alarm_reason():
        reason = pick(snap["reason"], lang) if snap else ""
        return reason or pick(NORMAL_REASON, lang)

    # 1) أمر الجرس نُفّذ قبل هذه النقطة؛ هنا نؤكد فقط
    if action:
        done = L("تم تشغيل الجرس.", "Buzzer turned on.") if action == "on" else L("تم إيقاف الجرس.", "Buzzer turned off.")
        return (done + (" " + alarm_reason() if asked_why else "")), True

    # 2) مساعدة
    if _words_hit(t, tokens, _LOCAL_HELP):
        return L("أنا المساعد المحلي: أعمل بدون إنترنت وأقرأ بيانات المحطة الحالية فقط. ",
                 "I am the local assistant: I work offline and only read the current station data. ") + examples(), True

    # 3) المخاطر الخمسة
    hazard_id = next((hid for hid, words in _LOCAL_HAZARD_WORDS.items() if _words_hit(t, tokens, words)), None)
    risk_word = _words_hit(t, tokens, _LOCAL_RISK_WORDS)
    if hazard_id is None and risk_word and _words_hit(t, tokens, ("اشعاع", "radiation")):
        hazard_id = "radiation"
    if hazard_id:
        det = HAZARD_DETAILS[hazard_id]
        name = pick(next(h["name"] for h in BODY_HAZARDS if h["id"] == hazard_id), lang)
        parts = [f"{name}: {pick(det['effects'], lang)}", pick(det["prevent"], lang)]
        if _words_hit(t, tokens, _LOCAL_ESCALATE):
            parts.append(pick(det["escalate"], lang))
        return " ".join(parts), True
    if _words_hit(t, tokens, _LOCAL_HAZARD_GENERIC):
        names = "، ".join(pick(h["name"], lang) for h in BODY_HAZARDS) if lang != "en" else \
            ", ".join(pick(h["name"], lang) for h in BODY_HAZARDS)
        return L("المخاطر الخمسة: ", "The five hazards: ") + names + L(". اسأل عن أي واحد منها لشرحه.", ". Ask about any one of them for details."), True

    # 4) لماذا الإنذار
    if asked_why and _words_hit(t, tokens, _LOCAL_ALARM_WORDS):
        return alarm_reason(), True

    metrics = _local_metrics(t, tokens)

    # 5) الحدود والمصدر
    if _words_hit(t, tokens, _LOCAL_LIMITS):
        keys = metrics or list(BODY_ORDER)
        lines = []
        for key in keys:
            spec = reference.checkin[key] if key in CHECKIN_KEYS else reference.current[key]
            if spec["configured"]:
                lines.append(f"{ms[key]['label']}: {describe_limits(spec, lang)} ({L('المصدر', 'source')}: {src(spec, lang)})")
            elif metrics:
                lines.append(f"{ms[key]['label']}: " + L("لا حدود محددة؛ تُستورد من بيانات ناسا أو limits.csv فقط.",
                                                       "no limits set; they are imported only from NASA data or limits.csv."))
        if not lines:
            return L("لا توجد حدود محددة بعد. تُستورد من بيانات ناسا في صفحة بيانات ناسا، ولا يضع النظام حدوداً من عنده.",
                     "No limits are set yet. They are imported from NASA data on the NASA Data page; the system never invents its own."), True
        return " | ".join(lines), True

    # 6) متى أتواصل مع الطبيب
    if _words_hit(t, tokens, _LOCAL_ESCALATE) and not (metrics and _words_hit(t, tokens, _LOCAL_ADVICE)):
        parts = [state["escalation"]["text"]]
        for key in metrics or [k for k in BODY_ORDER if ms[k]["level"] in ("warning", "danger")]:
            if key in KNOWLEDGE and (metrics or ms[key]["level"] in ("warning", "danger")):
                parts.append(f"{ms[key]['label']}: {pick(KNOWLEDGE[key]['escalate'], lang)}")
                if len(parts) >= 4:
                    break
        return " ".join(parts), True

    # 7) موعد الفحص الذاتي
    if _words_hit(t, tokens, _LOCAL_DUE) and not metrics or ("متي" in t and "فحص" in t):
        if state["due"]:
            names = (", " if lang == "en" else "، ").join(ms[k]["label"] for k in state["due"])
            return L("مطلوب تسجيلها في الفحص الذاتي: ", "Due in the check-in: ") + names + ".", True
        return L("كل قياسات الفحص الذاتي محدثة.", "All check-in measurements are up to date."), True

    # 8) الاتجاهات
    if _words_hit(t, tokens, _LOCAL_TREND):
        lines = [f"{ms[k]['label']}: {ms[k]['trend']}" for k in BODY_ORDER if ms[k].get("trend")]
        return (" ".join(lines) if lines else
                L("لا اتجاهات كافية بعد؛ سجّل قياسات الفحص الذاتي عدة مرات.",
                  "Not enough data for trends yet; log the check-in a few times.")), True

    # 9) مؤشر أو أكثر
    if 0 < len(set(metrics)) <= 3:
        keys = list(dict.fromkeys(metrics))
        parts = []
        for key in keys:
            info = KNOWLEDGE[key]
            explain = _words_hit(t, tokens, _LOCAL_EXPLAIN)
            advice = _words_hit(t, tokens, _LOCAL_ADVICE)
            if advice:
                parts.append(f"{ms[key]['label']}: {pick(info['action'], lang)} {pick(info['escalate'], lang)}")
            elif explain:
                parts.append(f"{pick(info['what'], lang)} {pick(info['space'], lang)} " + value_line(key))
            else:
                line = value_line(key)
                if ms[key]["level"] in ("warning", "danger"):
                    line += " " + pick(info["action"], lang)
                parts.append(line)
        if len(keys) == 2 and keys == ["bp_sys", "bp_dia"] and (_words_hit(t, tokens, _LOCAL_EXPLAIN) or _words_hit(t, tokens, _LOCAL_ADVICE)):
            parts = parts[:1]  # نص الضغط واحد للانقباضي والانبساطي
        return " ".join(parts), True

    # 10) الحالة العامة
    if _words_hit(t, tokens, _LOCAL_STATUS) or len(set(metrics)) > 3:
        bad = [k for k in BODY_ORDER if ms[k]["level"] in ("warning", "danger")]
        lines = [state["escalation"]["text"]]
        if bad:
            lines.append(" ".join(value_line(k) for k in bad))
        no_limits = sum(1 for k in BODY_ORDER if ms[k]["level"] == "unconfigured")
        if no_limits:
            lines.append(L(f"{no_limits} مؤشرات بلا حدود مرجعية بعد.", f"{no_limits} metrics have no reference limits yet."))
        if state["due"]:
            lines.append(L(f"فحص ذاتي مستحق: {len(state['due'])} مؤشرات.", f"Check-in due for {len(state['due'])} metrics."))
        return " ".join(lines), True

    return L("لم أفهم سؤالك. ", "I did not understand that question. ") + examples(), False


def local_reply(username, text, action=None):
    """رد المساعد المحلي بالعربية والإنجليزية. يرجع (رسالة ثنائية اللغة، هل فُهم السؤال)."""
    ar, understood = _local_answer(username, text, action, "ar")
    en, _ = _local_answer(username, text, action, "en")
    return bi(LOCAL_TAG["ar"] + ar, LOCAL_TAG["en"] + en), understood


def post_local_reply(username, text, action=None):
    try:
        message, _ = local_reply(username, text, action)
    except Exception as exc:  # المساعد المحلي لا يجوز أن يسقط الواجهة
        print(f"[local] خطأ: {exc}")
        message = bi("(رد محلي) تعذر تجهيز الرد.", "(Local reply) Could not prepare a reply.")
    add_chat(username, "assistant", message)


def _chat_history(username, limit=6):
    """آخر رسائل المحادثة كسياق للمساعد (حتى يفهم أسئلة المتابعة)."""
    rows = [r for r in get_chat(username, 20, "en") if r["sender"] in ("commander", "assistant")][-limit:]
    return "\n".join(f"{'Commander' if r['sender'] == 'commander' else 'Assistant'}: {r['message']}"
                     for r in rows)


def ask_assistant(username, text, user_initiated=True):
    """يرسل السؤال للمساعد. يرجع (نجح، رسالة). الرد يظهر لاحقاً في سجل المحادثة."""
    note = ""
    action = None
    history = _chat_history(username)  # قبل إضافة الرسالة الحالية
    if user_initiated:
        now = time.time()
        if now - _last_message_at.get(username, 0) < 1.0:
            return False, "رسائل كثيرة بسرعة، انتظر ثانية."
        recent = [t for t in _chat_times.get(username, []) if now - t < 600]
        if len(recent) >= Config.CHAT_PER_10MIN:  # يحمي حصة Gemini المشتركة من الإفراط
            _chat_times[username] = recent
            return False, "تجاوزت الحد المسموح من الرسائل، حاول بعد قليل."
        recent.append(now)
        _chat_times[username] = recent
        _last_message_at[username] = now
        add_chat(username, "commander", text)

        action = detect_buzzer_command(text)
        if action:
            engine.set_buzzer(username, action == "on", manual=True)
            note = f"Action executed: buzzer turned {action.upper()}. Confirm it briefly."
        if any(w in _normalize(text) for w in _WHY_WORDS):
            note += " The user asks why the alarm triggered; explain it from alarm_reason."

    if not Config.API_KEYS:  # لا Gemini: المساعد المحلي يجيب مباشرة
        if user_initiated:
            post_local_reply(username, text, action)
        return True, ""

    prompt = (f"{SYSTEM_INSTRUCTION}\n\nLive station data: {_live_context(username)}\n"
              f"Recent conversation (context only):\n{history or '(none)'}\n{note}\nUser prompt: {text}")
    threading.Thread(target=_answer, args=(username, prompt, text, action, user_initiated), daemon=True).start()
    return True, ""
