# AstroHab part: 01_settings. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 1. الإعدادات
# ============================================================
BASE_DIR = Path(__file__).resolve().parent


ENV_FILE_USED = None


def _parse_env_value(raw):
    """قيمة سطر في .env: تدعم علامات الاقتباس وتتجاهل تعليق نهاية السطر ( # ...)."""
    raw = raw.strip()
    if raw[:1] in ('"', "'"):
        end = raw.find(raw[0], 1)
        if end != -1:
            return raw[1:end]
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip().strip('"').strip("'")


def _load_env_file():
    """يقرأ ملف .env (إن وُجد) دون استبدال متغيرات البيئة الموجودة.

    يقبل أيضاً .env.txt لأن ويندوز يضيف .txt أحياناً عند الحفظ من المفكرة.
    """
    global ENV_FILE_USED
    for name in (".env", ".env.txt", "env", "env.txt", "config.env"):
        env_file = BASE_DIR / name
        if env_file.exists():
            break
    else:
        return
    ENV_FILE_USED = env_file
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), _parse_env_value(value)
        # متغير البيئة الحقيقي له الأولوية على الملف؛ والقيمة الفارغة في البيئة لا تمنع القراءة من الملف
        if value and not os.environ.get(key, "").strip():
            os.environ[key] = value


def _flag(name, default):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


_load_env_file()


class Config:
    API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()  # اختياري
    GEMINI_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "15000"))  # بعدها ينتقل للمساعد المحلي
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    HTTPS_ENABLED = _flag("HTTPS_ENABLED", True)   # منفذ HTTPS إضافي لتشغيل الميكروفون من الجوال
    HTTPS_PORT = int(os.getenv("HTTPS_PORT", "5443"))

    SERIAL_ENABLED = _flag("SERIAL_ENABLED", True)
    SERIAL_PORT = os.getenv("SERIAL_PORT", "COM7")
    BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))
    VOICE_ENABLED = _flag("VOICE_ENABLED", True)
    # النطق من مكبر الحاسوب للأحداث التلقائية (تنبيه خطر، رد المساعد على الزر). الافتراضي مغلق: تظهر في المحادثة بلا نطق.
    # ردود المساعد على سؤال المستخدم تُنطق دائماً في المتصفح الذي سأل فقط (الجوال أو الحاسوب)، ولا تخرج من مكبر الحاسوب.
    SPEAK_AUTO = _flag("SPEAK_AUTO", False)

    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "astrohab.db"))
    NASA_DIR = BASE_DIR / "data" / "nasa"

    TICK_SECONDS = 2               # فترة تحديث القراءات
    SIM_DAYS_PER_TICK = 1.0        # محاكاة: كل تحديث = يوم محاكى، وبه تتراكم الجرعة (قراءة الإشعاع تُعدّ mSv في اليوم)
    STORM_TICKS = 30               # مدة عاصفة شمسية محاكاة بالتحديثات
    HISTORY_EVERY_TICKS = 5        # حفظ قراءة في السجل كل 10 ثوان
    SESSION_IDLE_SECONDS = 600     # إيقاف محاكاة المستخدم الخامل
    CALM_TICKS_TO_SILENCE = 3      # قراءات طبيعية متتالية قبل إطفاء الإنذار تلقائياً
    MANUAL_OVERRIDE_SECONDS = 30   # مدة احترام الأمر اليدوي قبل عودة التحكم التلقائي
    BUZZER_HEARTBEAT_SECONDS = 1.0 # إعادة إرسال حالة الجرس للأردوينو (نبضة حياة)

    # حماية الحسابات والمساعد
    REGISTRATION_CODE = os.getenv("REGISTRATION_CODE", "").strip()  # اختياري: رمز دعوة للحسابات بعد المدير
    ALLOW_REMOTE_FIRST_ADMIN = _flag("ALLOW_REMOTE_FIRST_ADMIN", False)
    MIN_PASSWORD = 8
    LOGIN_MAX_FAILS = 5            # محاولات فاشلة لكل (جهاز، اسم مستخدم) قبل القفل المؤقت
    LOGIN_MAX_FAILS_PER_IP = 20    # محاولات فاشلة لكل جهاز مهما كان الاسم
    LOGIN_LOCK_SECONDS = 300
    REGISTER_PER_HOUR = 10         # محاولات إنشاء حساب لكل جهاز في الساعة
    CHAT_PER_10MIN = 30            # رسائل المساعد لكل مستخدم كل 10 دقائق (حماية حصة Gemini)
    MANUAL_DUE_HOURS = 24          # بعدها يُذكَّر المستخدم بتسجيل القياسات اليدوية
    DEMO_PHASE_TICKS = 4           # مدة كل مرحلة في العرض التجريبي (4 دورات = 8 ثوان)
    TREND_MIN_READINGS = 3         # أقل عدد قراءات متتالية بنفس الاتجاه لإعلان اتجاه
    EARLY_HORIZON_READINGS = 3     # التنبيه المبكر: يصل الحد خلال هذا العدد من القراءات القادمة بنفس الوتيرة
    EXERCISE_DETAILS_HOURS = 12    # بعد ضغطة الزر تبقى الجلسة تنتظر الدقائق والنوع هذه المدة ثم تُترك بلا تفاصيل
    EXERCISE_ACTIVE_SECONDS = 30   # يُعدّ المستخدم "نشطاً الآن" إن ظهرت صفحته خلال هذه المدة (استعلام الشريط كل 4 ثوان)
    EXERCISE_CLAIM_SECONDS = 60    # مهلة قول "أنا" بعد ضغطة زر التمرين قبل إلغائها
    HELP_CALL_MINUTES = 30         # ينتهي نداء المساعدة تلقائياً بعد هذه المدة إن لم يُلغَ
    TREND_MIN_CHANGE_PCT = 10      # أقل تغير (نسبة من مدى عرض المؤشر) حتى لا نعلن اتجاهاً من ضجيج
