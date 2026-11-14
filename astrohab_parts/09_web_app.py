# AstroHab part: 09_web_app. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 10. تطبيق الويب
# ============================================================
# ============================================================
# 9ب. الفحص الذاتي والمجسم التفاعلي (منطق)
# ============================================================
def classify_value(spec, value):
    """مستوى قيمة واحدة حسب الحدود المرجعية: danger / warning / normal، أو unconfigured / nodata."""
    if value is None:
        return "nodata"
    if not spec["configured"]:
        return "unconfigured"
    for severity in ("danger", "warning"):
        low, high = spec[severity]
        if (high is not None and value > high) or (low is not None and value < low):
            return severity
    return "normal"


def limit_message(spec, value, severity):
    """رسالة ثنائية اللغة تذكر القيمة والحد ومصدره (مثل رسائل evaluate)."""
    low, high = spec[severity]
    if high is not None and value > high:
        direction, en_dir, bound = "ارتفاع", "high", high
    else:
        direction, en_dir, bound = "انخفاض", "low", low
    critical = severity == "danger"
    ar = (f"{direction} {'حرج ' if critical else ''}في {spec['label']}: {value} {spec['unit']} "
          f"(الحد {bound}، المصدر: {src(spec, 'ar')}).")
    en_head = f"Critical {en_dir}" if critical else en_dir.capitalize()
    en = f"{en_head} {spec['label_en'].lower()}: {value} {spec['unit_en']} (limit {bound}, source: {src(spec, 'en')})."
    return bi(ar, en)


def escalation(levels):
    """توصية من ثلاثة مستويات حسب أسوأ حالة: 0 عناية ذاتية، 1 إبلاغ الطاقم، 2 تواصل مع الأرض.

    المستوى 2 عند أي خطر، أو عند ثلاثة تحذيرات فأكثر معاً. المؤشرات بلا حدود لا تُحتسب،
    فإن لم يوجد أي مؤشر له حدود يرجع tier=None.
    """
    judged = [lv for lv in levels.values() if lv in ("normal", "warning", "danger")]
    if not judged:
        return {"tier": None, "text": UNSET_REASON}
    warnings = judged.count("warning")
    tier = 2 if ("danger" in judged or warnings >= 3) else (1 if warnings else 0)
    return {"tier": tier, "text": ESCALATION[tier]}


def _parse_ts(ts):
    return time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))


# ---------- العرض التجريبي: قيم تُشتق من حدود المؤشر نفسها (لا أرقام من خارج بيانات ناسا) ----------
DEMO_PHASES = ("normal", "warning", "danger", "normal")
DEMO_STEP_TEXT = (
    bi("المرحلة 1 من 4: كل القراءات طبيعية", "Step 1 of 4: all readings normal"),
    bi("المرحلة 2 من 4: تحذير", "Step 2 of 4: warning"),
    bi("المرحلة 3 من 4: خطر (يرن الجرس)", "Step 3 of 4: danger (the buzzer rings)"),
    bi("المرحلة 4 من 4: العودة إلى الطبيعي", "Step 4 of 4: back to normal"),
)


def demo_value(spec, level):
    """قيمة تقع داخل نطاق المستوى المطلوب، محسوبة من حدود المؤشر ومدى عرضه فقط.

    يرجع None إن لم تكن للمؤشر حدود تسمح بذلك المستوى (فيُترك كما هو).
    """
    if not spec["configured"]:
        return None
    (wl, wh), (dl, dh) = spec["warning"], spec["danger"]
    smin, smax = spec["scale"]
    if level == "normal":
        lo = wl if wl is not None else (dl if dl is not None else smin)
        hi = wh if wh is not None else (dh if dh is not None else smax)
        value = (lo + hi) / 2
    elif level == "warning":
        if wh is not None:
            top = dh if dh is not None else smax
            value = (wh + top) / 2
        elif wl is not None:
            bottom = dl if dl is not None else smin
            value = (wl + bottom) / 2
        else:
            return None
    elif level == "danger":
        if dh is not None:
            value = dh + (smax - dh) / 2 if smax > dh else dh + abs(dh) * 0.05 + 0.1
        elif dl is not None:
            value = dl - (dl - smin) / 2 if smin < dl else dl - abs(dl) * 0.05 - 0.1
        else:
            return None
    else:
        return None
    value = round(value, 2)
    return value if classify_value(spec, value) == level else None


def demo_lead():
    """المؤشر الذي يقود العرض: أول مؤشر (بترتيب المجسم) يمكن أن يبلغ التحذير ثم الخطر، وإلا أول من يبلغ التحذير.

    يتحرك مؤشر واحد فقط وبقية المؤشرات تبقى طبيعية، فتتدرج التوصية بوضوح (عناية ذاتية، ثم إبلاغ الطاقم، ثم الأرض).
    """
    specs = {**reference.current, **reference.checkin}
    for need in (("warning", "danger"), ("warning",)):
        for key in BODY_ORDER:
            if all(demo_value(specs[key], lv) is not None for lv in need):
                return key
    return None


def demo_target(key, spec, phase, lead):
    level = DEMO_PHASES[phase] if key == lead else "normal"
    value = demo_value(spec, level)
    if value is None and level == "danger":
        value = demo_value(spec, "warning")
    return value


def compute_trend(spec, values, lang):
    """اتجاه ثابت في آخر قراءات المستخدم نفسه (من الأقدم إلى الأحدث). يرجع None إن لم يوجد.

    يُعلن الاتجاه عند n قراءات متتالية في الاتجاه نفسه بتغير لا يقل عن نسبة من مدى عرض المؤشر.
    هذه قاعدة كشف تغير وليست حداً طبياً، ولا ترفع مستوى التوصية بنفسها.
    """
    vals = [v for v in values if v is not None]
    if len(vals) < Config.TREND_MIN_READINGS:
        return None
    for sign, up in ((1, True), (-1, False)):
        run = 1
        for i in range(len(vals) - 1, 0, -1):
            if (vals[i] - vals[i - 1]) * sign > 0:
                run += 1
            else:
                break
        if run >= Config.TREND_MIN_READINGS:
            first, last = vals[-run], vals[-1]
            span = (spec["scale"][1] - spec["scale"][0]) or 1
            if abs(last - first) / span * 100 < Config.TREND_MIN_CHANGE_PCT:
                return None
            # يتجه نحو حد مرجعي إن وُجد حد في اتجاه الحركة ولم يُتجاوز بعد
            bounds = [b for pair in (spec["warning"], spec["danger"]) for b in (pair[1] if up else pair[0],)]
            toward = (spec["configured"] and any(b is not None for b in bounds)
                      and classify_value(spec, last) == "normal")
            unit_ar, unit_en = spec["unit"], spec["unit_en"]
            ar = (f"{spec['label']} {'ارتفع' if up else 'انخفض'} في آخر {run} قراءات متتالية "
                  f"(من {first:g} إلى {last:g} {unit_ar})." + (" وهو يتجه نحو حد مرجعي." if toward else ""))
            en = (f"{spec['label_en']} has {'risen' if up else 'fallen'} over its last {run} readings in a row "
                  f"(from {first:g} to {last:g} {unit_en})." + (" It is moving toward a reference limit." if toward else ""))
            return {"direction": "up" if up else "down", "readings": run, "from": first, "to": last,
                    "toward_limit": bool(toward), "message": pick(bi(ar, en), lang)}
    return None


def early_warning(spec, trend, lang):
    """تنبيه مبكر: المؤشر ما زال طبيعياً لكن اتجاهه الثابت سيبلغ حداً مرجعياً خلال بضع قراءات قادمة.

    إسقاط خطي بسيط على آخر قراءات المستخدم نفسه وعلى حدود البيانات المستوردة فقط؛ ليس تنبؤاً طبياً ولا يرفع التوصية.
    يرجع None أو {"readings": عدد القراءات، "bound": الحد، "kind": warning|danger، "message": نص}.
    """
    if not trend or not trend["toward_limit"] or trend["readings"] < 2:
        return None
    up = trend["direction"] == "up"
    slope = (trend["to"] - trend["from"]) / (trend["readings"] - 1)
    last = trend["to"]
    for kind in ("warning", "danger"):
        bound = spec[kind][1 if up else 0]
        if bound is None or (bound - last) * (1 if up else -1) <= 0:
            continue
        steps = (bound - last) / slope
        if 0 < steps <= Config.EARLY_HORIZON_READINGS:
            n = max(1, math.ceil(steps))
            ar = (f"بهذه الوتيرة قد يبلغ {spec['label']} حد {'التحذير' if kind == 'warning' else 'الخطر'} "
                  f"({bound:g} {spec['unit']}) خلال {n} قراءات قادمة. أعد القياس ولاحظ الاتجاه.")
            en = (f"At this pace {spec['label_en']} may reach the {kind} limit ({bound:g} {spec['unit_en']}) "
                  f"within about {n} more reading{'s' if n != 1 else ''}. Measure again and watch the trend.")
            return {"readings": n, "bound": bound, "kind": kind, "message": pick(bi(ar, en), lang)}
        return None
    return None


def checkin_trends(user, lang):
    rows = get_checkins(user, 30)
    out = {}
    for key in CHECKIN_KEYS:
        trend = compute_trend(reference.checkin[key], [r[key] for r in rows], lang)
        if trend:
            early = early_warning(reference.checkin[key], trend, lang)
            trend["early"] = early
            if early:
                trend["message"] += " " + early["message"]
            out[key] = trend
    return out


def live_trends(user, lang):
    """اتجاه التوتر (تقدير حي) من سجل المستخدم نفسه: قراءة واحدة تقريباً كل دقيقة. لا يحتاج حدوداً."""
    rows = get_history(user, 90)[::-1][::6][::-1]  # كل سادس صف (حوالي دقيقة) من الأقدم إلى الأحدث
    out = {}
    trend = compute_trend(reference.current["stress"], [r["stress"] for r in rows], lang)
    if trend:
        out["stress"] = trend
    return out


def _hazard_page(lang):
    out = []
    for h in BODY_HAZARDS:
        d = HAZARD_DETAILS[h["id"]]
        risks = []
        for m in h["metrics"]:
            r = risk_of(m)
            if r and r not in risks:
                risks.append(r)
        out.append({"id": h["id"], "name": pick(h["name"], lang), "what": pick(h["text"], lang),
                    "effects": pick(d["effects"], lang), "prevent": pick(d["prevent"], lang),
                    "escalate": pick(d["escalate"], lang), "metrics": h["metrics"],
                    "nasa_url": NASA_HAZARD_URL[h["id"]], "risks": risks,
                    "facts": pick(HAZARD_FACTS[h["id"]], lang) if h["id"] in HAZARD_FACTS else ""})
    return out


def _risk_groups(lang):
    watched = set(METRIC_RISK.values()) | {"fitness"}
    return [{"group": pick(label, lang),
             "items": [{"name": r["name"], "url": r["url"], "watched": r["key"] in watched}
                       for r in NASA_RISK.values() if r["group"] == g]} for g, label in RISK_GROUPS]


def describe_limits(spec, lang):
    """نص مقروء للحدود المرجعية لمؤشر (بلا أرقام من خارج الحدود المحددة)."""
    if not spec["configured"]:
        return pick(bi("لا حدود محددة", "No limits set"), lang)
    parts = []
    for severity, name in (("warning", bi("تحذير", "warning")), ("danger", bi("خطر", "danger"))):
        low, high = spec[severity]
        bits = []
        if low is not None:
            bits.append(pick(bi(f"أقل من {low:g}", f"below {low:g}"), lang))
        if high is not None:
            bits.append(pick(bi(f"أعلى من {high:g}", f"above {high:g}"), lang))
        if bits:
            parts.append(f"{pick(name, lang)}: " + (" / ".join(bits)))
    return "; ".join(parts)


def build_summary(user, days, lang):
    """ملخص قابل للطباعة لطبيب الطيران عن آخر عدد من الأيام، من القياسات المحفوظة فقط (لا قيم العرض التجريبي)."""
    days = max(1, min(int(days), 90))
    now = time.time()
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - days * 86400))
    with db() as conn:
        vit = [dict(r) for r in conn.execute(
            f"SELECT ts, {_COLS} FROM vitals WHERE username = ? AND ts >= ? ORDER BY id", (user, since))]
        chk = [dict(r) for r in conn.execute(
            f"SELECT ts, {', '.join(CHECKIN_KEYS)} FROM checkins WHERE username = ? AND ts >= ? ORDER BY id", (user, since))]
        alert_rows = [dict(r) for r in conn.execute(
            "SELECT ts, level, reason FROM alerts WHERE username = ? AND ts >= ? ORDER BY id DESC", (user, since))]
    metrics = []
    for key in BODY_ORDER:
        live = key in METRICS
        spec = (reference.current if live else reference.checkin)[key]
        values = [r[key] for r in (vit if live else chk) if r[key] is not None]
        levels = [classify_value(spec, v) for v in values]
        if live:
            reading_source = bi("إعادة تشغيل بيانات ناسا", "NASA data replay") if spec["replay"] else bi("محاكاة", "Simulated")
        else:
            reading_source = bi("إدخال المستخدم", "Entered by the user")
        metrics.append({
            "key": key, "label": spec["label_en"] if lang == "en" else spec["label"],
            "unit": spec["unit_en"] if lang == "en" else spec["unit"],
            "kind": "live" if live else "manual", "reading_source": pick(reading_source, lang),
            "n": len(values),
            "min": round(min(values), 2) if values else None, "max": round(max(values), 2) if values else None,
            "mean": round(sum(values) / len(values), 2) if values else None,
            "last": round(values[-1], 2) if values else None,
            "warning_n": levels.count("warning"), "danger_n": levels.count("danger"),
            "limits": describe_limits(spec, lang), "limit_source": src(spec, lang) if spec["configured"] else "",
            "configured": spec["configured"],
        })
    # التوصية الحالية من آخر القيم المحفوظة الحقيقية (لا العرض التجريبي)
    last_vitals = get_latest_vitals(user) or {}
    latest = latest_checkin(user)
    current = {k: classify_value(reference.current[k], last_vitals.get(k)) for k in METRICS}
    current.update({k: classify_value(reference.checkin[k], latest[k][0] if k in latest else None) for k in CHECKIN_KEYS})
    esc = escalation(current)
    alerts = [{"ts": a["ts"], "level": a["level"], "reason": localize_text(a["reason"], lang)} for a in alert_rows]
    return {
        "user": user, "days": days, "from": since, "to": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "metrics": metrics, "tier": esc["tier"], "tier_text": pick(esc["text"], lang),
        "alert_counts": {"danger": sum(a["level"] == "danger" for a in alerts),
                         "warning": sum(a["level"] == "warning" for a in alerts)},
        "alerts": alerts[:25], "trends": [t["message"] for t in {**checkin_trends(user, lang), **live_trends(user, lang)}.values()],
        "checkins": len(chk), "readings": len(vit),
        "exercise": {**exercise_summary(user, since), "log": exercise_log(user, since, lang)},
    }


# ---- ملخص الطبيب كملف PDF (reportlab): تشكيل الحروف العربية وترتيب الاتجاه نفذناهما هنا بلا مكتبات إضافية ----
_AR_FORMS = {}
_AR_LAM_ALEF = {}
_AR_MARKS = re.compile("[ً-ٰٟـ]")


def _arabic_tables():
    """أشكال الحروف (معزول، نهاية، بداية، وسط) من قاعدة بيانات يونيكود نفسها."""
    if _AR_FORMS:
        return
    names = {"<isolated>": "isol", "<final>": "fina", "<initial>": "init", "<medial>": "medi"}
    for cp in range(0xFE70, 0xFEFD):
        parts = unicodedata.decomposition(chr(cp)).split()
        if not parts or parts[0] not in names:
            continue
        chars = [chr(int(x, 16)) for x in parts[1:]]
        if len(chars) == 1:
            _AR_FORMS.setdefault(chars[0], {})[names[parts[0]]] = chr(cp)
        elif len(chars) == 2 and chars[0] == "ل":
            _AR_LAM_ALEF.setdefault(chars[1], {})[names[parts[0]]] = chr(cp)


def shape_arabic(text):
    """يحوّل الحروف العربية إلى أشكالها المتصلة (بداية/وسط/نهاية) مع لام-ألف. الترتيب يبقى منطقياً."""
    _arabic_tables()
    chars = list(_AR_MARKS.sub("", text))
    out, i = [], 0
    prev_dual = False  # الحرف السابق يتصل بما بعده
    while i < len(chars):
        c = chars[i]
        forms = _AR_FORMS.get(c)
        if not forms:
            out.append(c); prev_dual = False; i += 1
            continue
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if c == "ل" and nxt in _AR_LAM_ALEF:
            lig = _AR_LAM_ALEF[nxt]
            out.append(lig.get("fina") if prev_dual and "fina" in lig else lig["isol"])
            prev_dual = False; i += 2
            continue
        dual = "init" in forms
        next_joins = dual and "fina" in _AR_FORMS.get(nxt, {})
        if prev_dual and next_joins:
            kind = "medi"
        elif prev_dual:
            kind = "fina"
        elif next_joins:
            kind = "init"
        else:
            kind = "isol"
        out.append(forms.get(kind) or forms["isol"])
        prev_dual = dual
        i += 1
    return "".join(out)


_MIRROR = str.maketrans("()[]<>", ")(][><")


def _is_arabic(c):
    return "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" or "ﭐ" <= c <= "﷿" or "ﹰ" <= c <= "﻿"


def bidi_visual(text, rtl):
    """ترتيب العرض (من اليسار لليمين) لسطر واحد: نص عربي مع أرقام وكلمات لاتينية. بسيط لكنه يكفي لنصوص التقرير."""
    if not rtl or not text:
        return text
    cls = []
    for idx, c in enumerate(text):
        if _is_arabic(c):
            cls.append("R")
        elif c.isalnum():
            cls.append("L")
        elif c in ".,:/-" and 0 < idx < len(text) - 1 and text[idx - 1].isdigit() and text[idx + 1].isdigit():
            cls.append("L")
        else:
            cls.append("N")
    runs = []
    for c, k in zip(text, cls):
        if runs and runs[-1][0] == k:
            runs[-1][1] += c
        else:
            runs.append([k, c])
    for n, run in enumerate(runs):
        if run[0] == "N":
            before = next((r[0] for r in reversed(runs[:n]) if r[0] != "N"), None)
            after = next((r[0] for r in runs[n + 1:] if r[0] != "N"), None)
            run[0] = before if before == after and before else "R"
    merged = []
    for k, t in runs:
        if merged and merged[-1][0] == k:
            merged[-1][1] += t
        else:
            merged.append([k, t])
    return "".join(t[::-1].translate(_MIRROR) if k == "R" else t for k, t in reversed(merged))


def _pdf_fonts():
    """يسجل خطاً يدعم العربية: المرفق مع المشروع أولاً ثم خطوط النظام."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if "AstroSans" in pdfmetrics.getRegisteredFontNames():
        return "AstroSans", "AstroSans-Bold"
    regular = [BASE_DIR / "static" / "fonts" / "DejaVuSans.ttf",
               Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
               Path("C:/Windows/Fonts/arial.ttf"), Path("/Library/Fonts/Arial Unicode.ttf"),
               Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
    bold = [BASE_DIR / "static" / "fonts" / "DejaVuSans-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")]
    reg = next((f for f in regular if f.is_file()), None)
    if reg is None:
        raise RuntimeError("no font with Arabic support found (static/fonts/DejaVuSans.ttf is missing)")
    bld = next((f for f in bold if f.is_file()), reg)
    pdfmetrics.registerFont(TTFont("AstroSans", str(reg)))
    pdfmetrics.registerFont(TTFont("AstroSans-Bold", str(bld)))
    return "AstroSans", "AstroSans-Bold"


def build_summary_pdf(s, lang):
    """ملخص الطبيب كملف PDF (A4 أفقي). s ناتج build_summary. يرفع ImportError إن لم تكن reportlab مثبتة."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    ui = _ui(lang)
    rtl = lang != "en"
    font, bold = _pdf_fonts()
    page_w, page_h = landscape(A4)
    margin = 36
    width = page_w - 2 * margin
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle(ui["sm_title"] if not rtl else "AstroHab")
    c.setAuthor("AstroHab")
    state = {"y": page_h - margin, "page": 1}

    def prep(text):
        return bidi_visual(shape_arabic(str(text)) if rtl else str(text), rtl)

    def wrap(text, size, max_w, face=font):
        lines = []
        for para in str(text).split("\n"):
            words, line = para.split(), ""
            for w in words:
                trial = (line + " " + w).strip()
                if line and stringWidth(prep(trial), face, size) > max_w:
                    lines.append(line); line = w
                else:
                    line = trial
            lines.append(line)
        return lines

    def footer():
        c.setFont(font, 8); c.setFillGray(0.4)
        c.drawCentredString(page_w / 2, 18, f"AstroHab - {state['page']}")
        c.setFillGray(0)

    def ensure(h):
        if state["y"] - h < margin:
            footer(); c.showPage(); state["page"] += 1; state["y"] = page_h - margin

    def draw(text, x_left, y, size, face=font, w=None, align=None):
        c.setFont(face, size)
        vis = prep(text)
        if (align or ("right" if rtl else "left")) == "right":
            c.drawRightString(x_left + (w if w is not None else width), y, vis)
        else:
            c.drawString(x_left, y, vis)

    def para(text, size=10, face=font, gap=3, color=0):
        c.setFillGray(color)
        for line in wrap(text, size, width, face):
            ensure(size + gap)
            state["y"] -= size + gap
            draw(line, margin, state["y"], size, face)
        c.setFillGray(0)

    def heading(text):
        state["y"] -= 8
        ensure(30)
        para(text, 13, bold, gap=4)
        c.setStrokeGray(0.75); c.line(margin, state["y"] - 2, margin + width, state["y"] - 2)
        state["y"] -= 4

    para(ui["sm_title"], 18, bold, gap=6)
    para(f"{ui['sm_user']}: {s['user']}    {ui['sm_period']}: {s['from']} → {s['to']}")
    para(ui["sm_counts"].replace("{r}", str(s["readings"])).replace("{c}", str(s["checkins"]))
         .replace("{w}", str(s["alert_counts"]["warning"])).replace("{d}", str(s["alert_counts"]["danger"])))
    ex = s["exercise"]
    para(ui["sm_exercise"].replace("{s}", str(ex["sessions"])).replace("{m}", str(ex["minutes"])).replace("{d}", str(ex["days_active"])))
    for e in ex["log"]:
        detail = [f"{e['minutes']} {ui['ex_min']}" if e["minutes"] else ui["sm_ex_nodetails"], e["activity"], e["note"]]
        para(f"  {e['ts']}  -  " + " - ".join(x for x in detail if x), 9, color=0.25)
    para(ui["sm_current"], 9, color=0.4)
    para(s["tier_text"], 11, bold)

    heading(ui["sm_metrics"])
    keys = ["sm_col_metric", "sm_col_source", "sm_col_n", "sm_col_min", "sm_col_max", "sm_col_mean", "sm_col_last",
            "sm_col_warn", "sm_col_danger", "sm_col_limits", "sm_col_limit_source"]
    rel = [24, 15, 6, 7, 7, 7, 7, 9, 9, 30, 15]
    widths = [width * r / sum(rel) for r in rel]
    order = list(range(len(keys)))
    if rtl:
        order.reverse()

    def fmt(v):
        return "-" if v is None else f"{v:g}"

    def row(cells, face, size=8, fill=None):
        wrapped = [wrap(cells[i], size, widths[i] - 6, face) for i in range(len(cells))]
        h = max(len(w) for w in wrapped) * (size + 2) + 6
        ensure(h)
        top = state["y"]
        if fill is not None:
            c.setFillGray(fill); c.rect(margin, top - h, width, h, stroke=0, fill=1); c.setFillGray(0)
        xs, x = {}, margin
        for i in order:
            xs[i] = x; x += widths[i]
        for i in range(len(cells)):
            for n, line in enumerate(wrapped[i]):
                draw(line, xs[i] + 3, top - 3 - (n + 1) * (size + 2) + 2, size, face, widths[i] - 6)
        c.setStrokeGray(0.8); c.line(margin, top - h, margin + width, top - h)
        state["y"] = top - h

    row([ui[k] for k in keys], bold, 8, 0.92)
    for m in s["metrics"]:
        row([f"{m['label']} ({m['unit']})", m["reading_source"], str(m["n"]), fmt(m["min"]), fmt(m["max"]), fmt(m["mean"]),
             fmt(m["last"]), str(m["warning_n"]), str(m["danger_n"]), m["limits"], m["limit_source"]], font)

    heading(ui["sm_trends"])
    for t in (s["trends"] or [ui["sm_no_trends"]]):
        para(t, 10)
    heading(ui["sm_alerts"])
    for a in (s["alerts"] or [None]):
        para(ui["sm_no_alerts"] if a is None else f"[{ui['lv_' + a['level']]}] {a['ts']}  {a['reason']}", 10)
    heading(ui["sm_notes"])
    para(ui["sm_note_limits"], 9, color=0.3)
    para(ui["sm_note_trend"], 9, color=0.3)
    para(ui["disclaimer"], 9, color=0.3)
    footer()
    c.save()
    return buf.getvalue()



def _minutes_since_ts(ts, now):
    return None if not ts else max(0, int((now - _parse_ts(ts)) / 60))


def crew_state(viewer_role, viewer, lang):
    """حالة كل أفراد الطاقم. الجميع يرون المستوى والتوصية واسم أهم مؤشر، والأرقام للمدير فقط.

    من يشغّل العرض التجريبي تظهر قراءاته الحقيقية المحفوظة قبل العرض (قيم العرض محاكاة لا تُعرض للطاقم).
    """
    now = time.time()
    with engine.lock:
        live = {}
        for name, s in engine.sessions.items():
            demo = s["demo"]
            live[name] = {"vitals": dict(demo["backup"] if demo else s["vitals"]), "buzzer": s["buzzer"],
                          "seen": s["last_seen"], "demo": bool(demo)}
        shared_buzzer = engine.desired_buzzer()
    rank = {"danger": 3, "warning": 2, "normal": 1, "unconfigured": 0, "nodata": -1}
    members, tiers = [], []
    for u in list_users():
        if u["role"] == "doctor":  # طبيب الطيران ليس من الطاقم ولا يُحسب في حالته
            continue
        name = u["username"]
        info = live.get(name)
        vitals = info["vitals"] if info else get_latest_vitals(name)
        latest = latest_checkin(name)
        if vitals:
            level, _, metric = evaluate_detail(vitals)
        else:
            level, metric = "nodata", None
        levels = {k: classify_value(reference.current[k], vitals.get(k) if vitals else None) for k in METRICS}
        levels.update({k: classify_value(reference.checkin[k], latest[k][0] if k in latest else None)
                       for k in CHECKIN_KEYS})
        # أسوأ مؤشر يدوي يؤثر أيضاً على مستوى العضو الظاهر
        worst_manual = max((k for k in CHECKIN_KEYS), key=lambda k: rank.get(levels[k], -1))
        if rank.get(levels[worst_manual], -1) > rank.get(level, -1) and levels[worst_manual] in ("warning", "danger"):
            level, metric = levels[worst_manual], worst_manual
        esc = escalation(levels)
        if esc["tier"] is not None:
            tiers.append(esc["tier"])
        spec = None
        if metric:
            spec = (reference.current if metric in METRICS else reference.checkin)[metric]
        ages = [_minutes_since_ts(ts, now) for _, ts in latest.values()]
        member = {
            "name": name, "role": u["role"], "me": name == viewer, "active": bool(info), "demo": bool(info and info["demo"]),
            "level": level, "tier": esc["tier"], "tier_text": pick(esc["text"], lang),
            "metric": (spec["label_en"] if lang == "en" else spec["label"]) if spec else "",
            "buzzer": int(bool(info and info["buzzer"])),
            "seen_minutes": (max(0, int((now - info["seen"]) / 60)) if info
                             else _minutes_since_ts(latest_vitals_ts(name), now)),
            "checkin_minutes": min((a for a in ages if a is not None), default=None),
        }
        if viewer_role in ("admin", "doctor") or name == viewer:  # الأرقام للمدير ولطبيب الطيران ولصاحبها فقط
            vals = {}
            for k in METRICS:
                if vitals and vitals.get(k) is not None:
                    vals[k] = {"label": reference.current[k]["label_en" if lang == "en" else "label"],
                               "unit": reference.current[k]["unit_en" if lang == "en" else "unit"], "value": vitals[k]}
            for k in CHECKIN_KEYS:
                if k in latest:
                    vals[k] = {"label": reference.checkin[k]["label_en" if lang == "en" else "label"],
                               "unit": reference.checkin[k]["unit_en" if lang == "en" else "unit"], "value": latest[k][0]}
            member["values"] = vals
        members.append(member)
    members.sort(key=lambda m: (-rank.get(m["level"], -1), not m["active"], m["name"].lower()))
    crew_tier = max(tiers) if tiers else None
    text = ESCALATION[crew_tier] if crew_tier is not None else UNSET_REASON
    counts = {lv: sum(1 for m in members if m["level"] == lv) for lv in ("danger", "warning", "normal")}
    return {"members": members, "tier": crew_tier, "tier_text": pick(text, lang), "counts": counts,
            "active": sum(m["active"] for m in members), "total": len(members), "buzzer": shared_buzzer,
            "viewer_is_admin": viewer_role == "admin", "viewer_role": viewer_role}


def _expire_press(now):
    """يلغي ضغطة زر لم يطالب بها أحد في المهلة، ويكتب ملاحظة للمرشحين. يستدعى خارج قفل المحرك."""
    with engine.lock:
        pend = engine.pending_press
        if not pend or now - pend["ts"] <= Config.EXERCISE_CLAIM_SECONDS:
            return
        engine.pending_press = None
        names = list(pend["candidates"])
    for name in names:
        add_chat(name, "system", bi("ضغطة زر التمرين لم يطالب بها أحد، فلم تُسجَّل.",
                                    "The exercise button was pressed but nobody claimed it, so it was not recorded."))


def exercise_pressed(now=None):
    """إشارة زر التمرين: تُنسب فوراً إن كان هناك مستخدم نشط واحد، ومع أكثر من واحد ينتظر من يقول "أنا"."""
    now = time.time() if now is None else now
    _expire_press(now)
    with engine.lock:
        if engine.pending_press:
            return  # ضغطة سابقة لم يُبتّ فيها
        active = sorted(n for n, s in engine.sessions.items() if now - s["last_seen"] <= Config.EXERCISE_ACTIVE_SECONDS)
        if len(active) > 1:
            engine.pending_press = {"ts": now, "candidates": active}
            return
        target = active[0] if active else None
    engine.register_exercise(target)  # بلا مرشحين: السلوك القديم (آخر مستخدم نشط إن وُجد)


def claim_exercise(user, now=None):
    """المستخدم يقول إنه من ضغط الزر. يرجع True إن سُجِّل له التمرين."""
    now = time.time() if now is None else now
    _expire_press(now)
    with engine.lock:
        pend = engine.pending_press
        if not pend or user not in pend["candidates"]:
            return False
        engine.pending_press = None
    engine.register_exercise(user)
    return True


def crew_alerts(viewer, role, lang):
    """الحالات الطارئة الظاهرة لكل الطاقم: نداء مساعدة أو عضو نشط في حالة خطر، مع من أجاب "أنا معه".

    يظهر الاسم والمؤشر فقط (مثل شاشة الطاقم)؛ الأرقام لا تُعرض هنا.
    """
    members = crew_state(role, viewer, lang)["members"]
    now = time.time()
    _expire_press(now)
    items, targets = [], set()
    with engine.lock:
        pend = engine.pending_press
        if pend and role != "doctor" and viewer in pend["candidates"]:
            items.append({"user": "", "kind": "press", "metric": "", "me": False, "acks": [], "acked": False,
                          "can_ack": False, "can_claim": True, "minutes": None,
                          "seconds": max(0, int(Config.EXERCISE_CLAIM_SECONDS - (now - pend["ts"])))})
        pending_n = len(pending_exercises(viewer)) if role != "doctor" else 0
        if pending_n:
            items.append({"user": "", "kind": "log", "metric": "", "me": False, "acks": [], "acked": False,
                          "can_ack": False, "can_claim": False, "minutes": None, "count": pending_n})
        for name, call in list(engine.help_calls.items()):
            if now - call["ts"] > Config.HELP_CALL_MINUTES * 60:
                del engine.help_calls[name]
        for mem in members:
            name = mem["name"]
            if name in engine.help_calls:
                kind = "help"
            elif mem["level"] == "danger" and mem["active"]:
                kind = "danger"
            else:
                continue
            targets.add(name)
            acks = sorted(engine.acks.get(name, ()))
            items.append({"user": name, "kind": kind, "metric": mem["metric"] if kind == "danger" else "",
                          "me": name == viewer, "acks": acks, "acked": viewer in acks,
                          "can_ack": role != "doctor" and name != viewer,
                          "minutes": int((now - engine.help_calls[name]["ts"]) / 60) if kind == "help" else None})
        for name in list(engine.acks):
            if name not in targets:  # انتهت الحالة: تُنسى الاستجابات السابقة
                del engine.acks[name]
    order = {"press": 0, "help": 1, "danger": 2, "log": 3}
    items.sort(key=lambda i: (order.get(i["kind"], 2), i["user"].lower()))
    return {"alerts": items, "help_active": viewer in engine.help_calls}


def set_help_call(user, on):
    """يفتح أو يلغي نداء مساعدة. يرجع True إذا تغيّرت الحالة."""
    with engine.lock:
        if on == (user in engine.help_calls):
            return False
        if on:
            engine.help_calls[user] = {"ts": time.time()}
            engine.acks.pop(user, None)
        else:
            engine.help_calls.pop(user, None)
            engine.acks.pop(user, None)
    if on:
        add_alert(user, "danger", bi(f"نداء مساعدة من {user}.", f"Help call from {user}."))
    return True


def ack_crew_alert(viewer, role, target):
    """يسجل أن viewer في طريقه إلى target. يرجع True إن كانت الحالة قائمة."""
    if viewer == target or role == "doctor":  # طبيب الطيران على الأرض: لا يجيب "أنا معه"
        return False
    alerts = crew_alerts(viewer, role, "en")["alerts"]
    if not any(a["user"] == target for a in alerts):
        return False
    with engine.lock:
        engine.acks.setdefault(target, set()).add(viewer)
    return True


def body_state(user, lang):
    """حالة كل المؤشرات (الحية واليدوية) مع مستوى كل منها والتوصية العامة، لصفحة المجسم."""
    engine.start_session(user)
    snap = engine.snapshot(user)
    metrics, levels, due = {}, {}, []
    now = time.time()

    def add(key, spec, value, kind, ts):
        level = classify_value(spec, value)
        levels[key] = level
        metrics[key] = {
            "label": spec["label_en"] if lang == "en" else spec["label"],
            "unit": spec["unit_en"] if lang == "en" else spec["unit"],
            "value": value, "level": level, "kind": kind,
            "source": src(spec, lang) if spec["configured"] else "",
            "configured": spec["configured"], "measured": ts,
            "age_minutes": None if ts is None else max(0, int((now - _parse_ts(ts)) / 60)),
        }

    demo = engine.demo_info(user, lang)
    live = {} if demo["active"] else live_trends(user, lang)
    for key in METRICS:
        add(key, reference.current[key], snap["telemetry"][key], "live", None)
        metrics[key]["trend"] = live[key]["message"] if key in live else ""
    latest = latest_checkin(user)
    trends = {} if demo["active"] else checkin_trends(user, lang)
    for key in CHECKIN_KEYS:
        value, ts = latest.get(key, (None, None))
        if demo["active"]:  # قيم محاكاة مؤقتة لا تُحفظ في السجل
            fake = demo_target(key, reference.checkin[key], demo["phase"], demo_lead())
            if fake is not None:
                value, ts = fake, time.strftime("%Y-%m-%d %H:%M:%S")
        add(key, reference.checkin[key], value, "manual", ts)
        metrics[key]["trend"] = trends[key]["message"] if key in trends else ""
        age = metrics[key]["age_minutes"]
        if age is None or age > Config.MANUAL_DUE_HOURS * 60:
            due.append(key)  # القياس اليدوي مستحق إن لم يُسجَّل خلال المدة المحددة
    esc = escalation(levels)
    return {"metrics": {k: metrics[k] for k in BODY_ORDER},
            "escalation": {"tier": esc["tier"], "text": pick(esc["text"], lang)}, "due": due, "demo": demo}


def parse_checkin(body):
    """يتحقق من قياسات الفحص الذاتي. يرجع {المؤشر: القيمة} أو يرفع UserError."""
    values = {}
    for key in CHECKIN_KEYS:
        raw = body.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        info = CHECKIN_INFO[key]
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise UserError(f"قيمة غير رقمية في {info['label']}.", f"Non-numeric value in {info['label_en']}.")
        low, high = info["valid"]
        if not math.isfinite(value) or not low <= value <= high:
            raise UserError(f"قيمة غير معقولة في {info['label']} (المجال المقبول {low} إلى {high}).",
                            f"Implausible value in {info['label_en']} (accepted range {low} to {high}).")
        values[key] = float(round(value)) if key == "mood" else round(value, 1)
    if not values:
        raise UserError("أدخل قياساً واحداً على الأقل.", "Enter at least one measurement.")
    if ("bp_sys" in values) != ("bp_dia" in values):
        raise UserError("أدخل الضغط الانقباضي والانبساطي معاً.", "Enter systolic and diastolic pressure together.")
    if "bp_sys" in values and values["bp_sys"] <= values["bp_dia"]:
        raise UserError("الضغط الانقباضي يجب أن يكون أعلى من الانبساطي.",
                        "Systolic pressure must be higher than diastolic pressure.")
    return values


def register_checkin(user, values, lang):
    """يحفظ القياسات ويرجع نتيجة كل قياس. التحذير والخطر يُسجَّلان في سجل التنبيهات."""
    add_checkin(user, values)
    results = []
    for key, value in values.items():
        spec = reference.checkin[key]
        level = classify_value(spec, value)
        item = {"key": key, "label": spec["label_en"] if lang == "en" else spec["label"],
                "unit": spec["unit_en"] if lang == "en" else spec["unit"],
                "value": value, "level": level, "message": "", "advice": "", "risk": risk_of(key)}
        if level in ("warning", "danger"):
            message = limit_message(spec, value, level)
            add_alert(user, level, message)
            if level == "danger":
                add_chat(user, "system", bi(f"تنبيه: {message['ar']}", f"Alert: {message['en']}"))
            item["message"] = pick(message, lang)
            item["advice"] = pick(KNOWLEDGE[key]["action"], lang)
        results.append(item)
    return results


def _knowledge(lang):
    out = {key: {part: pick(text, lang) for part, text in info.items()} for key, info in KNOWLEDGE.items()}
    for key, info in out.items():
        if risk_of(key):
            info["risk"] = risk_of(key)
    return out


def _regions(lang):
    return [{"id": r["id"], "metrics": r["metrics"], "name": pick(r["name"], lang),
             "function": pick(r["function"], lang)} for r in BODY_REGIONS]


def _hazards(lang):
    return [{"id": h["id"], "regions": h["regions"], "metrics": h["metrics"],
             "name": pick(h["name"], lang), "text": pick(h["text"], lang)} for h in BODY_HAZARDS]


UI_TEXT = {
    # مشترك
    "crew_title": bi("حالة الطاقم", "Crew status"),
    "crew_intro_admin": bi("كل أفراد الطاقم بحالتهم الحالية. بصفتك مديراً ترى القيم أيضاً.",
                           "Every crew member and their current status. As the admin you also see the values."),
    "crew_intro_member": bi("كل أفراد الطاقم بحالتهم الحالية. الأرقام الصحية تظهر لصاحبها وللمدير وطبيب الطيران فقط.",
                            "Every crew member and their current status. Health values are shown only to their owner, the admin and the flight surgeon."),
    "crew_intro_doctor": bi("كل أفراد الطاقم بحالتهم الحالية. بصفتك طبيب طيران ترى القيم، والعرض للقراءة فقط.",
                            "Every crew member and their current status. As the flight surgeon you see the values; this view is read-only."),
    "crew_active": bi("{a} من {n} نشطون الآن", "{a} of {n} active now"),
    "crew_counts": bi("خطر: {d}، تحذير: {w}، طبيعي: {k}", "Danger: {d}, warning: {w}, normal: {k}"),
    "crew_buzzer_on": bi("جرس الإنذار المشترك يعمل", "The shared alarm buzzer is ringing"),
    "crew_buzzer_off": bi("جرس الإنذار المشترك مطفأ", "The shared alarm buzzer is off"),
    "crew_you": bi("أنت", "You"), "crew_admin": bi("مدير", "Admin"), "crew_commander": bi("قائد", "Commander"),
    "crew_worst": bi("المؤشر الأهم", "Main metric"),
    "crew_activity": bi("النشاط", "Activity"), "crew_online": bi("نشط الآن", "Active now"),
    "crew_offline": bi("غير نشط", "Not active"), "crew_never_seen": bi("لم يسجل قراءات بعد", "No readings yet"),
    "crew_checkin": bi("آخر فحص ذاتي", "Last self check-in"),
    "crew_buzzer_member": bi("جرسه يعمل", "Its buzzer is on"),
    "crew_demo": bi("يجرب العرض التجريبي (تظهر قراءاته الحقيقية)", "Running the demo (real readings shown)"),
    "crew_no_data": bi("لا توجد قراءات بعد", "No readings yet"),
    "hz_title": bi("مخاطر رحلات الفضاء الخمسة", "The five spaceflight hazards"),
    "hz_intro": bi("لكل خطر: ما هو، وكيف يؤثر على جسمك، وماذا تفعل، ومتى تطلب المساعدة. المؤشرات المرتبطة به تظهر بحالتها الحالية.",
                   "For each hazard: what it is, how it affects your body, what to do and when to get help. Its linked metrics show their current status."),
    "hz_effects": bi("كيف يؤثر على جسمك", "How it affects your body"),
    "hz_prevent": bi("ماذا أفعل (الوقاية)", "What I can do (prevention)"),
    "hz_escalate": bi("متى أطلب المساعدة؟", "When should I get help?"),
    "hz_metrics": bi("المؤشرات المرتبطة", "Linked metrics"),
    "hz_no_metrics": bi("لا يوجد مؤشر مباشر لهذا الخطر. المهم هو الإجراءات المتفق عليها والتواصل المبكر.",
                        "There is no direct metric for this hazard. What matters is agreed procedures and early communication."),
    "hz_facts": bi("معلومة من ناسا", "From NASA"),
    "hz_nasa_page": bi("صفحة الخطر في برنامج أبحاث الإنسان (ناسا)", "NASA Human Research Program page"),
    "hz_related_risks": bi("مخاطر ناسا الرسمية المرتبطة بمؤشراتنا", "Related NASA risks for our metrics"),
    "dose_title": bi("الجرعة الإشعاعية التراكمية", "Cumulative radiation dose"),
    "dose_intro": bi("تُجمع قراءات الإشعاع مع الوقت لأن حد ناسا يخص مجموع الجرعات طوال المسيرة وليس القراءة اللحظية. في المحاكاة كل تحديث يمثل يوماً، وقراءة الإشعاع تُعدّ mSv في اليوم.",
                     "Radiation readings are added up over time because NASA's limit is about the total dose over a career, not the instantaneous reading. In the simulation each update stands for one day and the radiation reading counts as mSv per day."),
    "dose_total": bi("المجموع حتى الآن", "Total so far"),
    "dose_rate": bi("القراءة الحالية", "Current reading"),
    "dose_limit": bi("الحد", "Limit"),
    "dose_not_set": bi("لم يُحدد الحد بعد: يُستورد من limits.csv فقط (المؤشر radiation_total).", "The limit is not set yet: it is imported only from limits.csv (metric radiation_total)."),
    "dose_source": bi("المصدر", "Source"),
    "dose_storm_btn": bi("محاكاة عاصفة شمسية", "Simulate a solar storm"),
    "dose_storm_on": bi("عاصفة شمسية محاكاة جارية", "Simulated solar storm in progress"),
    "dose_over": bi("تجاوز الحد", "Limit reached"),
    "hz_risks_title": bi("مخاطر ناسا الرسمية على صحة الإنسان", "NASA's official human health risks"),
    "hz_risks_intro": bi("حددها برنامج أبحاث الإنسان في ناسا ضمن المخاطر الخمسة. المميزة بعلامة يراقبها AstroHab بمؤشر أو أكثر. ربط المؤشرات بها من تصميم الفريق، وصفحات ناسا لا تنص عليه.",
                         "Identified by NASA's Human Research Program within the five hazards. Those marked are watched by AstroHab through one or more metrics. Pairing metrics with them is the project's own; NASA's pages do not state it."),
    "hz_watched": bi("يراقبه التطبيق", "Watched by AstroHab"),
    "risk_label": bi("خطر ناسا المرتبط", "Related NASA risk"),
    "ex_risk": bi("خطر ناسا المرتبط بالتمرين", "Related NASA risk"),
    "hz_open_map": bi("اعرض الأجزاء المتأثرة على المجسم", "Show the affected parts on the body map"),
    "sm_title": bi("ملخص لطبيب الطيران", "Summary for the flight surgeon"),
    "sm_intro": bi("ملخص من القياسات المحفوظة في هذا الحساب. القيم المحاكاة مذكورة كذلك في عمود مصدر القراءة، ولا يدخل فيه العرض التجريبي.",
                   "A summary of the readings saved on this account. Simulated values are labelled in the reading source column, and the demo mode is never included."),
    "sm_period": bi("الفترة", "Period"), "sm_user": bi("الحساب", "Account"),
    "sm_days": bi("آخر {n} أيام", "Last {n} days"),
    "sm_pdf": bi("تنزيل PDF", "Download PDF"), "sm_csv": bi("تصدير CSV", "Export CSV"),
    "sm_current": bi("التوصية الحالية (من آخر القيم المحفوظة)", "Current recommendation (from the latest saved values)"),
    "sm_counts": bi("القراءات المحفوظة: {r}، الفحوصات الذاتية: {c}، تنبيهات التحذير: {w}، تنبيهات الخطر: {d}",
                    "Saved readings: {r}, self check-ins: {c}, warning alerts: {w}, danger alerts: {d}"),
    "sm_metrics": bi("المؤشرات", "Metrics"),
    "sm_col_metric": bi("المؤشر", "Metric"), "sm_col_source": bi("مصدر القراءة", "Reading source"),
    "sm_col_n": bi("العدد", "Count"), "sm_col_min": bi("الأدنى", "Min"), "sm_col_max": bi("الأعلى", "Max"),
    "sm_col_mean": bi("المتوسط", "Mean"), "sm_col_last": bi("الأخير", "Last"),
    "sm_col_warn": bi("قراءات تحذير", "Warning readings"), "sm_col_danger": bi("قراءات خطر", "Danger readings"),
    "sm_col_limits": bi("الحدود المرجعية", "Reference limits"), "sm_col_limit_source": bi("مصدر الحدود", "Limit source"),
    "sm_exercise": bi("التمارين: {s} جلسة مؤكدة بالزر ({m} دقيقة مسجلة)، في {d} أيام نشطة",
                      "Exercise: {s} sessions confirmed by the button ({m} minutes logged), on {d} active days"),
    "sm_ex_log": bi("سجل التمارين", "Exercise log"),
    "sm_ex_time": bi("الوقت", "Time"), "sm_ex_min": bi("الدقائق", "Minutes"),
    "sm_ex_type": bi("النوع", "Type"), "sm_ex_note": bi("ملاحظة", "Note"),
    "sm_ex_nodetails": bi("لم تُسجَّل التفاصيل", "Details not logged"),
    "sm_ex_none": bi("لا جلسات في هذه الفترة.", "No sessions in this period."),
    "sm_member": bi("رائد الفضاء", "Crew member"),
    "ex_title": bi("سجل التمارين", "Exercise log"),
    "ex_intro": bi("التمرين اليومي يحمي العظام والقلب في الجاذبية الصغرى. ضغطة زر الأردوينو تؤكد الجلسة وترفع كثافة العظام في المحاكاة (قيمة توضيحية وليست من ناسا)، ثم تسجّل هنا مدة التمرين ونوعه ليراها طبيب الطيران.",
                   "Daily exercise protects bones and the heart in microgravity. A press of the Arduino button confirms the session and raises bone density in the simulation (an illustrative value, not from NASA); then you log the minutes and type here for the flight surgeon."),
    "ex_week": bi("آخر 7 أيام", "Last 7 days"),
    "ex_week_line": bi("{s} جلسات، {d} أيام نشطة، {m} دقيقة مسجلة", "{s} sessions, {d} active days, {m} minutes logged"),
    "ex_days": bi("الجلسات في آخر 14 يوماً", "Sessions in the last 14 days"),
    "ex_bone": bi("كثافة العظام", "Bone density"),
    "ex_bone_now": bi("الآن", "Now"),
    "ex_bone_note": bi("المسار من القراءات المحفوظة. ينزل ببطء بدون تمرين ويرتفع عند تأكيد الجلسة بالزر.",
                       "The path comes from saved readings. It falls slowly without exercise and rises when a session is confirmed with the button."),
    "ex_bone_nolimits": bi("لا توجد حدود مرجعية لكثافة العظام، فلا حكم على الحالة.", "There are no reference limits for bone density, so the state is not judged."),
    "ex_log_title": bi("جلسات تنتظر التفاصيل", "Sessions waiting for details"),
    "ex_pending_none": bi("لا جلسات تنتظر التفاصيل. اضغط زر التمرين ثم سجّل مدة التمرين ونوعه هنا.",
                          "No sessions are waiting. Press the exercise button, then log the minutes and type here."),
    "ex_session_at": bi("جلسة الزر في {t}", "Button session at {t}"),
    "ex_type": bi("التمارين التي أديتها", "Exercises you did"), "ex_note": bi("ملاحظة (اختياري)", "Note (optional)"),
    "ex_minutes": bi("الدقائق", "Minutes"), "ex_save": bi("حفظ", "Save"),
    "ex_recent": bi("آخر الجلسات", "Latest sessions"), "ex_none": bi("لا جلسات بعد.", "No sessions yet."),
    "ex_kind_button": bi("مؤكدة بالزر", "Confirmed by the button"), "ex_kind_manual": bi("يدوي", "By hand"),
    "ex_no_details": bi("بلا تفاصيل", "No details"),
    "ex_saved": bi("تم الحفظ", "Saved"),
    "ex_bad_minutes": bi("أدخل عدد دقائق بين 1 و300.", "Enter a number of minutes between 1 and 300."),
    "ex_bad_type": bi("اختر تمرينًا واحدًا على الأقل.", "Choose at least one exercise."),
    "st_title_ex": bi("سلسلة التمرين", "Exercise streak"),
    "st_title_chk": bi("سلسلة الفحص الذاتي", "Check-in streak"),
    "st_days": bi("أيام متتالية", "days in a row"),
    "st_best": bi("أفضل سلسلة: {n}", "Best streak: {n}"),
    "st_done": bi("تم احتساب اليوم. ارجع غدًا لتكمل السلسلة.", "Counted today. Come back tomorrow to keep it going."),
    "st_keep": bi("سجّل اليوم لتحافظ على سلسلتك.", "Log something today to keep your streak."),
    "st_start": bi("ابدأ سلسلتك اليوم.", "Start your streak today."),
    "ex_bad_note": bi("الملاحظة أطول من 120 حرفاً.", "The note is longer than 120 characters."),
    "ex_no_session": bi("هذه الجلسة غير موجودة أو سُجّلت تفاصيلها.", "This session does not exist or already has its details."),
    "ex_min": bi("د", "min"),
    "sm_trends": bi("الاتجاهات", "Trends"), "sm_no_trends": bi("لا اتجاهات ملحوظة.", "No notable trends."),
    "sm_alerts": bi("التنبيهات", "Alerts"), "sm_no_alerts": bi("لا تنبيهات في هذه الفترة.", "No alerts in this period."),
    "sm_notes": bi("ملاحظات", "Notes"),
    "sm_note_limits": bi("الحدود المرجعية مأخوذة كما هي من بيانات ناسا أو من الملف الذي استوردته الإدارة، ومصدر كل حد مذكور في الجدول. الأداة لا تضيف حدوداً من عندها.",
                         "Reference limits are taken as they are from NASA data or the file the admin imported, and each limit's source is listed in the table. The tool adds no limits of its own."),
    "sm_note_trend": bi("الاتجاهات قاعدة كشف تغير مستمر في قراءات المستخدم نفسه، وليست حداً طبياً.",
                        "Trends are a rule that detects a steady change in the user's own readings. They are not a medical limit."),
    "lv_normal": bi("طبيعي", "Normal"), "lv_warning": bi("تحذير", "Warning"), "lv_danger": bi("خطر", "Danger"),
    "lv_unconfigured": bi("الحدود غير محددة", "Limits not set"), "lv_nodata": bi("لا توجد قراءة", "No reading"),
    "disclaimer": bi("هذه أداة تعليمية بحثية وليست جهازاً طبياً، ولا تغني عن إجراءات المهمة وأطباء الطيران.",
                     "This is an educational research tool, not a medical device. It does not replace mission procedures or flight surgeons."),
    "no_data": bi("لا توجد قراءة بعد", "No reading yet"),
    "no_limits": bi("لم تُحدد حدود مرجعية لهذا المؤشر.", "No reference limits are set for this metric."),
    "source": bi("مصدر الحد", "Limit source"),
    "never": bi("لم يُقَس بعد", "Never measured"),
    "ago_now": bi("الآن", "just now"), "ago_min": bi("قبل {n} دقيقة", "{n} min ago"),
    "ago_hour": bi("قبل {n} ساعة", "{n} h ago"), "ago_day": bi("قبل {n} يوم", "{n} d ago"),
    "record_now": bi("سجّل القياس الآن", "Record it now"),
    "go_dashboard": bi("افتح اللوحة الحية", "Open the live dashboard"),
    "kind_live": bi("قراءة حية", "Live reading"), "kind_manual": bi("إدخال يدوي", "Manual entry"),
    "measured": bi("آخر قياس", "Last measured"),
    # المجسم
    "body_title": bi("المجسم التفاعلي", "Interactive body map"),
    "body_intro": bi("اضغط على أي جزء من الجسم لترى حالته، ومعناه، وماذا تفعل، ومتى تطلب المساعدة.",
                     "Tap any part of the body to see its status, what it means, what to do and when to get help."),
    "tier_title": bi("التوصية الحالية", "Current recommendation"),
    "tier_label_0": bi("عناية ذاتية", "Self-care"), "tier_label_1": bi("أبلغ الطاقم", "Tell the crew"),
    "tier_label_2": bi("تواصل مع الأرض", "Contact Earth"), "tier_label_none": bi("بدون حدود", "No limits"),
    "demo_start": bi("تشغيل عرض تجريبي", "Start a demo"),
    "demo_hint": bi("يقود القراءات عبر: طبيعي، تحذير، خطر، ثم عودة، بقيم مشتقة من الحدود المستوردة.",
                    "Steps the readings through normal, warning, danger and recovery, using values derived from the imported limits."),
    "trends_title": bi("الاتجاهات في قياساتك", "Trends in your readings"),
    "trends_note": bi("تنبيه بتغير مستمر في قراءاتك المتتالية، وليس حداً طبياً ولا يغيّر التوصية بحد ذاته.",
                      "A heads-up about a steady change across your consecutive readings. It is not a medical limit and does not change the recommendation by itself."),
    "due_title": bi("حان وقت القياس", "Time to measure"),
    "due_text": bi("لم تُسجَّل هذه القياسات خلال آخر 24 ساعة:", "These were not recorded in the last 24 hours:"),
    "regions_title": bi("أجزاء الجسم", "Body parts"),
    "hazards_title": bi("مخاطر رحلات الفضاء الخمسة", "The five spaceflight hazards"),
    "hazards_hint": bi("اضغط على خطر لترى الأجزاء المتأثرة به.", "Tap a hazard to see the parts it affects."),
    "hazard_none": bi("هذا الخطر لا يخص عضواً بعينه، بل يؤثر على الاتصال والإخلاء الطبي.",
                      "This hazard is not tied to one organ; it affects communication and medical evacuation."),
    "linked_hazards": bi("مخاطر مرتبطة", "Linked hazards"),
    "legend": bi("الألوان: أخضر طبيعي، أصفر تحذير، أحمر خطر، رمادي بلا حدود أو بلا قراءة.",
                 "Colors: green normal, amber warning, red danger, gray no limits or no reading."),
    "s_what": bi("ما هذا المؤشر؟", "What is it?"),
    "s_space": bi("كيف يؤثر الفضاء عليه؟", "How does spaceflight affect it?"),
    "s_action": bi("ماذا أفعل؟", "What can I do?"),
    "s_escalate": bi("متى أطلب المساعدة؟", "When should I get help?"),
    # الفحص الذاتي
    "checkin_title": bi("الفحص الذاتي", "Self check-in"),
    "checkin_intro": bi("سجّل قياساتك اليومية. يمكنك إدخال قياس واحد أو أكثر، وستظهر النتيجة بالألوان مع النصيحة.",
                        "Record your daily measurements. You can enter one or more, and you will see the result in color with advice."),
    "h_bp": bi("اجلس مرتاحاً لدقائق والذراع بمستوى القلب، وقس بنفس الوضعية كل مرة.",
               "Sit at rest for a few minutes with your arm at heart level, and measure in the same position each time."),
    "h_glucose": bi("يُفضّل القياس صائماً. أدخل القراءة بوحدة mg/dL.", "Fasting is best. Enter the reading in mg/dL."),
    "sleep_nasa": bi("توصية ناسا: فترة نوم مخططة مدتها 8.5 ساعات (مع ساعتين قبل النوم وساعة ونصف بعده). هذا هدف موصى به وليس حداً أدنى. المصدر: NASA-STD-3001 المجلد الأول، القسم 6.1.",
                     "NASA recommendation: a planned sleep period of 8.5 hours (plus 2 hours before sleep and 1.5 hours after). This is a recommended target, not a minimum. Source: NASA-STD-3001 Volume 1, section 6.1."),
    "h_sleep": bi("عدد الساعات التي نمتها فعلاً الليلة الماضية، مثلاً 6.5.",
                  "Hours you actually slept last night, for example 6.5."),
    "h_mood": bi("كيف تشعر الآن؟ هذا تقييم ذاتي بسيط وليس تشخيصاً.",
                 "How do you feel right now? This is a simple self-rating, not a diagnosis."),
    "f_bp": bi("ضغط الدم", "Blood pressure"),
    "f_sys": bi("انقباضي", "Systolic"), "f_dia": bi("انبساطي", "Diastolic"),
    "mood_1": bi("منخفض جداً", "Very low"), "mood_2": bi("منخفض", "Low"), "mood_3": bi("عادي", "Okay"),
    "mood_4": bi("جيد", "Good"), "mood_5": bi("جيد جداً", "Very good"),
    "save": bi("حفظ القياسات", "Save measurements"), "saving": bi("جارٍ الحفظ", "Saving"),
    "clear": bi("مسح الحقول", "Clear fields"),
    "saved": bi("تم الحفظ.", "Saved."), "save_failed": bi("تعذر الحفظ.", "Could not save."),
    "result_title": bi("نتيجة هذا الإدخال", "Result of this entry"),
    "advice": bi("نصيحة", "Advice"),
    "see_body": bi("عرض المجسم", "Open the body map"),
    "trend_title": bi("تطور القياسات", "Measurement trend"),
    "history_title": bi("آخر الإدخالات", "Recent entries"),
    "export_csv": bi("تصدير CSV", "Export CSV"),
    "col_time": bi("الوقت", "Time"),
    "empty_history": bi("لا توجد إدخالات بعد.", "No entries yet."),
    "latest_title": bi("آخر القيم المسجلة", "Latest recorded values"),
}


# نصوص الشريط العلوي (نداء المساعدة وتنبيهات الطاقم): تصل للواجهة جاهزة بلغة المستخدم
TOP_UI = {
    "sos": bi("نداء مساعدة", "Call for help"),
    "sos_confirm": bi("اضغط مرة أخرى للتأكيد", "Press again to confirm"),
    "sos_cancel": bi("إلغاء النداء", "Cancel call"),
    "help_mine": bi("نداء المساعدة نشط والطاقم يراه.", "Your help call is active and the crew can see it."),
    "help_other": bi("{name} يطلب المساعدة", "{name} is asking for help"),
    "danger_other": bi("{name} في حالة خطر", "{name} is in danger"),
    "ack": bi("أنا معه", "I am with them"),
    "ack_you": bi("أنت في طريقك إليه", "You are going to them"),
    "ack_by": bi("في طريقهم: {names}", "On their way: {names}"),
    "ack_none": bi("لا أحد في طريقه بعد", "No one is on the way yet"),
    "open_crew": bi("شاشة الطاقم", "Crew screen"),
    "press": bi("تم ضغط زر التمرين. هل هذا أنت؟", "The exercise button was pressed. Was it you?"),
    "press_claim": bi("أنا", "It was me"),
    "log_pending": bi("تمرينك مؤكد. سجّل مدته ونوعه.", "Your exercise is confirmed. Log its minutes and type."),
    "log_open": bi("سجّل التمرين", "Log exercise"),
}


ADMIN_UI = {
    "col_name": bi("الاسم", "Name"), "col_role": bi("الدور", "Role"), "col_created": bi("تاريخ الإنشاء", "Created"),
    "col_readings": bi("عدد القراءات", "Readings"), "col_change": bi("تغيير الدور", "Change role"),
    "save": bi("حفظ", "Save"), "saved": bi("تم الحفظ", "Saved"), "failed": bi("تعذر الحفظ", "Could not save"),
    "users": bi("المستخدمون", "Users"),
    "doctor_note": bi("طبيب الطيران يرى حالة الطاقم وأرقامه وملخصاتهم للقراءة فقط، ولا يُحسب من الطاقم. حوّل الحساب بعد أن ينشئه صاحبه.",
                      "A flight surgeon sees the crew status, values and summaries read-only and does not count as crew. Switch the account after its owner has created it."),
    "alerts": bi("آخر التنبيهات", "Latest alerts"), "all_users": bi("كل المستخدمين", "All users"),
    "col_time": bi("الوقت", "Time"), "col_user": bi("المستخدم", "User"), "col_level": bi("المستوى", "Level"),
    "col_reason": bi("السبب", "Reason"), "no_alerts": bi("لا توجد تنبيهات.", "No alerts."),
    "danger": bi("خطر", "Danger"), "warning": bi("تحذير", "Warning"),
}


def _ui(lang):
    return {key: pick(text, lang) for key, text in UI_TEXT.items()}


app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=64 * 1024)  # كل الطلبات صغيرة: لا حاجة لقبول أجسام كبيرة

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


_DOCTOR_ALLOWED = ("/crew", "/api/crew", "/summary", "/hazards", "/nasa", "/api/nasa", "/lang", "/logout", "/login", "/static")


@app.before_request
def _role_gate():
    """يقرأ الدور من قاعدة البيانات في كل طلب (فتغيير المدير للدور يسري فوراً)، ويقصر طبيب الطيران على صفحات القراءة."""
    user = session.get("user")
    if not user:
        return None
    role = get_role(user)
    if role and session.get("role") != role:
        session["role"] = role
    if session.get("role") != "doctor":
        return None
    path = request.path
    if path == "/":
        return redirect("/crew")
    if any(path == a or path.startswith(a + "/") or path.startswith(a + ".") for a in _DOCTOR_ALLOWED):
        return None
    if path.startswith("/api/"):
        return jsonify({"error": "read-only role"}), 403
    return redirect("/crew")


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", CSP)
    if request.endpoint != "static":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _limits_for(lang, source=None):
    """الحدود المرجعية مع اسم ووحدة كل مؤشر بلغة الواجهة (المؤشرات الحية افتراضياً)."""
    out = {}
    for key, spec in (reference.current if source is None else source).items():
        item = dict(spec)
        item["source"] = src(spec, lang)
        if lang == "en":
            item["label"], item["unit"] = spec["label_en"], spec["unit_en"]
        out[key] = item
    return out


def render_page(name, **ctx):
    lang = _lang()
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    ctx.update(csrf_token=session["csrf"], user=session.get("user"), role=session.get("role"),
               limits=_limits_for(lang), limits_version=reference.version, path=request.path,
               topui={k: pick(v, lang) for k, v in TOP_UI.items()},
               demo=engine.demo_info(session["user"], lang) if session.get("user") else {"active": False})
    html = ENVS[lang].get_template(name).render(**ctx)
    other_code, other_name = ("en", "English") if lang == "ar" else ("ar", "العربية")
    switch = f'<a class="langsw" href="/lang/{other_code}?next={quote(request.path)}">{other_name}</a>'
    return (html.replace("<!--LANGSWITCH-->", switch)
                .replace("__LOCALE__", "en-US" if lang == "en" else "ar-SA")
                .replace("__CHART_JS__", _chart_head()))


def _csrf_ok():
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
    return bool(session.get("csrf")) and hmac.compare_digest(sent, session["csrf"])


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": T("هذا الإجراء للمدير فقط.")}), 403
            abort(403)
        return view(*args, **kwargs)
    return login_required(wrapper)


_guard = threading.Lock()
_login_fails = {}      # (جهاز، اسم مستخدم) -> أوقات المحاولات الفاشلة
_ip_fails = {}         # جهاز -> أوقات المحاولات الفاشلة
_register_times = {}   # جهاز -> أوقات محاولات إنشاء حساب


def _client_ip():
    return request.remote_addr or "?"


def _is_loopback(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (getattr(addr, "ipv4_mapped", None) or addr).is_loopback


def _recent(times, window):
    now = time.time()
    return [t for t in times if now - t < window]


def _login_blocked(ip, username):
    with _guard:
        key = (ip, username.lower())
        _login_fails[key] = _recent(_login_fails.get(key, []), Config.LOGIN_LOCK_SECONDS)
        _ip_fails[ip] = _recent(_ip_fails.get(ip, []), Config.LOGIN_LOCK_SECONDS)
        return (len(_login_fails[key]) >= Config.LOGIN_MAX_FAILS
                or len(_ip_fails[ip]) >= Config.LOGIN_MAX_FAILS_PER_IP)


def _login_failed(ip, username):
    with _guard:
        now = time.time()
        _login_fails.setdefault((ip, username.lower()), []).append(now)
        _ip_fails.setdefault(ip, []).append(now)
        if len(_login_fails) > 2000:  # سقف للذاكرة: نحذف المنتهي
            for table in (_login_fails, _ip_fails):
                for key in [k for k, v in table.items() if not _recent(v, Config.LOGIN_LOCK_SECONDS)]:
                    del table[key]


def _login_succeeded(ip, username):
    with _guard:
        _login_fails.pop((ip, username.lower()), None)


def _register_allowed(ip):
    with _guard:
        times = _recent(_register_times.get(ip, []), 3600)
        allowed = len(times) < Config.REGISTER_PER_HOUR
        if allowed:
            times.append(time.time())
        _register_times[ip] = times
        return allowed


def register_account(username, password, invite_code, ip):
    """إنشاء حساب بعد فحوص الوصول. يرجع (نجح، رسالة خطأ).

    الحساب الأول (المدير) يُنشأ من الحاسوب نفسه فقط، حتى لا يسبقك إليه جهاز آخر على الشبكة.
    وإن ضُبط REGISTRATION_CODE فالحسابات اللاحقة تتطلب رمز الدعوة.
    """
    if not _register_allowed(ip):
        return False, "محاولات تسجيل كثيرة من هذا الجهاز. حاول لاحقاً."
    if not users_exist():
        if not Config.ALLOW_REMOTE_FIRST_ADMIN and not _is_loopback(ip):
            return False, "أنشئ حساب المدير الأول من الحاسوب نفسه (localhost) وليس من جهاز آخر."
    elif Config.REGISTRATION_CODE and not hmac.compare_digest(
            (invite_code or "").encode(), Config.REGISTRATION_CODE.encode()):
        return False, "رمز الدعوة غير صحيح."
    return create_user(username, password)


@app.route("/login", methods=["GET", "POST"])
def login():
    error, status = None, 200
    if request.method == "POST":
        if not _csrf_ok():
            abort(400)
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip = _client_ip()
        if _login_blocked(ip, username):
            error, status = "محاولات كثيرة فاشلة. حاول بعد بضع دقائق.", 429
        else:
            if request.form.get("action") == "register":
                ok, message = register_account(username, password, request.form.get("invite_code", ""), ip)
                error = None if ok else message
            if error is None:
                role = verify_user(username, password)
                if role:
                    _login_succeeded(ip, username)
                    lang = session.get("lang")
                    session.clear()
                    session.update(user=username, role=role, csrf=secrets.token_hex(16))
                    if lang:
                        session["lang"] = lang
                    return redirect(url_for("home"))
                error = "اسم المستخدم أو كلمة المرور غير صحيحة."
                _login_failed(ip, username)
    need_code = bool(Config.REGISTRATION_CODE) and users_exist()
    return render_page("login", error=T(error) if error else None, need_code=need_code), status


@app.route("/logout", methods=["POST"])
def logout():
    if not _csrf_ok():
        abort(400)
    lang = session.get("lang")
    session.clear()
    if lang:
        session["lang"] = lang
    return redirect(url_for("login"))


@app.route("/lang/<code>")
def set_lang(code):
    if code in ("ar", "en"):
        session["lang"] = code
    target = request.args.get("next", "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    return redirect(target)


@app.route("/")
@login_required
def home():
    engine.start_session(session["user"])
    return render_page("dashboard", page="dashboard")


@app.route("/history")
@login_required
def history_page():
    return render_page("history", page="history")


@app.route("/nasa")
@login_required
def nasa_page():
    lang = _lang()
    return render_page("nasa", page="nasa", datasets=list_datasets(),
                       limits_all={**_limits_for(lang), **_limits_for(lang, reference.checkin)})


@app.route("/crew")
@login_required
def crew_page():
    if session.get("role") != "doctor":  # طبيب الطيران ليس له جلسة قراءات
        engine.start_session(session["user"])
    return render_page("crew", page="crew", ui=_ui(_lang()))


@app.route("/api/crew")
@login_required
def api_crew():
    return jsonify(crew_state(session.get("role"), session["user"], _lang()))


@app.route("/api/crew/alerts")
@login_required
def api_crew_alerts():
    if session.get("role") != "doctor":
        engine.touch(session["user"])
    return jsonify(crew_alerts(session["user"], session.get("role"), _lang()))


@app.route("/api/crew/help", methods=["POST"])
@login_required
def api_crew_help():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    if session.get("role") == "doctor":
        return jsonify({"error": "read-only role"}), 403
    action = (request.get_json(silent=True) or {}).get("action")
    if action not in ("call", "cancel"):
        return jsonify({"error": "bad action"}), 400
    engine.start_session(session["user"])
    set_help_call(session["user"], action == "call")
    return jsonify({"help_active": session["user"] in engine.help_calls})


@app.route("/api/crew/ack", methods=["POST"])
@login_required
def api_crew_ack():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    target = str((request.get_json(silent=True) or {}).get("target") or "")[:64]
    ok = ack_crew_alert(session["user"], session.get("role"), target)
    return jsonify({"ok": ok}), (200 if ok else 404)


@app.route("/api/crew/claim", methods=["POST"])
@login_required
def api_crew_claim():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    if session.get("role") == "doctor":
        return jsonify({"error": "read-only role"}), 403
    ok = claim_exercise(session["user"])
    return jsonify({"ok": ok}), (200 if ok else 404)


@app.route("/exercise")
@login_required
def exercise_page():
    lang = _lang()
    engine.start_session(session["user"])
    return render_page("exercise", page="exercise", ui=_ui(lang), fitness_risk=risk_of_key("fitness"))


@app.route("/api/exercise", methods=["GET", "POST"])
@login_required
def api_exercise():
    user = session["user"]
    engine.start_session(user)
    if request.method == "POST":
        if not _csrf_ok():
            return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
        body = request.get_json(silent=True) or {}
        ui = _ui(_lang())
        try:
            minutes = int(float(body.get("minutes")))
            ex_id = int(body.get("id"))
        except (TypeError, ValueError):
            return jsonify({"error": ui["ex_bad_minutes"]}), 400
        if not 1 <= minutes <= 300:
            return jsonify({"error": ui["ex_bad_minutes"]}), 400
        chosen = body.get("activities")
        if (not isinstance(chosen, list) or not chosen or len(set(chosen)) != len(chosen)
                or any(c not in EXERCISE_TYPES for c in chosen)):
            return jsonify({"error": ui["ex_bad_type"]}), 400
        activity = ",".join(chosen)
        note = str(body.get("note") or "").strip()
        if len(note) > EXERCISE_NOTE_MAX:
            return jsonify({"error": ui["ex_bad_note"]}), 400
        if not complete_exercise(user, ex_id, minutes, activity, note):
            return jsonify({"error": ui["ex_no_session"]}), 404
    return jsonify(exercise_overview(user, _lang()))


@app.route("/hazards")
@login_required
def hazards_page():
    lang = _lang()
    return render_page("hazards", page="hazards", ui=_ui(lang), hazards=_hazard_page(lang), risk_groups=_risk_groups(lang))


def _summary_days():
    return max(1, min(request.args.get("days", 7, type=int), 90))


def _summary_target():
    """صاحب الملخص: المدير وطبيب الطيران يختاران أي فرد من الطاقم (?user=)، وغيرهما يرى ملخصه فقط."""
    me, role = session["user"], session.get("role")
    if role not in ("admin", "doctor"):
        return me, []
    crew = [u["username"] for u in list_users() if u["role"] != "doctor"]
    want = (request.args.get("user") or "").strip()
    if want in crew:
        return want, crew
    if role == "doctor" and crew:
        return crew[0], crew
    return me, crew


@app.route("/summary")
@login_required
def summary_page():
    lang = _lang()
    target, crew = _summary_target()
    return render_page("summary", page="summary", ui=_ui(lang), s=build_summary(target, _summary_days(), lang), crew=crew)


@app.route("/summary.pdf")
@login_required
def summary_pdf():
    lang = _lang()
    target, _ = _summary_target()
    s = build_summary(target, _summary_days(), lang)
    try:
        data = build_summary_pdf(s, lang)
    except ImportError:
        return Response("PDF export needs the reportlab package: pip install reportlab", status=503, mimetype="text/plain")
    except RuntimeError as exc:
        return Response(str(exc), status=503, mimetype="text/plain")
    name = _safe_filename(target)
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=astrohab_summary_{name}.pdf"})


@app.route("/summary.csv")
@login_required
def summary_csv():
    target, _ = _summary_target()
    s = build_summary(target, _summary_days(), _lang())
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "unit", "kind", "reading_source", "readings", "min", "max", "mean", "last",
                     "warning_readings", "danger_readings", "reference_limits", "limit_source"])
    for m in s["metrics"]:
        writer.writerow([m["label"], m["unit"], m["kind"], m["reading_source"], m["n"], m["min"], m["max"], m["mean"],
                         m["last"], m["warning_n"], m["danger_n"], m["limits"], m["limit_source"]])
    name = _safe_filename(target)
    return Response("﻿" + buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=astrohab_summary_{name}.csv"})


@app.route("/body")
@login_required
def body_page():
    lang = _lang()
    engine.start_session(session["user"])
    return render_page("body", page="body", ui=_ui(lang), knowledge=_knowledge(lang),
                       regions=_regions(lang), hazards=_hazards(lang))


@app.route("/checkin")
@login_required
def checkin_page():
    lang = _lang()
    return render_page("checkin", page="checkin", ui=_ui(lang), knowledge=_knowledge(lang),
                       climits=_limits_for(lang, reference.checkin), keys=list(CHECKIN_KEYS),
                       valid={k: v["valid"] for k, v in CHECKIN_INFO.items()})


@app.route("/api/body")
@login_required
def api_body():
    return jsonify(body_state(session["user"], _lang()))


@app.route("/api/checkin", methods=["POST"])
@login_required
def api_checkin():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    try:
        values = parse_checkin(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({"error": err_text(exc)}), 400
    user, lang = session["user"], _lang()
    user_lang[user] = lang
    results = register_checkin(user, values, lang)
    return jsonify({"results": results, "escalation": body_state(user, lang)["escalation"],
                    "trends": checkin_trends(user, lang)})


def dose_state(username, lang="en"):
    """الجرعة التراكمية للمستخدم مقارنة بحد limits.csv (إن وُجد). بلا حد لا يُحكم بشيء."""
    with engine.lock:
        s = engine.sessions.get(username)
        live = s is not None
        dose = s["dose"] if s else get_dose(username)
        storm = s["storm"] if s else 0
        rate = s["vitals"].get("radiation") if s else None
    spec = reference.dose
    warn, danger = spec["warning"][1], spec["danger"][1]
    limit = danger if danger is not None else warn
    level = "unconfigured"
    if limit is not None:
        level = "danger" if danger is not None and dose >= danger else \
                ("warning" if warn is not None and dose >= warn else "normal")
    return {"dose": round(dose, 3), "rate": rate, "limit": limit, "configured": limit is not None,
            "fraction": (min(dose / limit, 1.0) if limit else None), "level": level, "source": src(spec, lang),
            "storm": storm, "live": live, "unit": "mSv"}


@app.route("/api/dose")
@login_required
def api_dose():
    return jsonify(dose_state(session["user"], _lang()))


@app.route("/api/storm", methods=["POST"])
@login_required
def api_storm():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    engine.start_storm(session["user"])
    return jsonify(dose_state(session["user"], _lang()))


@app.route("/api/demo", methods=["POST"])
@login_required
def api_demo():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    action = (request.get_json(silent=True) or {}).get("action")
    user, lang = session["user"], _lang()
    if action == "start":
        try:
            engine.start_demo(user)
        except UserError as exc:
            return jsonify({"error": err_text(exc)}), 400
    elif action == "stop":
        engine.stop_demo(user)
    else:
        return jsonify({"error": UserError("إجراء غير معروف.", "Unknown action.").text(lang)}), 400
    return jsonify({"demo": engine.demo_info(user, lang)})


@app.route("/demo/stop", methods=["POST"])
@login_required
def demo_stop():
    if _csrf_ok():
        engine.stop_demo(session["user"])
    target = request.form.get("next", "/")
    return redirect(target if target.startswith("/") and not target.startswith("//") else "/")


@app.route("/api/checkins")
@login_required
def api_checkins():
    limit = max(1, min(request.args.get("limit", 60, type=int), 1000))
    return jsonify({"rows": get_checkins(session["user"], limit), "trends": checkin_trends(session["user"], _lang()),
                    "streak": checkin_streak(session["user"])})


@app.route("/export_checkins.csv")
@login_required
def export_checkins_csv():
    rows = get_checkins(session["user"], 100000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["time", *CHECKIN_KEYS])
    for r in rows:
        writer.writerow([r["ts"], *(r[k] for k in CHECKIN_KEYS)])
    name = _safe_filename(session["user"])
    return Response("﻿" + buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=astrohab_checkins_{name}.csv"})


@app.route("/admin")
@admin_required
def admin_page():
    lang = _lang()
    users = list_users()
    for u in users:
        u["role_label"] = pick(ROLE_LABEL.get(u["role"], ROLE_LABEL["commander"]), lang)
    adm = {k: pick(v, lang) for k, v in ADMIN_UI.items()}
    return render_page("admin", page="admin", users=users, alerts=get_alerts(limit=50, lang=lang), adm=adm,
                       role_options=[(r, pick(ROLE_LABEL[r], lang)) for r in ASSIGNABLE_ROLES])


@app.route("/api/admin/role", methods=["POST"])
@admin_required
def api_admin_role():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    body = request.get_json(silent=True) or {}
    ok, why = set_user_role(str(body.get("username") or "")[:64], str(body.get("role") or ""))
    if not ok:
        return jsonify({"error": why}), (404 if why == "no_user" else 400)
    return jsonify({"ok": True})


@app.route("/api/data")
@login_required
def api_data():
    user = session["user"]
    snap = engine.snapshot(user)
    if snap is None:
        engine.start_session(user)
        snap = engine.snapshot(user)
    lang = _lang()
    user_lang[user] = lang
    snap["chat"] = get_chat(user, 100, lang)
    snap["reason"] = pick(snap["reason"], lang)
    snap["hardware"] = hardware_status["connected"]
    snap["limits_version"] = reference.version
    return jsonify(snap)


@app.route("/api/send", methods=["POST"])
@login_required
def api_send():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    prompt = ((request.get_json(silent=True) or {}).get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": T("الرسالة فارغة.")}), 400
    if len(prompt) > 500:
        return jsonify({"error": T("الرسالة طويلة، الحد الأقصى 500 حرف.")}), 400
    engine.start_session(session["user"])
    user_lang[session["user"]] = _lang()
    ok, message = ask_assistant(session["user"], prompt, user_initiated=True)
    return jsonify({"status": "ok" if ok else "limited", "message": T(message)}), (200 if ok else 429)


@app.route("/api/buzzer", methods=["POST"])
@login_required
def api_buzzer():
    if not _csrf_ok():
        return jsonify({"error": T("رمز الحماية غير صالح.")}), 400
    on = bool((request.get_json(silent=True) or {}).get("state"))
    user = session["user"]
    user_lang[user] = _lang()
    engine.start_session(user)
    engine.set_buzzer(user, on, manual=True)
    add_chat(user, "system", "تم تشغيل جرس الإنذار يدوياً." if on else "تم إيقاف جرس الإنذار يدوياً.")
    return jsonify({"status": "ok", "buzzer": int(on)})


@app.route("/api/history")
@login_required
def api_history():
    limit = max(1, min(request.args.get("limit", 300, type=int), 2000))
    user = session["user"]
    return jsonify({"rows": get_history(user, limit), "alerts": get_alerts(user, 30, _lang())})


def _safe_filename(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "") or "user"


@app.route("/export.csv")
@login_required
def export_csv():
    rows = get_history(session["user"], 100000)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["time", *METRICS, "level"])
    for r in rows:
        writer.writerow([r["ts"], *(r[m] for m in METRICS), r["level"]])
    return Response("\ufeff" + buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=astrohab_{_safe_filename(session['user'])}.csv"})


@app.route("/api/nasa/series")
@login_required
def api_nasa_series():
    series = get_series(request.args.get("file", ""), request.args.get("column", ""))
    if series is None:
        return jsonify({"error": T("الملف أو العمود غير موجود.")}), 404
    return jsonify(series)


def _json_body():
    if not _csrf_ok():
        abort(400)
    return request.get_json(silent=True) or {}


def _derive_from_request(body):
    """يقرأ طلب الاشتقاق ويحسب الحدود من العمود المحدد. يرفع ValueError عند الخطأ."""
    metric = body.get("metric")
    if metric not in ALL_INFO:
        raise UserError("مؤشر غير معروف.", "Unknown metric.")
    try:
        warn_pct, danger_pct = float(body.get("warn_pct")), float(body.get("danger_pct"))
    except (TypeError, ValueError):
        raise UserError("النسبتان المئويتان يجب أن تكونا رقمين.", "Both percentiles must be numbers.")
    data = read_column(body.get("file"), body.get("column"))
    if data is None:
        raise UserError("الملف أو العمود غير موجود.", "File or column not found.")
    derived = derive_limits(data[1], body.get("direction"), warn_pct, danger_pct)
    return metric, warn_pct, danger_pct, derived


@app.route("/api/reference/preview", methods=["POST"])
@admin_required
def api_reference_preview():
    try:
        _, _, _, derived = _derive_from_request(_json_body())
    except ValueError as exc:
        return jsonify({"error": err_text(exc)}), 400
    return jsonify(derived)


@app.route("/api/reference/save", methods=["POST"])
@admin_required
def api_reference_save():
    body = _json_body()
    try:
        metric, warn_pct, danger_pct, d = _derive_from_request(body)
    except ValueError as exc:
        return jsonify({"error": err_text(exc)}), 400
    replay = bool(body.get("replay")) and metric in METRIC_INFO  # إعادة التشغيل للمؤشرات الحية فقط
    source = f"{body['file']} / {body['column']} / P{warn_pct:g}, P{danger_pct:g}"
    save_reference_row(
        metric, warn_low=d["warning"][0], warn_high=d["warning"][1],
        danger_low=d["danger"][0], danger_high=d["danger"][1],
        scale_min=d["scale"][0], scale_max=d["scale"][1],
        unit=str(body.get("unit") or "")[:16], source=source,
        replay_file=body["file"] if replay else None, replay_column=body["column"] if replay else None)
    reference.reload()
    return jsonify({"ok": True})


@app.route("/api/reference/import", methods=["POST"])
@admin_required
def api_reference_import():
    _json_body()
    try:
        rows = parse_limits_csv()
    except ValueError as exc:
        return jsonify({"error": err_text(exc)}), 400
    existing = {r["metric"]: r for r in get_reference_rows()}
    for row in rows:
        metric = row.pop("metric")
        old = existing.get(metric) or {}  # الاستيراد لا يمسح مصدر إعادة التشغيل المحفوظ للمؤشر
        save_reference_row(metric, replay_file=old.get("replay_file"),
                           replay_column=old.get("replay_column"), **row)
    reference.reload()
    return jsonify({"ok": True, "imported": len(rows)})


@app.route("/api/reference/clear", methods=["POST"])
@admin_required
def api_reference_clear():
    metric = _json_body().get("metric")
    if metric not in ALL_INFO and metric != DOSE_KEY:
        return jsonify({"error": T("مؤشر غير معروف.")}), 400
    delete_reference_row(metric)
    reference.reload()
    return jsonify({"ok": True})
