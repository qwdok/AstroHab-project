#!/usr/bin/env python3
"""يحوّل ملفات NASA الخام "Flight Crew Physiological Data for Crew State Monitoring" إلى ملف صغير يقرأه AstroHab.

الملفات الخام (مثل 26_CA.csv و26_DA.csv و26_SS.csv) إشارات بمعدل 256 قراءة في الثانية: ECG وR (تنفس) وGSR
(توصيل الجلد) وعشرون قناة EEG وعمود Event. هذا البرنامج يقسم كل تسجيل إلى نوافذ زمنية ويحسب لكل نافذة:
  heart_rate_bpm    نبض القلب (وسيط الفواصل بين قمم ECG، بعد فلترة 5 إلى 25 هرتز؛ يُرفض التسجيل إن لم تبرز القمم عن الضجيج)
  breaths_per_min   عدد الأنفاس في الدقيقة (قمم إشارة R بعد فلترة 0.1 إلى 0.7 هرتز)
  gsr_raw           متوسط GSR كما سُجّل (وحدة خام غير معايرة)
  gsr_vs_subject_median   متوسط GSR مقسوماً على وسيط GSR لنفس المشارك (قراءة نسبية، لأن خط الأساس يختلف بين الأشخاص)
  state             حالة التجربة من عمود Event: none, startle (1), channelized (2), diverted (5)
البرنامج لا يضيف أي حد صحي ولا رقماً من عنده: كل القيم مشتقة من الإشارات، والحدود تشتقها صفحة "بيانات NASA" لاحقاً.

الاستخدام (يحتاج numpy وscipy، وهما ليسا من متطلبات AstroHab نفسها):
    python tools/prepare_csm.py مجلد_أو_ملفات... -o data/nasa/csm_vitals.csv
    (الخيارات: --window 30 --step 10 --with-loft)
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

FS = 256.0                     # معدل أخذ العينات الموثق في وصف المجموعة
STATE_NAMES = {0: "none", 1: "startle", 2: "channelized", 5: "diverted"}
NAME_RE = re.compile(r"^(?:.*?[-_ ])?(\d+)_(CA|DA|SS|LOFT)\.csv$", re.IGNORECASE)
HR_MIN_RR, HR_MAX_RR = 0.4, 1.5  # فواصل بين الضربات خارج هذا المدى (أقل من 40 أو أكثر من 150 نبضة) تُعد خطأ كشف
MIN_BEATS = 12                  # أقل عدد ضربات صالحة في النافذة لنُصدر نبضاً
MAX_RR_SPREAD = 0.25            # أقصى تشتت نسبي (MAD / الوسيط) للفواصل داخل النافذة
MIN_PEAK_SNR = 3.5              # القمة النموذجية يجب أن تبرز عن ضجيج الإشارة بهذه النسبة (الضجيج العشوائي يعطي نحو 2، والتسجيلات الجيدة 4.7 فأكثر)
OUT_COLUMNS = ["sample", "subject", "recording", "state", "time_s",
               "heart_rate_bpm", "breaths_per_min", "gsr_raw", "gsr_vs_subject_median"]


def _np():
    try:
        import numpy as np
        from scipy.signal import butter, filtfilt, find_peaks
    except ImportError:
        sys.exit("This tool needs numpy and scipy:  pip install numpy scipy")
    return np, butter, filtfilt, find_peaks


def parse_name(path):
    """(رقم المشارك، نوع التسجيل) من اسم الملف، أو None إن لم يطابق تسمية المجموعة."""
    m = NAME_RE.match(Path(path).name)
    return (int(m.group(1)), m.group(2).upper()) if m else None


def read_signals(path):
    """يقرأ الأعمدة المطلوبة فقط (تجاهل EEG) ويرجع قاموساً من مصفوفات numpy."""
    np, *_ = _np()
    cols = {"TimeSecs": [], "ECG": [], "R": [], "GSR": [], "Event": []}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        try:
            idx = {name: header.index(name) for name in cols}
        except ValueError as exc:
            raise ValueError(f"missing column: {exc}") from None
        for row in reader:
            try:
                vals = [float(row[idx[name]]) for name in cols]
            except (ValueError, IndexError):
                continue  # صف ناقص أو غير رقمي
            for name, v in zip(cols, vals):
                cols[name].append(v)
    return {k: np.asarray(v, dtype=float) for k, v in cols.items()}


def _flat(x):
    """إشارة بلا تغير يُعتد به (حساس غير موصول أو أصفار)."""
    return len(x) == 0 or float(x.std()) < 1e-6 or float((x == 0).mean()) > 0.5


def analyse(sig, window=30.0, step=10.0):
    """يرجع (rows, notes): نوافذ {t0, state, hr, resp, gsr} وملاحظات عن الإشارات التي رُفضت."""
    np, butter, filtfilt, find_peaks = _np()
    t = sig["TimeSecs"]
    notes = []
    if len(t) < FS * window or not np.all(np.diff(t) >= 0):
        return [], ["recording shorter than one window or time not increasing"]
    tu = np.arange(t[0], t[-1], 1 / FS)
    ecg, resp, gsr = (np.interp(tu, t, sig[k]) for k in ("ECG", "R", "GSR"))
    event = np.interp(tu, t, sig["Event"]).round().astype(int)

    # ---- نبض القلب ----
    beat_t = beat_rr = np.array([])
    if _flat(ecg):
        notes.append("ECG is flat or zero (sensor problem): no heart rate")
    else:
        b, a = butter(2, [5 / (FS / 2), 25 / (FS / 2)], btype="band")
        e = filtfilt(b, a, ecg)
        noise = 1.4826 * float(np.median(np.abs(e - np.median(e))))  # تقدير قوي لضجيج الإشارة
        best = None
        for sign in (1, -1):  # اتجاه الموجة يختلف بين الأجهزة: نأخذ الاتجاه الذي تبرز قممه أكثر
            x = sign * e
            pk, _ = find_peaks(x, distance=int(0.33 * FS), height=0.5 * np.percentile(x, 99))
            snr = float(np.median(x[pk]) / noise) if len(pk) and noise > 0 else 0.0
            if best is None or snr > best[0]:
                best = (snr, pk)
        pk = best[1]
        if best[0] < MIN_PEAK_SNR:
            notes.append(f"ECG too noisy (peak/noise {best[0]:.1f} < {MIN_PEAK_SNR}): no heart rate")
            pk = pk[:0]
        rr = np.diff(pk) / FS
        ok = (rr > HR_MIN_RR) & (rr < HR_MAX_RR)
        beat_t, beat_rr = tu[pk][1:][ok], rr[ok]
        if len(beat_rr) < MIN_BEATS and not any("too noisy" in n for n in notes):
            notes.append("too few clean heart beats found")

    # ---- التنفس ----
    breath_t = np.array([])
    if _flat(resp):
        notes.append("respiration signal is flat: no breathing rate")
    else:
        b2, a2 = butter(2, [0.1 / (FS / 2), 0.7 / (FS / 2)], btype="band")
        r = filtfilt(b2, a2, resp - resp.mean())
        pk2, _ = find_peaks(r, distance=int(1.5 * FS), prominence=0.3 * r.std())
        breath_t = tu[pk2]

    rows = []
    start = float(tu[0])
    while start + window <= tu[-1] + 1e-9:
        end = start + window
        lo, hi = int((start - tu[0]) * FS), int((end - tu[0]) * FS)
        hr = resp_rate = None
        m = (beat_t >= start) & (beat_t < end)
        if m.sum() >= MIN_BEATS:
            rr = beat_rr[m]
            med = float(np.median(rr))
            if float(np.median(np.abs(rr - med))) / med <= MAX_RR_SPREAD:
                hr = 60.0 / med
        if len(breath_t):
            n = int(((breath_t >= start) & (breath_t < end)).sum())
            if n >= 2:
                resp_rate = n * 60.0 / window
        ev = event[lo:hi]
        code = int(np.bincount(np.where(np.isin(ev, list(STATE_NAMES)), ev, 0)).argmax())
        rows.append({"t0": start, "state": STATE_NAMES[code], "hr": hr, "resp": resp_rate,
                     "gsr": None if _flat(gsr[lo:hi]) else float(gsr[lo:hi].mean())})
        start += step
    return rows, notes


def find_inputs(paths, with_loft):
    files = []
    for p in map(Path, paths):
        files += sorted(p.rglob("*.csv")) if p.is_dir() else [p]
    out = []
    for f in files:
        parsed = parse_name(f)
        if parsed is None:
            continue
        if parsed[1] == "LOFT" and not with_loft:
            continue
        out.append((f, parsed))
    return sorted(out, key=lambda x: (x[1][0], x[1][1]))


def fmt(v, digits=2):
    return "" if v is None else f"{v:.{digits}f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert NASA crew-state-monitoring CSV files into a small AstroHab dataset.")
    ap.add_argument("inputs", nargs="+", help="folders or CSV files named like 26_CA.csv")
    ap.add_argument("-o", "--output", default="data/nasa/csm_vitals.csv")
    ap.add_argument("--window", type=float, default=30.0, help="window length in seconds (default 30)")
    ap.add_argument("--step", type=float, default=10.0, help="step between windows in seconds (default 10)")
    ap.add_argument("--with-loft", action="store_true", help="also process the long LOFT flight-simulator files")
    args = ap.parse_args(argv)
    if args.window < 10 or args.step <= 0:
        sys.exit("window must be at least 10 s and step positive")
    inputs = find_inputs(args.inputs, args.with_loft)
    if not inputs:
        sys.exit("No files named like 26_CA.csv, 26_DA.csv or 26_SS.csv were found.")

    all_rows, report, skipped = [], [], []
    for path, (subject, kind) in inputs:
        t0 = time.time()
        try:
            rows, notes = analyse(read_signals(path), args.window, args.step)
        except (OSError, ValueError, csv.Error) as exc:
            rows, notes = [], [str(exc)]
        for r in rows:
            r.update(subject=subject, recording=kind)
        all_rows += rows
        hrs = [r["hr"] for r in rows if r["hr"] is not None]
        brs = [r["resp"] for r in rows if r["resp"] is not None]
        line = (f"{path.name}: {len(rows)} windows, heart rate in {len(hrs)}, breathing in {len(brs)}"
                f" ({time.time() - t0:.0f}s)" + ("".join(f"; NOTE: {n}" for n in notes)))
        print(line); report.append(line)
        if notes and not hrs and not brs:
            skipped.append(path.name)

    medians = {}
    for subject in {r["subject"] for r in all_rows}:
        vals = sorted(r["gsr"] for r in all_rows if r["subject"] == subject and r["gsr"] is not None)
        if vals:
            medians[subject] = vals[len(vals) // 2]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(OUT_COLUMNS)
        for r in all_rows:
            if r["hr"] is None and r["resp"] is None and r["gsr"] is None:
                continue
            ratio = r["gsr"] / medians[r["subject"]] if r["gsr"] is not None and medians.get(r["subject"]) else None
            w.writerow([f'{r["subject"]}_{r["recording"]}@{r["t0"]:.0f}s', r["subject"], r["recording"], r["state"],
                        f'{r["t0"]:.0f}', fmt(r["hr"], 1), fmt(r["resp"], 1), fmt(r["gsr"], 1), fmt(ratio, 3)])
    sources = out.with_name(out.stem + "_SOURCES.txt")
    sources.write_text(
        "Dataset: Flight Crew Physiological Data for Crew State Monitoring (NASA Open Data Portal)\n"
        "URL: https://data.nasa.gov/dataset/flight-crew-physiological-data-for-crew-state-monitoring\n"
        f"Converted on: {time.strftime('%Y-%m-%d')} with tools/prepare_csm.py (window {args.window:g} s, step {args.step:g} s)\n"
        "Method: heart rate = 60 / median beat interval of ECG peaks (band-pass 5-25 Hz, intervals outside 0.4-1.5 s rejected,\n"
        f"  at least {MIN_BEATS} clean beats and relative spread <= {MAX_RR_SPREAD} per window); breathing = peaks of the R signal (band-pass 0.1-0.7 Hz);\n"
        "  GSR = window mean of the raw signal, and the same divided by the median GSR of that subject.\n"
        "Nothing was added by the tool: no health limits and no outside values.\n"
        "Files processed:\n" + "\n".join("  " + line for line in report) + "\n"
        + ("Files without usable signals: " + ", ".join(skipped) + "\n" if skipped else ""), encoding="utf-8")
    print(f"\nWrote {out} ({sum(1 for _ in open(out, encoding='utf-8')) - 1} rows) and {sources.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
