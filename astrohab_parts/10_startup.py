# AstroHab part: 10_startup. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 11. ربط الأحداث والتشغيل
# ============================================================
def _on_alert(username, level, reason):
    add_alert(username, level, reason)
    if level == "danger":
        add_chat(username, "system", bi(f"تنبيه: {reason['ar']}", f"Alert: {reason['en']}"))
        if Config.SPEAK_AUTO:
            speak(pick(reason, user_lang.get(username, "ar")))


def _on_exercise(username):
    try:
        add_exercise(username, None, "button")
    except Exception as exc:
        print(f"[exercise] {exc}")
    add_chat(username, "system", bi("تم تأكيد إنهاء التمرين عبر الزر، وتحسنت كثافة العظام في المحاكاة. افتح صفحة التمارين وسجّل مدة التمرين ونوعه.",
                                    "Exercise confirmed with the button; bone density improved in the simulation. Open the Exercise page and log the minutes and type."))
    if user_lang.get(username) == "en":
        prompt = "Tell the commander briefly and enthusiastically, in English: well done, the exercise was detected and bone density improved."
    else:
        prompt = "قل للقائد بإيجاز وحماس: أحسنت، تم رصد التمرين وتحسنت كثافة العظام."
    ask_assistant(username, prompt, user_initiated=False)


def start_background():
    init_db()
    reference.reload()
    engine.alert_listeners.append(_on_alert)
    engine.exercise_listeners.append(_on_exercise)
    if Config.VOICE_ENABLED:
        threading.Thread(target=_voice_loop, daemon=True, name="voice").start()
    if Config.SERIAL_ENABLED:
        threading.Thread(target=_serial_loop, daemon=True, name="serial").start()
    engine.start()


def _lan_address():
    """عنوان الجهاز في الشبكة المحلية (لفتح الموقع من الجوال)."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def _ensure_cert():
    """يولّد شهادة HTTPS ذاتية التوقيع مرة واحدة في data/cert."""
    import datetime
    import ipaddress
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_dir = BASE_DIR / "data" / "cert"
    cert_dir.mkdir(parents=True, exist_ok=True)
    crt, key = cert_dir / "astrohab.crt", cert_dir / "astrohab.key"
    if crt.exists() and key.exists():
        return str(crt), str(key)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AstroHab")])
    names = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    lan = _lan_address()
    if lan:
        names.append(x509.IPAddress(ipaddress.ip_address(lan)))
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(private.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .sign(private, hashes.SHA256()))
    key.write_bytes(private.private_bytes(serialization.Encoding.PEM,
                                          serialization.PrivateFormat.TraditionalOpenSSL,
                                          serialization.NoEncryption()))
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(crt), str(key)


def _start_https():
    """يشغّل منفذ HTTPS إضافي. المتصفحات لا تسمح بالميكروفون إلا في اتصال آمن."""
    if not Config.HTTPS_ENABLED:
        return False
    try:
        from werkzeug.serving import make_server
        crt, key = _ensure_cert()
        server = make_server(Config.HOST, Config.HTTPS_PORT, app, threaded=True, ssl_context=(crt, key))
    except Exception as exc:
        print(f"[https] تعذر تشغيل HTTPS ({exc}). ثبّت المكتبة بالأمر: pip install cryptography")
        return False
    threading.Thread(target=server.serve_forever, daemon=True, name="https").start()
    return True
