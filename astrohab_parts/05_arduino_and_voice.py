# AstroHab part: 05_arduino_and_voice. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 5. الأردوينو (السيريال)
# ============================================================
hardware_status = {"connected": False, "error": ""}


def _serial_loop():
    try:
        import serial
    except ImportError:
        hardware_status["error"] = "مكتبة pyserial غير مثبتة"
        print("[serial] مكتبة pyserial غير مثبتة، يعمل النظام بالمحاكاة فقط.")
        return

    last_error = None
    while True:
        ser = None
        try:
            ser = serial.Serial(Config.SERIAL_PORT, Config.BAUD_RATE, timeout=0.1)
            time.sleep(2)  # لوحات NodeMCU تعيد التشغيل عند فتح المنفذ، نمهلها حتى تجهز
            while not engine.outbox.empty():  # تجاهل أوامر قديمة تراكمت أثناء الانقطاع
                engine.outbox.get_nowait()
            hardware_status.update(connected=True, error="")
            last_error = None
            print(f"[serial] متصل بالمنفذ {Config.SERIAL_PORT}")
            last_press = 0.0
            last_beat = 0.0
            while True:
                beat_now = time.time()
                if beat_now - last_beat >= Config.BUZZER_HEARTBEAT_SECONDS:
                    # نبضة حياة: نعيد إرسال الحالة المطلوبة كل ثانية. هذا يعيد مزامنة الجهاز بعد
                    # أي إعادة تشغيل، والأردوينو يُسكت الجرس وحده إن توقفت النبضات.
                    last_beat = beat_now
                    ser.write(b"BUZZER_ON\n" if engine.desired_buzzer() else b"BUZZER_OFF\n")
                while True:  # إرسال الأوامر المعلقة
                    try:
                        ser.write(engine.outbox.get_nowait())
                    except queue.Empty:
                        break
                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8", errors="ignore").strip().lower()
                    now = time.time()
                    if "exercise_confirmed" in line and now - last_press > 3:
                        last_press = now
                        exercise_pressed()
                time.sleep(0.05)
        except Exception as exc:
            hardware_status.update(connected=False, error=str(exc))
            if str(exc) != last_error:
                print(f"[serial] {exc} (المحاكاة تعمل، وإعادة المحاولة كل 5 ثوان)")
                last_error = str(exc)
            time.sleep(5)
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass


# ============================================================
# 6. الصوت
# ============================================================
_voice_queue = queue.Queue(maxsize=5)


def _is_arabic(text):
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def _speak_arabic(text):
    from gtts import gTTS
    try:
        from playsound3 import playsound  # بديل حديث لـ playsound يعمل على بايثون 3.10 فما فوق
    except ImportError:
        from playsound import playsound
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        gTTS(text=text, lang="ar").save(path)
        playsound(path)
    finally:
        if os.path.exists(path):
            os.remove(path)


def _speak_english(text):
    import pyttsx3
    tts = pyttsx3.init()
    tts.setProperty("rate", 155)
    tts.setProperty("volume", 1.0)
    tts.say(text)
    tts.runAndWait()


def _voice_loop():
    while True:
        text = _voice_queue.get()
        try:
            (_speak_arabic if _is_arabic(text) else _speak_english)(text)
        except Exception as exc:
            print(f"[voice] خطأ: {exc}")
        finally:
            _voice_queue.task_done()


def speak(text):
    if not Config.VOICE_ENABLED or not text:
        return
    try:
        _voice_queue.put_nowait(text)
    except queue.Full:
        pass  # تجاهل الكلام الزائد بدل تراكمه
