# AstroHab part: 02_vitals_model. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 2. نموذج المؤشرات الحيوية
# ============================================================
# حدود التحذير والخطر لا تُكتب في الكود: تأتي من بيانات ناسا المفتوحة عبر صفحة
# "بيانات ناسا" وتُحفظ في قاعدة البيانات (انظر ReferenceStore في القسم 8).
# هنا فقط وصف المؤشرات: الاسم والوحدة الافتراضية ومجال العرض الافتراضي للرسم.
def bi(ar, en):
    """رسالة ثنائية اللغة (عربي، إنجليزي)."""
    return {"ar": ar, "en": en}


def pack(message):
    """يحول الرسالة الثنائية إلى نص JSON للتخزين في قاعدة البيانات."""
    return json.dumps(message, ensure_ascii=False) if isinstance(message, dict) else message


def pick(message, lang):
    """يختار لغة الرسالة (قاموس أو نص JSON مخزن أو نص عادي)."""
    if isinstance(message, str) and message.startswith('{"ar"'):
        try:
            message = json.loads(message)
        except ValueError:
            return message
    if isinstance(message, dict):
        return message.get(lang) or message.get("ar") or ""
    return message


class UserError(ValueError):
    """خطأ يُعرض للمستخدم بلغتين."""

    def __init__(self, ar, en):
        super().__init__(ar)
        self.ar, self.en = ar, en

    def text(self, lang):
        return self.en if lang == "en" else self.ar


METRIC_INFO = {
    "bpm": {"label": "نبض القلب", "label_en": "Heart rate", "unit": "نبضة/د", "unit_en": "bpm", "scale": [40, 160]},
    "radiation": {"label": "الإشعاع", "label_en": "Radiation", "unit": "mSv", "unit_en": "mSv", "scale": [0, 1]},
    "oxygen": {"label": "الأكسجين", "label_en": "Oxygen", "unit": "%", "unit_en": "%", "scale": [84, 100]},
    "temp": {"label": "حرارة الجسم", "label_en": "Body temperature", "unit": "°C", "unit_en": "°C", "scale": [35.5, 39.5]},
    "stress": {"label": "الإجهاد", "label_en": "Stress", "unit": "/10", "unit_en": "/10", "scale": [0, 10]},
    "bone_health": {"label": "كثافة العظام", "label_en": "Bone density", "unit": "%", "unit_en": "%", "scale": [0, 100]},
}
METRICS = tuple(METRIC_INFO)

# مؤشرات يدخلها رائد الفضاء بنفسه (الفحص الذاتي). حدودها تأتي من نفس جدول الحدود المرجعية:
# تُستورد من data/nasa/limits.csv أو تُشتق من بيانات ناسا.
# "valid" مجال معقول للقيمة المدخلة فقط (لرفض الأخطاء المطبعية)، وليس حداً صحياً.
CHECKIN_INFO = {
    "bp_sys": {"label": "الضغط الانقباضي", "label_en": "Systolic blood pressure", "unit": "mmHg",
               "unit_en": "mmHg", "scale": [70, 200], "valid": [50, 260]},
    "bp_dia": {"label": "الضغط الانبساطي", "label_en": "Diastolic blood pressure", "unit": "mmHg",
               "unit_en": "mmHg", "scale": [40, 130], "valid": [30, 160]},
    "glucose": {"label": "سكر الدم", "label_en": "Blood glucose", "unit": "mg/dL",
                "unit_en": "mg/dL", "scale": [40, 250], "valid": [20, 600]},
    "sleep": {"label": "ساعات النوم", "label_en": "Hours of sleep", "unit": "ساعة",
              "unit_en": "h", "scale": [0, 12], "valid": [0, 24]},
    "mood": {"label": "الحالة المزاجية", "label_en": "Mood", "unit": "/5",
             "unit_en": "/5", "scale": [1, 5], "valid": [1, 5]},
}
CHECKIN_KEYS = tuple(CHECKIN_INFO)
ALL_INFO = {**METRIC_INFO, **CHECKIN_INFO}
# الجرعة التراكمية ليست قراءة حية: تُحسب بجمع قراءات الإشعاع، وحدّها يأتي من limits.csv فقط (المؤشر radiation_total)
DOSE_KEY = "radiation_total"
DOSE_INFO = {DOSE_KEY: {"label": "الجرعة الإشعاعية التراكمية", "label_en": "Cumulative radiation dose",
                        "unit": "mSv", "unit_en": "mSv", "scale": [0, 1]}}
BODY_ORDER = ("bpm", "bp_sys", "bp_dia", "oxygen", "temp", "glucose", "stress",
              "radiation", "bone_health", "sleep", "mood")

# شرح كل مؤشر لرائد الفضاء (لا نفترض أنه يعرف): ما هو، كيف يؤثر الفضاء عليه، ماذا يفعل، ومتى يطلب المساعدة.
# النصوص عامة وتعليمية ولا تحتوي أرقاماً طبية؛ الأرقام تأتي من الحدود المرجعية المعتمدة فقط.
_BP_INFO = {
    "what": bi("ضغط الدم هو قوة دفع الدم على جدران الشرايين: الانقباضي عند انقباض القلب والانبساطي عند ارتخائه.",
               "Blood pressure is the force of blood on artery walls: systolic as the heart contracts, diastolic as it relaxes."),
    "space": bi("انتقال السوائل نحو الرأس وضعف التكيف القلبي الوعائي قد يغيّران الضغط، وقد يظهر دوار عند الوقوف بعد العودة إلى الجاذبية.",
                "Fluid shifts and reduced cardiovascular conditioning can change blood pressure, and dizziness on standing can appear after returning to gravity."),
    "action": bi("قس الضغط جالساً بعد راحة قصيرة وبنفس الوضعية كل مرة، وقلّل الملح، واستمر في التمارين، وسجّل القراءات لتتبع الاتجاه.",
                 "Measure seated after a short rest and in the same position each time, limit salt, keep exercising, and log readings to follow the trend."),
    "escalate": bi("قراءة مرتفعة جداً، أو مصحوبة بصداع شديد أو ألم في الصدر أو اضطراب في الرؤية: تواصل مع طبيب الطيران فوراً.",
                   "A very high reading, or one with severe headache, chest pain or vision changes: contact the flight surgeon at once."),
}
KNOWLEDGE = {
    "bpm": {
        "what": bi("عدد نبضات القلب في الدقيقة، وهو مؤشر سريع على جهد القلب والإجهاد والحالة العامة.",
                   "Heartbeats per minute: a quick sign of how hard the heart is working and of stress and general condition."),
        "space": bi("في الجاذبية الصغرى تنتقل السوائل نحو الرأس ويقل جهد القلب ضد الجاذبية، ومع الوقت قد يضعف التكيف القلبي الوعائي.",
                    "In microgravity fluids shift toward the head and the heart works less against gravity; over time cardiovascular conditioning can decline."),
        "action": bi("قس النبض وأنت مرتاح، واستمر في تمارين التحمل والمقاومة اليومية، واشرب سوائل كافية، وقلّل الكافيين إن كان النبض مرتفعاً.",
                     "Measure at rest, keep up the daily endurance and resistance exercise, drink enough fluids, and cut back on caffeine if your heart rate runs high."),
        "escalate": bi("إن بقي النبض خارج النطاق وأنت مرتاح، أو صاحبه ألم في الصدر أو دوار أو ضيق نفس: أبلغ الطاقم فوراً وتواصل مع طبيب الطيران.",
                       "If your resting heart rate stays out of range, or comes with chest pain, dizziness or shortness of breath: tell the crew immediately and contact the flight surgeon."),
    },
    "bp_sys": _BP_INFO,
    "bp_dia": _BP_INFO,
    "oxygen": {
        "what": bi("نسبة تشبع الدم بالأكسجين، وتدل على كفاية وصول الأكسجين إلى الأنسجة.",
                   "The share of your blood carrying oxygen; it shows whether your tissues are getting enough."),
        "space": bi("هواء المركبة مغلق ويُدار صناعياً: ارتفاع ثاني أكسيد الكربون أو ضعف التهوية قد يخفض الأكسجين ويسبب صداعاً ونعاساً.",
                    "Cabin air is closed and managed artificially: high carbon dioxide or poor ventilation can lower oxygen and cause headache and drowsiness."),
        "action": bi("تأكد من تدفق الهواء حولك، وتجنب الجهد الزائد، وراجع قراءات جو المقصورة، وأعد القياس بعد الراحة.",
                     "Check the air flow around you, avoid overexertion, review the cabin atmosphere readings and measure again after resting."),
        "escalate": bi("انخفاض مستمر، أو صداع ودوار وضيق نفس: أبلغ الطاقم فوراً واتبع إجراءات جو المقصورة وتواصل مع الأرض.",
                       "A lasting low reading, or headache, dizziness and breathlessness: tell the crew immediately, follow the cabin atmosphere procedures and contact Earth."),
    },
    "temp": {
        "what": bi("حرارة الجسم الأساسية. ارتفاعها أو انخفاضها قد يدل على عدوى أو إجهاد حراري أو خلل في التنظيم الحراري.",
                   "Core body temperature. A rise or fall can point to infection, heat stress or poor temperature regulation."),
        "space": bi("في الجاذبية الصغرى يتغير تبديد الحرارة (لا حمل حراري طبيعي للهواء)، والمجهود البدني والمقصورة الدافئة قد يرفعان حرارة الجسم.",
                    "In microgravity heat is shed differently (no natural air convection), and exercise or a warm cabin can raise body temperature."),
        "action": bi("قس بعد الراحة وليس بعد التمرين مباشرة، واضبط حرارة المقصورة والملابس، واشرب سوائل.",
                     "Measure after resting rather than right after exercise, adjust cabin temperature and clothing, and drink fluids."),
        "escalate": bi("حمى مستمرة أو قشعريرة أو ضعف شديد: أبلغ الطاقم وتواصل مع طبيب الطيران، فالعدوى في بيئة مغلقة قد تنتشر.",
                       "A lasting fever, chills or severe weakness: tell the crew and contact the flight surgeon; infections can spread in a closed environment."),
    },
    "glucose": {
        "what": bi("مستوى السكر في الدم، وهو مصدر الطاقة الرئيسي للجسم والدماغ.",
                   "Blood sugar level: the main fuel for the body and brain."),
        "space": bi("تشير دراسات إلى تغيرات في استقلاب السكر أثناء الرحلات الفضائية (مثل حساسية الإنسولين)، وقد تتغير التغذية والنشاط أيضاً.",
                    "Studies report changes in glucose metabolism during spaceflight (for example in insulin sensitivity), and diet and activity may also change."),
        "action": bi("قس صائماً إن أمكن وسجّل وقت آخر وجبة، والتزم بوجبات متوازنة ونشاط يومي.",
                     "Measure fasting if you can and note the time of your last meal; keep to balanced meals and daily activity."),
        "escalate": bi("انخفاض شديد مع رجفة أو تعرق أو تشوش، أو ارتفاع متكرر: أبلغ الطاقم وتواصل مع طبيب الطيران. وعند الانخفاض تناول مصدراً سريعاً للسكر إن توفر.",
                       "A severe low with shaking, sweating or confusion, or repeated high readings: tell the crew and contact the flight surgeon. For a low reading, take a quick source of sugar if available."),
    },
    "stress": {
        "what": bi("درجة من 0 إلى 10 يقدّرها النظام من النبض والإشعاع والأكسجين. هي تقدير وليست قياساً سريرياً.",
                   "A score from 0 to 10 that the system estimates from heart rate, radiation and oxygen. It is an estimate, not a clinical measurement."),
        "space": bi("العزلة وضيق المكان والبعد عن الأرض والعمل المكثف ترفع الإجهاد النفسي في المهمات الطويلة.",
                    "Isolation, tight quarters, distance from Earth and heavy workloads raise psychological stress on long missions."),
        "action": bi("خذ فترات راحة منتظمة، وتنفس ببطء، ومارس نشاطاً تحبه، وتحدث مع زملائك أو عائلتك عبر وسائل الاتصال المتاحة.",
                     "Take regular breaks, breathe slowly, do an activity you enjoy, and talk with crewmates or family through the links available."),
        "escalate": bi("إجهاد مرتفع يستمر أياماً أو يؤثر على النوم والعمل: أبلغ الطاقم واطلب جلسة دعم نفسي مع الأرض.",
                       "High stress lasting days, or affecting sleep and work: tell the crew and ask for a behavioral-health support session with the ground."),
    },
    "radiation": {
        "what": bi("الجرعة الإشعاعية التي يتعرض لها الجسم. الإشعاع الفضائي أعلى من إشعاع الأرض لأن الغلاف الجوي، وخارج المدار الأرضي المنخفض المجال المغناطيسي أيضاً، لا يحميانك.",
                   "The radiation dose absorbed by the body. Space radiation is higher than on Earth because the atmosphere, and beyond low Earth orbit Earth's magnetic field too, no longer shield you."),
        "space": bi("الأشعة الكونية والعواصف الشمسية ترفع على المدى البعيد مخاطر السرطان وتضر بالجهاز العصبي والقلب.",
                    "Cosmic rays and solar storms raise long-term risks of cancer and of damage to the nervous and cardiovascular systems."),
        "action": bi("تابع تنبيهات الطقس الفضائي، واقضِ وقتاً أطول في المنطقة الأكثر تدريعاً عند التحذير، وسجّل قراءات المقياس الشخصي.",
                     "Follow space-weather alerts, spend more time in the best-shielded area when warned, and log your personal dosimeter readings."),
        "escalate": bi("ارتفاع مفاجئ أو تحذير من عاصفة شمسية: انتقل فوراً إلى الملجأ الأكثر تدريعاً وأبلغ الطاقم والأرض.",
                       "A sudden rise or a solar-storm warning: move at once to the best-shielded shelter and tell the crew and the ground."),
    },
    "bone_health": {
        "what": bi("كثافة العظام، وتدل على قوة العظام ومقاومتها للكسر.",
                   "Bone density: it shows how strong your bones are and how well they resist fractures."),
        "space": bi("العظام الحاملة للوزن (الورك والعمود الفقري) تفقد من كثافتها في الجاذبية الصغرى لأنها لا تتحمل وزن الجسم.",
                    "Weight-bearing bones (hip and spine) lose density in microgravity because they no longer carry body weight."),
        "action": bi("مارس تمارين المقاومة يومياً (واضغط زر التمرين لتسجيلها)، والتزم بالكالسيوم وفيتامين د في خطة التغذية.",
                     "Do resistance exercise daily (and press the exercise button to log it), and keep to the calcium and vitamin D in your nutrition plan."),
        "escalate": bi("هبوط مستمر رغم التمارين، أو ألم عظمي غير معتاد: أبلغ طبيب الطيران لمراجعة الخطة.",
                       "A steady drop despite exercise, or unusual bone pain: tell the flight surgeon so the plan can be reviewed."),
    },
    "sleep": {
        "what": bi("عدد ساعات نومك في الليلة الماضية. النوم يرمم الجسم ويثبّت الذاكرة والمزاج.",
                   "Hours you slept last night. Sleep restores the body and supports memory and mood."),
        "space": bi("الإضاءة غير المعتادة وتعاقب الشروق والغروب السريع والضجيج وجداول العمل تخلّ بالساعة البيولوجية، فيقصر النوم غالباً.",
                    "Unusual lighting, rapid sunrises and sunsets, noise and work schedules disturb the body clock, so sleep is often shorter."),
        "action": bi("التزم بموعد نوم ثابت، وخفّض الإضاءة قبل النوم، وقلّل الشاشات والكافيين، واجعل مكان نومك هادئاً ومظلماً.",
                     "Keep a fixed bedtime, dim the lights before sleep, limit screens and caffeine, and keep your sleep area quiet and dark."),
        "escalate": bi("قلة نوم لعدة ليالٍ، أو نعاس أثناء مهام حرجة: أبلغ الطاقم واطلب من الأرض مراجعة جدولك.",
                       "Several short nights, or drowsiness during critical tasks: tell the crew and ask the ground to review your schedule."),
    },
    "mood": {
        "what": bi("تقييمك الذاتي لمزاجك من 1 (منخفض جداً) إلى 5 (جيد جداً). مقياس بسيط من تعريف التطبيق وليس تشخيصاً.",
                   "Your self-rating of mood from 1 (very low) to 5 (very good). A simple scale defined by this app, not a diagnosis."),
        "space": bi("العزلة والانغلاق والبعد عن الأرض قد تؤثر على المزاج والدافعية والعلاقات داخل الطاقم.",
                    "Isolation, confinement and distance from Earth can affect mood, motivation and relationships within the crew."),
        "action": bi("حافظ على روتين ثابت، وتواصل مع الأهل والأصدقاء، وشارك زملاءك في أنشطة جماعية، وخصص وقتاً لهواية.",
                     "Keep a steady routine, stay in touch with family and friends, share group activities with crewmates and make time for a hobby."),
        "escalate": bi("مزاج منخفض يستمر أياماً، أو أفكار مقلقة: تحدث مع زميل موثوق واطلب جلسة دعم نفسي خاصة مع الأرض، ولا تنتظر.",
                       "Low mood that lasts for days, or worrying thoughts: talk to a trusted crewmate and ask for a private behavioral-health session with the ground, and don't wait."),
    },
}

# أجزاء الجسم القابلة للنقر في المجسم، والمؤشرات التي تغذيها
BODY_REGIONS = [
    {"id": "head", "metrics": ["mood", "sleep", "stress"],
     "name": bi("الرأس والدماغ", "Head and brain"),
     "function": bi("الدماغ يتحكم في النوم والمزاج والانتباه واتخاذ القرار، وهو حساس للعزلة وقلة النوم.",
                    "The brain controls sleep, mood, attention and decision-making, and is sensitive to isolation and lack of sleep.")},
    {"id": "lungs", "metrics": ["oxygen"],
     "name": bi("الرئتان", "Lungs"),
     "function": bi("تُدخلان الأكسجين إلى الدم وتخرجان ثاني أكسيد الكربون، وتعتمدان على جودة هواء المقصورة.",
                    "They bring oxygen into the blood and remove carbon dioxide, and depend on the quality of the cabin air.")},
    {"id": "heart", "metrics": ["bpm", "bp_sys", "bp_dia"],
     "name": bi("القلب والدورة الدموية", "Heart and circulation"),
     "function": bi("يضخ الدم إلى كل الجسم. الجاذبية الصغرى تغيّر توزيع السوائل وتخفف عمل القلب فيضعف تدريجياً دون تمرين.",
                    "It pumps blood to the whole body. Microgravity shifts fluids and lightens the heart's work, so it can weaken without exercise.")},
    {"id": "abdomen", "metrics": ["glucose"],
     "name": bi("البطن والاستقلاب", "Abdomen and metabolism"),
     "function": bi("البنكرياس والكبد ينظمان سكر الدم وطاقة الجسم، ويتأثران بالغذاء والنشاط.",
                    "The pancreas and liver regulate blood sugar and energy, and are affected by food and activity.")},
    {"id": "bones", "metrics": ["bone_health"],
     "name": bi("العظام", "Bones"),
     "function": bi("تحمل الجسم وتخزن الكالسيوم. تتجدد بالضغط والحركة، لذلك تضعف في غياب الجاذبية دون تمارين مقاومة.",
                    "They support the body and store calcium. They renew under load and movement, so they weaken without gravity unless you do resistance exercise.")},
    {"id": "body", "metrics": ["temp", "radiation"],
     "name": bi("الجسم كله", "Whole body"),
     "function": bi("حرارة الجسم وتعرضه للإشعاع يخصان كل الأنسجة، من الجلد إلى نخاع العظم.",
                    "Body temperature and radiation exposure concern every tissue, from the skin to the bone marrow.")},
]

# المخاطر الخمسة التي حددها برنامج أبحاث الإنسان في ناسا، وربطها بالأجزاء والمؤشرات
BODY_HAZARDS = [
    {"id": "radiation", "regions": ["body", "head", "heart"], "metrics": ["radiation"],
     "name": bi("الإشعاع الفضائي", "Space radiation"),
     "text": bi("جسيمات عالية الطاقة تخترق المركبة وتزيد مخاطر السرطان وتضر بالأعصاب والقلب.",
                "High-energy particles pass through the spacecraft and raise cancer risk and harm the nerves and the heart.")},
    {"id": "isolation", "regions": ["head"], "metrics": ["mood", "stress", "sleep"],
     "name": bi("العزلة والانغلاق", "Isolation and confinement"),
     "text": bi("قلة التواصل الاجتماعي وضيق المساحة تؤثر على المزاج والنوم والأداء.",
                "Limited social contact and small spaces affect mood, sleep and performance.")},
    {"id": "distance", "regions": [], "metrics": [],
     "name": bi("البعد عن الأرض", "Distance from Earth"),
     "text": bi("تأخر الاتصال وصعوبة الإخلاء الطبي، لذلك تعتمد أولاً على القياس الذاتي وإجراءات الطاقم، ولهذا تعمل الأداة بأقل اعتماد على الإنترنت.",
                "Communication is delayed and medical evacuation is hard, so you rely first on self-assessment and crew procedures, which is why this tool needs as little internet as possible.")},
    {"id": "gravity", "regions": ["bones", "heart"], "metrics": ["bone_health", "bpm", "bp_sys", "bp_dia"],
     "name": bi("مجالات الجاذبية", "Gravity fields"),
     "text": bi("الجاذبية الصغرى تغيّر توزيع السوائل وتضعف العظام والعضلات والقلب.",
                "Microgravity shifts fluids and weakens bones, muscles and the heart.")},
    {"id": "closed", "regions": ["lungs", "body", "head"], "metrics": ["oxygen", "temp"],
     "name": bi("البيئة المغلقة القاسية", "Hostile closed environment"),
     "text": bi("الهواء والحرارة والضجيج تُدار صناعياً، وانتشار العدوى في مكان مغلق أسهل.",
                "Air, temperature and noise are managed artificially, and infections spread more easily in an enclosed space.")},
]

# NASA Human Research Program pages (read 2026-11-13). The titles are NASA's; sources in RESOURCES.md.
_NASA = "https://www.nasa.gov/"
NASA_HAZARD_URL = {
    "radiation": _NASA + "hrp/hazard-space-radiation/", "isolation": _NASA + "hrp/hazard-isolation-and-confinement/",
    "distance": _NASA + "hrp/hazard-distance-from-earth/", "gravity": _NASA + "hrp/hazard-gravity-fields/",
    "closed": _NASA + "hrp/hazard-hostile-closed-environments/",
}
# the only numbers that page gives for the hazards (no medical limits)
HAZARD_FACTS = {
    "distance": bi("المريخ يبعد في المتوسط نحو 140 مليون ميل عن الأرض. الرحلة إلى القمر تستغرق نحو ثلاثة أيام، ومهمة المريخ نحو ثلاث سنوات.",
                   "Mars is, on average, about 140 million miles from Earth. A lunar trip takes about three days and a Mars mission would last roughly three years."),
    "gravity": bi("على المريخ يعيش الرواد في ثلاثة أثمان جاذبية الأرض لمدة تصل إلى سنتين.",
                  "On Mars, astronauts would live in three-eighths of Earth's gravity for up to two years."),
}
RISK_GROUPS = [
    ("physiology", bi("فسيولوجيا الإنسان (11)", "Human physiology (11)")),
    ("behavioral", bi("الأداء السلوكي والعوامل البشرية (5)", "Behavioral performance and human factors (5)")),
    ("radiation", bi("الإشعاع الفضائي (1)", "Space radiation (1)")),
]
NASA_RISKS = [  # (key, group, NASA title, page)
    ("immune", "physiology", "Risk of Altered Immune System Responses", "risk-of-altered-immune-system-responses"),
    ("sensorimotor", "physiology", "Risk of Altered Sensorimotor and Vestibular Function", "risk-of-altered-sensorimotor-and-vestibular-function"),
    ("cardiovascular", "physiology", "Risk of Cardiovascular Adaptations", "risk-of-cardiovascular-adaptations"),
    ("decompression", "physiology", "Risk of Decompression Sickness", "risk-of-decompression-sickness"),
    ("microbiome", "physiology", "Risk of Host-Microorganism Interactions", "risk-of-host-microorganism-interactions"),
    ("hypoxia", "physiology", "Risk of Hypoxia", "risk-of-hypoxia"),
    ("nutrition", "physiology", "Risk of Inadequate Food and Nutrition", "risk-of-inadequate-food-and-nutrition"),
    ("eva", "physiology", "Risk of Injury and Compromised Performance from Spacewalks", "risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva"),
    ("fitness", "physiology", "Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness", "risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness"),
    ("sans", "physiology", "Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)", "risk-of-spaceflight-associated-neuro-ocular-syndrome-sans"),
    ("bone", "physiology", "Risk of Spaceflight-Induced Bone Changes", "risk-of-spaceflight-induced-bone-changes"),
    ("behavioral", "behavioral", "Risk of Behavioral Changes and Psychiatric Disorders", "risk-of-behavioral-conditions-and-psychiatric-disorders"),
    ("teamwork", "behavioral", "Risk of Inadequate Teamwork", "risk-of-inadequate-teamwork"),
    ("sleep", "behavioral", "Risk of Inadequate Sleep and Irregular Schedules", "risk-from-inadequate-sleep-and-irregular-schedules"),
    ("sysops", "behavioral", "Risk of Inadequate Systems Operations Support", "risk-of-inadequate-systems-operations-support"),
    ("dynamic", "behavioral", "Risk of Injury from Dynamic Loads", "risk-of-injury-from-dynamic-loads"),
    ("radiation_cancer", "radiation", "Risk of Radiation-Induced Cancers", "risk-of-radiation-induced-cancers"),
]
NASA_RISK = {k: {"key": k, "group": g, "name": n, "url": f"{_NASA}reference/{slug}/"} for k, g, n, slug in NASA_RISKS}
# Which NASA risk each AstroHab metric relates to. This pairing is the project's own (NASA's pages do not state it);
# glucose and body temperature have no matching NASA risk title, so they have none.
METRIC_RISK = {"bpm": "cardiovascular", "bp_sys": "cardiovascular", "bp_dia": "cardiovascular", "bone_health": "bone",
               "sleep": "sleep", "mood": "behavioral", "stress": "behavioral", "radiation": "radiation_cancer",
               "oxygen": "hypoxia"}


def risk_of_key(key):
    r = NASA_RISK[key]
    return {"name": r["name"], "url": r["url"]}


def risk_of(metric):
    r = NASA_RISK.get(METRIC_RISK.get(metric))
    return {"name": r["name"], "url": r["url"]} if r else None


# تفاصيل صفحة المخاطر الخمسة: نصوص تعليمية عامة بلا أرقام طبية. الأرقام والحدود تأتي من بيانات ناسا فقط.
HAZARD_DETAILS = {
    "radiation": {
        "effects": bi("خارج الحماية المغناطيسية للأرض تتعرض لجسيمات عالية الطاقة من الشمس والفضاء العميق. التعرض الطويل يرفع خطر السرطان، وقد يؤثر على الجهاز العصبي والقلب. العواصف الشمسية ترفع الجرعة فجأة.",
                      "Outside Earth's magnetic protection you are exposed to high-energy particles from the Sun and deep space. Long exposure raises cancer risk and may affect the nervous system and the heart. Solar storms raise the dose suddenly."),
        "prevent": bi("اتبع تعليمات مركز التحكم عند التنبيه من عاصفة شمسية واذهب إلى المنطقة الأفضل حماية في المحطة. سجّل قراءة جهاز قياس الجرعة بانتظام، والتزم بحدود التعرض التي يحددها أطباء الطيران.",
                      "Follow mission control when a solar storm is announced and move to the best shielded area of the station. Log your dosimeter reading regularly and keep to the exposure limits your flight surgeons set."),
        "escalate": bi("عند ارتفاع إنذار الإشعاع، أو ظهور غثيان أو قيء أو إرهاق شديد بعد تعرض معروف: أبلغ الطاقم وتواصل مع أطباء الطيران فوراً.",
                       "When a radiation alarm rises, or you get nausea, vomiting or severe fatigue after a known exposure: tell the crew and contact the flight surgeons at once."),
    },
    "isolation": {
        "effects": bi("قلة التواصل الاجتماعي وضيق المكان وتكرار الروتين تؤثر على المزاج والنوم والتركيز، وقد تزيد التوتر والخلافات داخل الطاقم.",
                      "Limited social contact, small spaces and repetitive routine affect mood, sleep and concentration, and can raise tension and conflict inside the crew."),
        "prevent": bi("حافظ على موعد نوم ثابت وروتين يومي، واحجز وقتاً للتواصل مع الأهل والأصدقاء، ومارس هواية، وتحدث مع زملائك بصراحة، وسجّل مزاجك يومياً في الفحص الذاتي لتلاحظ الاتجاه.",
                      "Keep a fixed sleep time and a daily routine, schedule contact with family and friends, keep a hobby, talk openly with your crewmates and log your mood daily in the check-in so you can see the trend."),
        "escalate": bi("إن استمر انخفاض المزاج أو فقدان الاهتمام أو الأرق أياماً، أو شعرت باليأس أو بأنك غير آمن: أبلغ زميلاً وطبيب الطيران فوراً.",
                       "If low mood, loss of interest or insomnia lasts for days, or you feel hopeless or unsafe: tell a crewmate and the flight surgeon right away."),
    },
    "distance": {
        "effects": bi("الاتصال بالأرض يتأخر، ولا يمكن الإخلاء الطبي السريع. لذلك يجب أن تعتمد أولاً على القياس الذاتي والإجراءات المتفق عليها مسبقاً، وأن تتخذ قرارات مبكرة بدل الانتظار.",
                      "Contact with Earth is delayed and quick medical evacuation is not possible. You rely first on self-assessment and procedures agreed in advance, and you decide early instead of waiting."),
        "prevent": bi("سجّل قياساتك بانتظام، واعرف الإجراءات وموقع المعدات الطبية، واتفق مع أطباء الطيران قبل الرحلة على قواعد القرار. تعمل لوحة المراقبة والفحص الذاتي والمجسم بدون إنترنت، أما مساعد Gemini فيحتاج اتصالاً.",
                      "Log your readings regularly, know the procedures and where the medical equipment is, and agree decision rules with your flight surgeons before the mission. The dashboard, the check-in and the body map work without internet; the Gemini assistant needs a connection."),
        "escalate": bi("أرسل تقريراً مكتوباً واضحاً مبكراً: ماذا حدث، ومتى، وما قياساتك. استخدم صفحة ملخص الطبيب لتجهيزه.",
                       "Send a clear written report early: what happened, when, and your readings. Use the doctor summary page to prepare it."),
    },
    "gravity": {
        "effects": bi("في الجاذبية الصغرى تنتقل السوائل نحو الرأس، وتضعف العظام والعضلات، ويقل جهد القلب، وقد تتغير الرؤية. وعند العودة إلى الجاذبية قد يظهر دوار وضعف في التوازن.",
                      "In microgravity fluids shift toward the head, bones and muscles weaken, the heart works less and vision can change. Back in gravity you may feel dizzy and unsteady."),
        "prevent": bi("التزم بتمارين المقاومة والتحمل اليومية المقررة لك، وبالتغذية وشرب السوائل حسب توجيهات أطباء الطيران، وراقب النبض وضغط الدم وكثافة العظام.",
                      "Keep to your scheduled daily resistance and endurance exercise, follow your flight surgeons' nutrition and fluid guidance, and watch your heart rate, blood pressure and bone density."),
        "escalate": bi("تغير في الرؤية، صداع شديد، ألم في الصدر، أو دوار عند الوقوف: أبلغ الطاقم وتواصل مع أطباء الطيران.",
                       "Changes in vision, severe headache, chest pain, or dizziness on standing: tell the crew and contact the flight surgeons."),
    },
    "closed": {
        "effects": bi("الهواء والحرارة والضجيج تُدار صناعياً: تراكم ثاني أكسيد الكربون أو ضعف التهوية يسبب صداعاً ونعاساً، والضجيج يعطل النوم، والعدوى تنتشر أسهل في مكان مغلق.",
                      "Air, temperature and noise are managed artificially: carbon dioxide build-up or poor ventilation causes headache and drowsiness, noise disturbs sleep, and infections spread more easily in an enclosed space."),
        "prevent": bi("نظّف الأسطح ونظّف يديك، وتأكد من تدفق الهواء حول مكان نومك وعملك، وأبلغ عن أي رائحة غريبة، واستخدم حماية السمع قرب المعدات العالية الصوت.",
                      "Clean surfaces and your hands, make sure air flows around where you sleep and work, report any strange smell, and use hearing protection near loud equipment."),
        "escalate": bi("صداع مستمر أو ضيق نفس أو حمى، أو دخان أو رائحة غريبة أو إنذار جو المقصورة: اتبع إجراءات الطوارئ وأبلغ الطاقم والأرض.",
                       "Lasting headache, breathlessness or fever, or smoke, a strange smell or a cabin atmosphere alarm: follow the emergency procedures and tell the crew and Earth."),
    },
}

# توصية التصعيد: ثلاثة مستويات (عناية ذاتية، إبلاغ الطاقم، تواصل مع الأرض)
ESCALATION = {
    0: bi("كل المؤشرات التي لها حدود ضمن النطاق الآمن. واصل روتينك اليومي وقياساتك.",
          "Every metric that has limits is within the safe range. Keep up your daily routine and measurements."),
    1: bi("هناك مؤشر يحتاج انتباهاً: أعد القياس بعد قليل من الراحة، وأبلغ زميلاً في الطاقم، وسجّل ملاحظاتك.",
          "A metric needs attention: measure again after a short rest, tell a crewmate, and note what you observe."),
    2: bi("تواصل مع أطباء الطيران على الأرض الآن، واتبع إجراءات الطوارئ في المحطة، وأبلغ الطاقم.",
          "Contact the flight surgeons on Earth now, follow the station emergency procedures, and tell the crew."),
}
DEFAULTS = {"bpm": 72.0, "temp": 36.6, "stress": 2.0,
            "radiation": 0.15, "oxygen": 98.5, "bone_health": 100.0}  # العظام: 100 = قيمة ما قبل المهمة (حد ناسا نسبي)
UNSET_REASON = bi("لم تُحدد الحدود المرجعية بعد، لذلك لا يعلن النظام خطراً. "
                  "حدّدها من بيانات ناسا في صفحة بيانات ناسا.",
                  "Reference limits are not set yet, so the system does not declare danger. "
                  "Set them from NASA data on the NASA Data page.")
NORMAL_REASON = bi("جميع المؤشرات ذات الحدود المرجعية ضمن النطاق الآمن.",
                   "All metrics that have reference limits are within the safe range.")
BONE_DECAY_PER_TICK = 0.01  # فقدان بطيء لكثافة العظام في الجاذبية الصغرى


def _clamp(value, low, high):
    return max(low, min(high, value))


def evaluate_detail(data, limits=None):
    """يقارن القراءات بالحدود المرجعية المأخوذة من بيانات ناسا.

    يرجع (المستوى، السبب، المؤشر المتسبب). المستوى: normal أو warning أو danger، أو unconfigured
    إذا لم يُحدد أي حد بعد (فلا يعلن النظام خطراً من تلقاء نفسه).
    """
    limits = limits if limits is not None else reference.current
    if not any(spec["configured"] for spec in limits.values()):
        return "unconfigured", UNSET_REASON, None
    for severity in ("danger", "warning"):
        for key in METRICS:
            spec = limits[key]
            low, high = spec[severity]
            value = data[key]
            if high is not None and value > high:
                direction, bound = "ارتفاع", high
            elif low is not None and value < low:
                direction, bound = "انخفاض", low
            else:
                continue
            critical = severity == "danger"
            qualifier = "حرج " if critical else ""
            ar = (f"{direction} {qualifier}في {spec['label']}: {value} {spec['unit']} "
                  f"(الحد {bound}، المصدر: {src_short(spec, 'ar')}).")
            en_dir = "high" if direction == "ارتفاع" else "low"
            en_head = f"Critical {en_dir}" if critical else en_dir.capitalize()
            en = (f"{en_head} {spec['label_en'].lower()}: {value} {spec['unit_en']} "
                  f"(limit {bound}, source: {src_short(spec, 'en')}).")
            return severity, bi(ar, en), key
    return "normal", NORMAL_REASON, None


def evaluate(data, limits=None):
    """نفس evaluate_detail لكن يرجع (المستوى، السبب) فقط."""
    level, reason, _ = evaluate_detail(data, limits)
    return level, reason


def simulate_step(data, replay=None, index=0):
    """خطوة محاكاة واحدة.

    المؤشرات التي لها مصدر إعادة تشغيل من بيانات ناسا (replay) تأخذ قيمتها من
    العمود المرجعي بالترتيب، وبقية المؤشرات تُحاكى عشوائياً حول قيم طبيعية.
    """
    replay = replay or {}
    for key, values in replay.items():
        data[key] = round(values[index % len(values)], 4)

    if "bpm" not in replay:
        bpm = data["bpm"] + (72 - data["bpm"]) * 0.05 + random.uniform(-5, 6)
        if random.random() < 0.02:
            bpm += 30
        data["bpm"] = round(_clamp(bpm, 45.0, 150.0), 1)

    if "temp" not in replay:
        temp = data["temp"] + (36.7 - data["temp"]) * 0.05 + random.uniform(-0.1, 0.1)
        data["temp"] = round(_clamp(temp, 36.0, 39.0), 2)

    if "oxygen" not in replay:
        oxygen = data["oxygen"] + (98 - data["oxygen"]) * 0.1 + random.uniform(-1.0, 0.5)
        if random.random() < 0.02:
            oxygen -= 6
        data["oxygen"] = round(_clamp(oxygen, 85.0, 100.0), 1)

    if "radiation" not in replay:
        if random.random() < 0.06:  # ارتفاع مفاجئ في الإشعاع
            data["radiation"] = round(random.uniform(0.55, 0.95), 2)
        elif data["radiation"] > 0.4:  # بعد الارتفاع المفاجئ يعود تدريجياً وليس بقفزة واحدة
            data["radiation"] = round(0.2 + (data["radiation"] - 0.2) * 0.6, 2)
        else:
            radiation = data["radiation"] + random.uniform(-0.02, 0.02)
            data["radiation"] = round(_clamp(radiation, 0.1, 0.4), 2)

    if "stress" not in replay:
        stress = (data["bpm"] - 65) / 8
        if data["radiation"] > 0.5:
            stress += 2
        if data["oxygen"] < 94:
            stress += 1.5
        data["stress"] = round(_clamp(stress, 0, 10), 1)

    if "bone_health" not in replay:
        data["bone_health"] = round(_clamp(data["bone_health"] - BONE_DECAY_PER_TICK, 0, 100), 2)
