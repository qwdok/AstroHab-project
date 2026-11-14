# AstroHab part: 07_nasa_data. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 8. بيانات ناسا المفتوحة
# ============================================================
def _nasa_dir():
    Config.NASA_DIR.mkdir(parents=True, exist_ok=True)
    return Config.NASA_DIR


_dataset_cache = {}  # اسم الملف -> ((وقت التعديل، الحجم)، الوصف): لا نعيد قراءة الملفات الكبيرة كل مرة


def list_datasets():
    """يعدّد ملفات CSV في data/nasa مع أعمدتها وعدد صفوفها (ما عدا limits.csv فهو ملف حدود)."""
    out = []
    for path in sorted(_nasa_dir().glob("*.csv")):
        if path.name.lower() == "limits.csv":
            continue
        try:
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
            cached = _dataset_cache.get(path.name)
            if cached and cached[0] == stamp:
                out.append(cached[1])
                continue
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []
                rows = sum(1 for _ in reader)
            item = {"file": path.name, "columns": columns, "rows": rows}
            _dataset_cache[path.name] = (stamp, item)
            out.append(item)
        except (OSError, csv.Error):
            continue
    return out


def read_column(file, column):
    """يقرأ القيم الرقمية لعمود من ملف في data/nasa (الصفوف غير الرقمية تُتجاهل).

    يرجع (labels, values) أو None إذا لم يوجد الملف أو العمود.
    """
    path = _nasa_dir() / Path(file or "").name  # Path.name يمنع الخروج من المجلد
    if path.suffix.lower() != ".csv" or path.name.lower() == "limits.csv" or not path.is_file():
        return None
    labels, values = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            return None
        first = reader.fieldnames[0]
        for i, row in enumerate(reader):
            try:
                values.append(float(row[column]))
            except (TypeError, ValueError):
                continue
            labels.append(row.get(first) or str(i))
    return labels, values


def get_series(file, column, limit=500):
    """نفس read_column لكن مع تقليل العينات لأغراض الرسم."""
    data = read_column(file, column)
    if data is None:
        return None
    labels, values = data
    step = max(1, math.ceil(len(values) / limit))
    return {"labels": labels[::step], "values": values[::step]}


def percentile(values, pct):
    """النسبة المئوية بالاستيفاء الخطي."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct / 100
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def derive_limits(values, direction, warn_pct, danger_pct):
    """يشتق حدود التحذير والخطر من توزيع العمود المرجعي.

    direction: high (القيم العالية خطرة) أو low أو both.
    الحد الأعلى = النسبة المئوية warn_pct / danger_pct، والأدنى = المتممة (100 - النسبة).
    """
    if direction not in ("high", "low", "both"):
        raise UserError("اتجاه غير صالح.", "Invalid direction.")
    if not 50 <= warn_pct < danger_pct <= 100:
        raise UserError("يجب أن يكون: 50 <= نسبة التحذير < نسبة الخطر <= 100.",
                        "Required: 50 <= warning percentile < danger percentile <= 100.")
    if len(values) < 30:
        raise UserError("البيانات قليلة (أقل من 30 قراءة رقمية) ولا تكفي لاشتقاق حدود.",
                        "Too little data (fewer than 30 numeric readings) to derive limits.")
    r = lambda x: round(x, 4)
    out = {"warning": [None, None], "danger": [None, None]}
    if direction in ("high", "both"):
        out["warning"][1] = r(percentile(values, warn_pct))
        out["danger"][1] = r(percentile(values, danger_pct))
    if direction in ("low", "both"):
        out["warning"][0] = r(percentile(values, 100 - warn_pct))
        out["danger"][0] = r(percentile(values, 100 - danger_pct))
    low, high = min(values), max(values)
    pad = (high - low) * 0.05 or 1
    out["scale"] = [r(low - pad), r(high + pad)]
    out["count"] = len(values)
    return out


def parse_limits_csv():
    """يقرأ data/nasa/limits.csv ويرجع قائمة حدود جاهزة للحفظ."""
    path = _nasa_dir() / "limits.csv"
    if not path.is_file():
        raise UserError("الملف data/nasa/limits.csv غير موجود.", "The file data/nasa/limits.csv does not exist.")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            metric = (row.get("metric") or "").strip()
            if metric not in ALL_INFO and metric != DOSE_KEY:
                raise UserError(f"السطر {line_no}: المؤشر '{metric}' غير معروف.",
                                f"Line {line_no}: unknown metric '{metric}'.")

            def num(name):
                text = (row.get(name) or "").strip()
                if not text:
                    return None
                try:
                    return float(text)
                except ValueError:
                    raise UserError(f"السطر {line_no}: قيمة غير رقمية في العمود {name}.",
                                        f"Line {line_no}: non-numeric value in column {name}.")

            wl, wh, dl, dh = (num(n) for n in ("warning_low", "warning_high", "danger_low", "danger_high"))
            given = [v for v in (wl, wh, dl, dh) if v is not None]
            if not given:
                raise UserError(f"السطر {line_no}: لا يوجد أي حد للمؤشر {metric}.",
                                f"Line {line_no}: no limit given for metric {metric}.")
            low, high = min(given), max(given)
            pad = (high - low) or abs(high) or 1
            smin, smax = num("scale_min"), num("scale_max")
            if smin is None:
                smin = max(0.0, low - pad) if low >= 0 else low - pad
            if smax is None:
                smax = high + pad
            rows.append({"metric": metric, "warn_low": wl, "warn_high": wh, "danger_low": dl,
                         "danger_high": dh, "scale_min": smin, "scale_max": smax,
                         "unit": (row.get("unit") or "").strip(),
                         "source": (row.get("source") or "limits.csv").strip()})
    if not rows:
        raise UserError("الملف limits.csv فارغ.", "The file limits.csv is empty.")
    return rows


class ReferenceStore:
    """الحدود المرجعية الحالية، ومصادر إعادة تشغيل القراءات من بيانات ناسا.

    current: قاموس لكل مؤشر فيه الاسم والوحدة والمجال والحدود والمصدر.
    replay:  قاموس مؤشر -> قائمة قيم من عمود مرجعي (إن اختارها المدير).
    version: يزيد مع كل تغيير حتى تعيد اللوحة المفتوحة تحميل نفسها.
    """

    def __init__(self):
        self.current = self._build({}, {})
        self.checkin = self._build({}, {}, CHECKIN_INFO)  # حدود مؤشرات الفحص الذاتي
        self.dose = self._build({}, {}, DOSE_INFO)[DOSE_KEY]
        self.replay = {}
        self.version = 0

    @staticmethod
    def _build(rows, replay, infos=METRIC_INFO):
        out = {}
        for key, info in infos.items():
            r = rows.get(key)
            has_scale = bool(r) and r["scale_min"] is not None and r["scale_max"] is not None
            limits = [r["warn_low"], r["warn_high"], r["danger_low"], r["danger_high"]] if r else [None] * 4
            out[key] = {
                "label": info["label"],
                "label_en": info["label_en"],
                "unit": (r["unit"] if r and r["unit"] else info["unit"]),
                "unit_en": (r["unit"] if r and r["unit"] else info["unit_en"]),
                "scale": [r["scale_min"], r["scale_max"]] if has_scale else list(info["scale"]),
                "warning": limits[0:2],
                "danger": limits[2:4],
                "source": (r["source"] or "") if r else "",
                "configured": any(v is not None for v in limits),
                "replay": key in replay,
            }
        return out

    def reload(self):
        rows = {r["metric"]: r for r in get_reference_rows()}
        replay = {}
        for key, r in rows.items():
            if r["replay_file"] and r["replay_column"] and key in METRIC_INFO:
                data = read_column(r["replay_file"], r["replay_column"])
                if data and data[1]:
                    replay[key] = data[1][:20000]
        self.current = self._build(rows, replay)
        self.checkin = self._build(rows, {}, CHECKIN_INFO)
        self.dose = self._build(rows, {}, DOSE_INFO)[DOSE_KEY]
        self.replay = replay
        self.version += 1


reference = ReferenceStore()

# نص مصدر الحد يأتي من limits.csv بالإنجليزية. هنا ترجمة العبارة المشتقة وعبارات المصادر الشائعة للواجهة العربية فقط
# (لا أرقام حدود هنا؛ الحدود نفسها من limits.csv فقط).
SOURCE_AR = (
    ("US government reference: NIH MedlinePlus, Pulse Oximetry: contact a provider at 92% or lower (warning, whole-number readings) and seek immediate attention at 88% or lower (danger)",
     "مرجع حكومي أمريكي: NIH MedlinePlus، قياس التأكسج: تواصل مع الطبيب عند 92% أو أقل (تحذير، قراءات بأعداد صحيحة) واطلب عناية طبية فورية عند 88% أو أقل (خطر)"),
    ("US government reference: NIH NIDDK, Low Blood Glucose: a reading lower than 70 mg/dL is low",
     "مرجع حكومي أمريكي: NIH NIDDK، انخفاض سكر الدم: القراءة الأقل من 70 ملغ/ديسيلتر منخفضة"),
    ("US government reference: NIH MedlinePlus, Fever: an adult probably has a fever above 37.2 to 37.5 C by mouth (warning); contact a provider right away if it stays above 39.4 C (danger)",
     "مرجع حكومي أمريكي: NIH MedlinePlus، الحمى: يُرجّح أن البالغ مصاب بحمى إذا تجاوزت حرارته 37.2 إلى 37.5 °م بالفم (تحذير)، وتواصل مع الطبيب فوراً إذا استمرت فوق 39.4 °م (خطر)"),
    ("Danger = US government reference: NIH NHLBI, hypertensive crisis higher than 180 systolic",
     "الخطر = مرجع حكومي أمريكي: NIH NHLBI، أزمة ضغط الدم: أعلى من 180 انقباضي"),
    ("Danger = US government reference: NIH NHLBI, hypertensive crisis higher than 120 diastolic",
     "الخطر = مرجع حكومي أمريكي: NIH NHLBI، أزمة ضغط الدم: أعلى من 120 انبساطي"),
    ("Warning =", "التحذير ="),
    ("Derived from NASA data", "مشتق من بيانات ناسا"),
    ("95th percentile of heart rate", "المئين 95 للنبض"),
    ("warning =", "التحذير ="),
    ("Danger =", "الخطر ="),
    ("windows,", "نافذة،"),
    ("subjects,", "شخصاً،"),
    ("NASA Crew State Monitoring dataset", "مجموعة بيانات ناسا Crew State Monitoring"),
    ("(above 130 at rest)", "(فوق 130 في الراحة)"),
    ("(below 30)", "(تحت 30)"),
    ("(astronaut medical selection standard)", "(معيار طبي لاختيار الرواد)"),
    ("sustained systolic 140 mmHg or higher", "ضغط انقباضي 140 ملم زئبق أو أكثر بشكل مستمر"),
    ("sustained diastolic 90 mmHg or higher", "ضغط انبساطي 90 ملم زئبق أو أكثر بشكل مستمر"),
    ("hip and spine at or above 95% of pre-mission value", "الورك والعمود الفقري 95% أو أكثر من قيمة ما قبل المهمة"),
    ("career effective dose less than 600 mSv", "الجرعة الفعالة طوال المسيرة أقل من 600 mSv"),
    ("Reference only (not an alarm)", "للمرجعية فقط وليس إنذاراً"),
    ("design solar particle event less than 250 mSv", "عاصفة جسيمات شمسية مرجعية أقل من 250 mSv"),
)


def src_short(spec, lang, limit=70):
    """مصدر الحد مختصراً لرسائل التنبيه في المحادثة (النص الكامل يبقى في بطاقة المؤشر)."""
    text = src(spec, lang)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:(=")
    return cut + "…"


def src(spec, lang):
    """نص مصدر الحد بلغة الواجهة."""
    text = spec["source"]
    if lang == "en":
        return text
    for en, ar in SOURCE_AR:
        text = text.replace(en, ar)
    return text


# ============================================================
# 8ب. اللغتان (عربي / English)
# ============================================================
# القوالب مكتوبة بالعربية. نسخة English تُبنى عند التشغيل باستبدال كل عبارة عربية
# بمقابلها من القاموس أدناه (الأطول أولاً). أي عبارة عربية جديدة في القوالب
# يجب إضافتها هنا. ملاحظة: لا تستخدم علامات اقتباس ولا فواصل عليا داخل الترجمات
# لأنها تظهر داخل نصوص جافاسكربت وسمات HTML.
EN_TEMPLATE = {
    "مراقبة صحة الطاقم": "Crew health monitoring",
    "المجسم التفاعلي": "Body map",
    "الفحص الذاتي": "Self check-in",
    "المخاطر الخمسة": "Five hazards",
    "الطاقم": "Crew",
    "ملخص الطبيب": "Doctor summary",
    "وضع العرض التجريبي:": "Demo mode:",
    "القيم المعروضة محاكاة مشتقة من حدود بيانات ناسا ولا تُحفظ في السجل.": "The values shown are simulated from the NASA-derived limits and are not saved to the history.",
    "إيقاف العرض": "Stop demo",
    "لوحة المراقبة -": "Dashboard -",
    "السجل والتقارير -": "History and Reports -",
    "بيانات ناسا -": "NASA Data -",
    "الإدارة -": "Admin -",
    "تسجيل الدخول -": "Sign in -",
    "لوحة المراقبة": "Dashboard",
    "السجل والتقارير": "History and Reports",
    "بيانات ناسا المفتوحة": "NASA open data",
    "بيانات ناسا": "NASA Data",
    "الإدارة": "Admin",
    "المزيد": "More",
    "سجل التمارين": "Exercise log",
    "تسجيل الخروج": "Sign out",
    "تسجيل الدخول": "Sign in",
    "نظام مراقبة صحة طاقم المحطة الفضائية": "Space station crew health monitoring system",
    "اسم المستخدم": "Username",
    "كلمة المرور": "Password",
    "إنشاء حساب": "Create account",
    "أول حساب يتم إنشاؤه (من الحاسوب نفسه) يصبح مدير النظام.":
        "The first account created (from the computer itself) becomes the system admin.",
    "رمز الدعوة (عند إنشاء حساب فقط)": "Invite code (only when creating an account)",
    "جارٍ التحميل": "Loading",
    "تحديد الحدود من بيانات ناسا": "Set limits from NASA data",
    "العتاد: --": "Hardware: --",
    "العتاد: متصل": "Hardware: connected",
    "العتاد: غير متصل (وضع المحاكاة)": "Hardware: not connected (simulation mode)",
    "جرس الإنذار": "Alarm buzzer",
    ">مطفأ<": ">Off<",
    ">يعمل<": ">On<",
    "المؤشرات الحيوية": "Vital signs",
    "chartTitle\">المؤشر<": "chartTitle\">Metric<",
    ">المساعد<": ">Assistant<",
    "'المساعد'": "'Assistant'",
    "'القائد'": "'Commander'",
    "'النظام'": "'System'",
    "صوت الردود على هذا الجهاز": "Speak replies on this device",
    "اكتب أمراً أو سؤالاً": "Type a command or question",
    "aria-label=\"رسالة\"": "aria-label=\"Message\"",
    ">إرسال<": ">Send<",
    "إملاء صوتي": "Voice dictation",
    "مستقر": "Stable",
    "تحذير": "Warning",
    "خطر": "Danger",
    "الحالة مستقرة": "Status stable",
    "حالة خطر": "Danger status",
    "الحدود المرجعية غير محددة": "Reference limits not set",
    "ما حالة المؤشرات الآن؟": "What is the status of the vitals now?",
    "لماذا الإنذار؟": "Why is the alarm on?",
    "شغل الإنذار": "Turn on the alarm",
    "أوقف الإنذار": "Turn off the alarm",
    "الخطوط المنقطة: حدود التحذير والخطر. المصدر:": "Dashed lines: warning and danger limits. Source:",
    "لا توجد حدود مرجعية لهذا المؤشر": "No reference limits for this metric",
    "لا توجد رسائل بعد. اسأل عن حالة المؤشرات أو تحكم بجرس الإنذار.": "No messages yet. Ask about the vitals or control the alarm buzzer.",
    "تعذر إرسال الرسالة.": "Could not send the message.",
    "الميكروفون ممنوع. اسمح للموقع باستخدامه من إعدادات المتصفح (رمز القفل بجانب العنوان).":
        "The microphone is blocked. Allow this site to use it in the browser settings (lock icon next to the address).",
    "لم يتم التقاط صوت. حاول مرة أخرى.": "No sound was captured. Try again.",
    "لا يوجد ميكروفون متاح في هذا الجهاز.": "No microphone is available on this device.",
    "الإملاء الصوتي يحتاج اتصالاً بالإنترنت.": "Voice dictation needs an internet connection.",
    "لغة الإملاء غير مدعومة في هذا المتصفح.": "The dictation language is not supported in this browser.",
    "تعذر الإملاء الصوتي:": "Voice dictation failed:",
    "المتصفح لا يدعم الإملاء الصوتي. استخدم Chrome أو Edge.": "This browser does not support voice dictation. Use Chrome or Edge.",
    "الإملاء الصوتي يحتاج اتصالاً آمناً. على الحاسوب افتح http://localhost:5000 ومن الجوال افتح رابط https الظاهر في نافذة تشغيل البرنامج.":
        "Voice dictation needs a secure connection. On the computer open http://localhost:5000, and on the phone open the https link shown in the program window.",
    "جارٍ الاستماع": "Listening",
    "تطور المؤشر": "Metric trend",
    "تصدير": "Export",
    "طباعة التقرير": "Print report",
    "التنبيهات": "Alerts",
    "الوقت": "Time",
    "المستوى": "Level",
    "السبب": "Reason",
    "آخر القراءات": "Latest readings",
    "آخر 50 قراءة": "Last 50 readings",
    "بدون حدود": "No limits",
    "الحالة": "Status",
    "لا توجد قراءات بعد. افتح لوحة المراقبة لبدء التسجيل.": "No readings yet. Open the dashboard to start recording.",
    "لا توجد تنبيهات مسجلة.": "No alerts recorded.",
    "الحدود المرجعية المعتمدة": "Approved reference limits",
    "تُستخدم لإعلان التحذير والخطر": "Used to declare warning and danger",
    "تحذير أدنى": "Warning min",
    "تحذير أعلى": "Warning max",
    "خطر أدنى": "Danger min",
    "خطر أعلى": "Danger max",
    "الوحدة (اختياري)": "Unit (optional)",
    "الوحدة": "Unit",
    "المصدر": "Source",
    "قراءة من ناسا": "Read from NASA",
    "غير محدد": "Not set",
    "{{ 'نعم' if s.replay else 'لا' }}": "{{ 'Yes' if s.replay else 'No' }}",
    ">مسح<": ">Clear<",
    "لا توجد حدود بعد، ولن يعلن النظام خطراً حتى تُحدد.": "No limits yet, and the system will not declare danger until they are set.",
    "اطلب من مدير النظام تحديدها.": "Ask the system admin to set them.",
    "استيراد حدود صريحة": "Import explicit limits",
    "إذا كانت بيانات ناسا تتضمن حدوداً جاهزة، ضعها في": "If the NASA data includes ready-made limits, put them in",
    "بالأعمدة": "with the columns",
    "وأسماء المؤشرات المقبولة:": "The accepted metric names are:",
    "اترك الخانة فارغة إن لم يوجد حد في ذلك الاتجاه.": "Leave a cell empty if there is no limit in that direction.",
    "استيراد": "Import",
    "استعراض البيانات": "Browse data",
    "aria-label=\"الملف\"": "aria-label=\"File\"",
    "aria-label=\"العمود\"": "aria-label=\"Column\"",
    "aria-label=\"المؤشر\"": "aria-label=\"Metric\"",
    "صف)": "rows)",
    "اشتقاق الحدود من العمود المحدد": "Derive limits from the selected column",
    "يُحسب الحد من توزيع قيم العمود: مثلاً تحذير عند النسبة المئوية 95 وخطر عند 99 للقيم العالية.":
        "The limit is computed from the distribution of the column values, for example warning at the 95th percentile and danger at the 99th for high values.",
    "اختر النسب بما يناسب طبيعة البيانات، وعاين النتيجة على الرسم قبل الاعتماد.":
        "Choose the percentiles that suit the data, and check the result on the chart before approving.",
    "الاتجاه الخطر": "Risk direction",
    "القيم العالية": "High values",
    "القيم المنخفضة": "Low values",
    "الاتجاهان": "Both directions",
    "نسبة التحذير المئوية": "Warning percentile",
    "نسبة الخطر المئوية": "Danger percentile",
    "استخدام هذا العمود كمصدر لقراءات هذا المؤشر": "Use this column as the source of readings for this metric",
    "معاينة": "Preview",
    "اعتماد الحدود": "Approve limits",
    "لا توجد ملفات بيانات بعد. ضع ملفات": "No data files yet. Put",
    "داخل المجلد": "files inside the folder",
    "ثم حدّث الصفحة،": "then refresh the page,",
    "وستظهر أعمدتها الرقمية مع رسم بياني، ويمكن اشتقاق الحدود منها.": "and their numeric columns will appear with a chart, and limits can be derived from them.",
    "تعذر تنفيذ الطلب.": "The request failed.",
    "مسح الحد المرجعي لهذا المؤشر؟": "Clear the reference limit for this metric?",
    "تم استيراد": "Imported",
    "} مؤشر.": "} metrics.",
    "تحذير: أدنى": "Warning: min",
    "/ أعلى": "/ max",
    "خطر: أدنى": "Danger: min",
    "عدد القراءات:": "Readings:",
    "تم اعتماد الحدود.": "Limits approved.",
    "المستخدمون": "Users",
    "الاسم": "Name",
    "الدور": "Role",
    "تاريخ الإنشاء": "Created",
    "عدد القراءات": "Readings",
    "آخر التنبيهات": "Latest alerts",
    "كل المستخدمين": "All users",
    "المستخدم": "User",
    "المؤشر": "Metric",
    "لا توجد تنبيهات.": "No alerts.",
    "<html lang=\"ar\" dir=\"rtl\">": "<html lang=\"en\" dir=\"ltr\">",
    "IBM+Plex+Sans+Arabic": "IBM+Plex+Sans+Arabic",
}
_EN_PATTERN = re.compile("|".join(re.escape(k) for k in sorted(EN_TEMPLATE, key=len, reverse=True)))
_COMMENT_AR = re.compile(r"/\*[^*]*?[\u0600-\u06FF][^*]*?\*/")


def translate_template(source):
    """يبني نسخة English من قالب عربي."""
    source = _COMMENT_AR.sub("", source)
    return _EN_PATTERN.sub(lambda m: EN_TEMPLATE[m.group(0)], source)


# رسائل بايثون الثابتة (مطابقة كاملة)
PY_EN = {
    "اسم المستخدم يجب أن يكون بين 3 و32 حرفاً.": "Username must be between 3 and 32 characters.",
    "اسم المستخدم يقبل الحروف والأرقام والرموز . _ - @ فقط.":
        "Username accepts letters, digits and the symbols . _ - @ only.",
    "كلمة المرور يجب ألا تقل عن 8 أحرف.": "Password must be at least 8 characters.",
    "محاولات كثيرة فاشلة. حاول بعد بضع دقائق.": "Too many failed attempts. Try again in a few minutes.",
    "أنشئ حساب المدير الأول من الحاسوب نفسه (localhost) وليس من جهاز آخر.":
        "Create the first (admin) account from the computer itself (localhost), not from another device.",
    "رمز الدعوة غير صحيح.": "The invite code is incorrect.",
    "محاولات تسجيل كثيرة من هذا الجهاز. حاول لاحقاً.": "Too many sign-up attempts from this device. Try again later.",
    "تجاوزت الحد المسموح من الرسائل، حاول بعد قليل.": "You have reached the message limit, try again shortly.",
    "لم يصل رد من المساعد (قد يكون حُجب لأسباب الأمان). أعد صياغة السؤال.":
        "No reply came from the assistant (it may have been blocked for safety reasons). Rephrase the question.",
    "اسم المستخدم مستخدم مسبقاً.": "That username is already taken.",
    "اسم المستخدم أو كلمة المرور غير صحيحة.": "Incorrect username or password.",
    "هذا الإجراء للمدير فقط.": "This action is for the admin only.",
    "رمز الحماية غير صالح.": "Invalid security token.",
    "الرسالة فارغة.": "The message is empty.",
    "الرسالة طويلة، الحد الأقصى 500 حرف.": "The message is too long (500 characters max).",
    "رسائل كثيرة بسرعة، انتظر ثانية.": "Too many messages too fast, wait a second.",
    "الملف أو العمود غير موجود.": "File or column not found.",
    "مؤشر غير معروف.": "Unknown metric.",
    "تم تشغيل جرس الإنذار يدوياً.": "The alarm buzzer was turned on manually.",
    "تم إيقاف جرس الإنذار يدوياً.": "The alarm buzzer was turned off manually.",
    "تم تأكيد إنهاء التمرين عبر الزر، وتحسنت كثافة العظام.": "Exercise confirmed via the button, and bone density improved.",
    "مفاتيح المساعد غير مضبوطة. أضف GEMINI_API_KEYS في ملف .env.": "Assistant keys are not set. Add GEMINI_API_KEYS to the .env file.",
    "خدمة Gemini عليها ضغط عالٍ الآن. أعدت المحاولة عدة مرات، أرسل رسالتك بعد دقيقة.":
        "The Gemini service is under heavy load. I retried several times, send your message again in a minute.",
    "تعذر الاتصال بالمساعد حالياً. حاول مرة أخرى بعد قليل.": "Could not reach the assistant right now. Try again shortly.",
}


def _lang():
    try:
        lang = session.get("lang")
    except RuntimeError:  # خارج سياق الطلب
        return "ar"
    return lang if lang in ("ar", "en") else "ar"


def localize_text(text, lang):
    """رسالة مخزنة (نص أو JSON ثنائي اللغة) بلغة المستخدم."""
    text = pick(text, lang)
    if lang == "en" and isinstance(text, str):
        return PY_EN.get(text, text)
    return text


def T(text):
    """يترجم رسالة ثابتة حسب لغة الطلب الحالي."""
    return localize_text(text, _lang())


def err_text(exc):
    return exc.text(_lang()) if isinstance(exc, UserError) else T(str(exc))
