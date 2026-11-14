#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AstroHab - crew health monitoring for a space station
=====================================================
Sections:

    1.  Settings            read variables from .env or the environment
    2.  Vitals model        limits, evaluation, simulation
    3.  Database            users, history, alerts, chat (SQLite)
    4.  Engine              per-user state, automatic alarm and auto-silence
    5.  Arduino             serial link with automatic reconnection
    6.  Voice               spoken alerts (Arabic or English) on the host computer
    7.  Assistant           Gemini with key rotation, retries and alarm commands
    8.  NASA data           CSV files from data/nasa, limit derivation
    8b. Languages           Arabic / English interface
    9.  Templates           web pages (HTML/CSS/JS) and the built-in fallback chart
    10. Web app             Flask routes, login protection, security headers
    11. Wiring and startup  event hooks, HTTPS port, entry point

Run:
    pip install -r requirements.txt
    copy .env.example to .env and fill in your values, then:
    python astrohab.py          then open  http://localhost:5000

.env variables:
    GEMINI_API_KEYS=key1,key2        Gemini keys, comma separated (rotated on quota errors)
    GEMINI_MODEL=gemini-3.6-flash    model name
    GEMINI_FALLBACK_MODEL=           optional model used if the main one stays busy
    SECRET_KEY=long-random-text      signs login sessions
    SERIAL_PORT=COM7                 Arduino port
    HOST=0.0.0.0                     0.0.0.0 to reach the site from a phone, 127.0.0.1 for this computer only
    HTTPS_ENABLED=true               extra HTTPS port (default 5443), needed for the microphone on a phone
    SERIAL_ENABLED=true / VOICE_ENABLED=true
    REGISTRATION_CODE=               optional invite code required to create accounts after the admin
    ALLOW_REMOTE_FIRST_ADMIN=false   the first (admin) account may only be created from this computer
                                     (localhost); set true only in setups where every request looks remote
    Real environment variables win over the .env file (an empty value does not block the file).

Reference limits:
    No limits are written in the code. The admin sets them from the "NASA Data" page in one of two ways:
      1) derive them from a column of a CSV file in data/nasa (warning and danger at chosen percentiles)
      2) import explicit limits from data/nasa/limits.csv with the columns:
         metric,warning_low,warning_high,danger_low,danger_high,unit,source
    The same column can also drive the metric's readings. Until limits are set the system declares no danger.

Arduino protocol (see astrohab_arduino.ino):
    computer -> Arduino:   BUZZER_ON   and   BUZZER_OFF   (also re-sent every second as a heartbeat:
                           the Arduino silences the buzzer by itself if the heartbeat stops)
    Arduino -> computer:   exercise_confirmed   (when the exercise button is pressed)
    Without an Arduino the system runs in simulation and retries the connection every 5 seconds.

Project note: this software was built with Claude (Anthropic)."""

import csv
import functools
import hmac
import io
import ipaddress
import json
import math
import os
import queue
import random
import re
import secrets
import sqlite3
import tempfile
import threading
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)
from jinja2 import DictLoader, Environment
from werkzeug.security import check_password_hash, generate_password_hash

# ---- Load the parts in order into this module's namespace --------------------------------------------
_PARTS_DIR = Path(__file__).resolve().parent / "astrohab_parts"
_PARTS = ('01_settings', '02_vitals_model', '03_database', '04_engine', '05_arduino_and_voice', '06_assistant', '07_nasa_data', '08_templates', '09_web_app', '10_startup')
for _part in _PARTS:
    _path = _PARTS_DIR / (_part + ".py")
    exec(compile(_path.read_text(encoding="utf-8"), str(_path), "exec"), globals())
del _part, _path


if __name__ == "__main__":
    start_background()
    print(f"[إعدادات] مجلد البرنامج: {BASE_DIR}")
    print(f"[إعدادات] الملفات في المجلد: {', '.join(sorted(x.name for x in BASE_DIR.iterdir()))}")
    print(f"[إعدادات] ملف الإعدادات: {ENV_FILE_USED or 'غير موجود (ضع ملف .env بجانب astrohab.py)'}")
    print(f"[إعدادات] عدد مفاتيح Gemini المقروءة: {len(Config.API_KEYS)}")
    if not Config.API_KEYS:
        print("[تنبيه] لا توجد مفاتيح Gemini. تأكد أنك فككت الضغط عن الملف ثم شغلت astrohab.py من المجلد المفكوك.")
    https_ok = _start_https()
    lan = _lan_address() if Config.HOST in ("0.0.0.0", "") else None
    print()
    print(f"على هذا الحاسوب (الميكروفون يعمل):   http://localhost:{Config.PORT}")
    if lan:
        if https_ok:
            print(f"من الجوال (الميكروفون يعمل):          https://{lan}:{Config.HTTPS_PORT}")
            print("   عند التحذير الأمني اضغط: متقدم ثم المتابعة إلى الموقع (الشهادة ذاتية التوقيع)")
        print(f"من الجوال (بدون ميكروفون):           http://{lan}:{Config.PORT}")
    print()
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
