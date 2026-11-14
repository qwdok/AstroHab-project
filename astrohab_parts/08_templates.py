# AstroHab part: 08_templates. Loaded by astrohab.py into the same module namespace (see astrohab.py).
# ============================================================
# 9. الواجهة (القوالب)
# ============================================================
# رسم بياني احتياطي مدمج: إن لم يوجد static/vendor/chart.umd.js (Chart.js الأصلي) تعمل اللوحة بهذا الرسم
# البسيط بدون أي اتصال بالإنترنت. يدعم ما تستخدمه الصفحات فقط: خطوط، تعبئة، خطوط متقطعة، مجال محور y.
CHART_SHIM = r"""
if (typeof Chart === 'undefined') {
  window.Chart = function (canvas, config) {
    var self = this, ctx = canvas.getContext('2d');
    this.data = config.data || {labels: [], datasets: []};
    this.options = config.options || {};
    canvas.style.display = 'block'; canvas.style.width = '100%'; canvas.style.height = '100%';

    function niceScale(lo, hi) {
      if (!(hi > lo)) { lo -= 1; hi += 1; }
      var raw = (hi - lo) / 4, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = mag * 10;
      [1, 2, 2.5, 5, 10].some(function (m) { if (m * mag >= raw) { step = m * mag; return true; } return false; });
      return {lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step: step};
    }

    function draw() {
      var d = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) { return; }
      canvas.width = Math.round(w * d); canvas.height = Math.round(h * d);
      ctx.setTransform(d, 0, 0, d, 0, 0);
      ctx.clearRect(0, 0, w, h);
      var sets = self.data.datasets || [], labels = self.data.labels || [];
      var y = ((self.options.scales || {}).y) || {};
      var lo = Infinity, hi = -Infinity;
      sets.forEach(function (s) {
        (s.data || []).forEach(function (v) {
          if (v !== null && v !== undefined && isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
        });
      });
      if (typeof y.suggestedMin === 'number') { lo = Math.min(lo, y.suggestedMin); }
      if (typeof y.suggestedMax === 'number') { hi = Math.max(hi, y.suggestedMax); }
      if (!isFinite(lo) || !isFinite(hi)) { lo = 0; hi = 1; }
      var sc = niceScale(lo, hi), L = 48, R = 12, T = 10, B = 26, pw = w - L - R, ph = h - T - B;
      var X = function (i, n) { return n > 1 ? L + pw * i / (n - 1) : L + pw / 2; };
      var Y = function (v) { return T + ph * (1 - (v - sc.lo) / (sc.hi - sc.lo)); };

      ctx.font = '11px "IBM Plex Sans Arabic", "Segoe UI", sans-serif';
      ctx.fillStyle = '#8b9bb1'; ctx.strokeStyle = 'rgba(139,155,177,.12)'; ctx.lineWidth = 1; ctx.setLineDash([]);
      ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
      for (var v = sc.lo; v <= sc.hi + sc.step / 1e6; v += sc.step) {
        var gy = Math.round(Y(v)) + 0.5;
        ctx.beginPath(); ctx.moveTo(L, gy); ctx.lineTo(w - R, gy); ctx.stroke();
        ctx.fillText(String(+v.toFixed(4)), L - 6, gy);
      }
      var n = labels.length, every = Math.max(1, Math.ceil(n / 8));
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      for (var i = 0; i < n; i += every) { if (labels[i]) { ctx.fillText(String(labels[i]), X(i, n), h - B + 8); } }

      sets.forEach(function (s) {
        var pts = s.data || [], segs = [], cur = [];
        pts.forEach(function (val, i) {
          if (val === null || val === undefined || !isFinite(val)) { if (cur.length) { segs.push(cur); cur = []; } }
          else { cur.push([X(i, pts.length), Y(val)]); }
        });
        if (cur.length) { segs.push(cur); }
        ctx.lineJoin = 'round'; ctx.lineWidth = s.borderWidth || 2; ctx.strokeStyle = s.borderColor || '#5b9cf5';
        segs.forEach(function (seg) {
          ctx.setLineDash(s.borderDash || []);
          ctx.beginPath();
          seg.forEach(function (p, k) { if (k) { ctx.lineTo(p[0], p[1]); } else { ctx.moveTo(p[0], p[1]); } });
          ctx.stroke();
          if (s.fill && seg.length > 1) {
            ctx.lineTo(seg[seg.length - 1][0], T + ph); ctx.lineTo(seg[0][0], T + ph); ctx.closePath();
            ctx.fillStyle = s.backgroundColor || 'rgba(91,156,245,.10)'; ctx.fill();
          }
          if (s.pointRadius > 0) {
            ctx.fillStyle = s.borderColor || '#5b9cf5';
            seg.forEach(function (p) { ctx.beginPath(); ctx.arc(p[0], p[1], s.pointRadius, 0, 6.2832); ctx.fill(); });
          }
        });
      });
      ctx.setLineDash([]);
    }

    this.update = function () { draw(); };
    this.destroy = function () {};
    window.addEventListener('resize', draw);
    if (window.ResizeObserver) { new ResizeObserver(draw).observe(canvas.parentNode); }
    draw();
  };
}
"""

_CHART_VENDOR = BASE_DIR / "static" / "vendor" / "chart.umd.js"


def _chart_head():
    """وسوم الرسم البياني: Chart.js المحلي إن وُجد (بدون CDN)، ثم الرسم الاحتياطي المدمج."""
    tag = '<script src="/static/vendor/chart.umd.js"></script>' if _CHART_VENDOR.is_file() else ""
    return tag + "<script>" + CHART_SHIM + "</script>"


BASE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="csrf-token" content="{{ csrf_token }}">
<title>{% block title %}AstroHab{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #0c1420; --panel: #121c2b; --panel-2: #182538; --line: #243349;
    --text: #e7edf5; --muted: #8b9bb1; --accent: #5b9cf5;
    --ok: #3fb68b; --warn: #e2a93b; --crit: #e5534b;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "IBM Plex Sans Arabic", "Segoe UI", Tahoma, sans-serif; color: var(--text); line-height: 1.6;
       font-size: 15px; min-height: 100vh; background-color: var(--bg);
       background-image: radial-gradient(1px 1px at 12% 18%, rgba(231,237,245,.55), transparent),
           radial-gradient(1px 1px at 63% 8%, rgba(231,237,245,.4), transparent),
           radial-gradient(1.4px 1.4px at 81% 36%, rgba(231,237,245,.5), transparent),
           radial-gradient(1px 1px at 32% 62%, rgba(231,237,245,.35), transparent),
           radial-gradient(1px 1px at 92% 78%, rgba(231,237,245,.4), transparent),
           radial-gradient(1.2px 1.2px at 47% 88%, rgba(231,237,245,.35), transparent),
           radial-gradient(ellipse at 50% -10%, rgba(91,156,245,.12), transparent 60%);
       background-size: 420px 360px, 530px 410px, 610px 470px, 380px 330px, 710px 540px, 470px 590px, 100% 520px;
       background-repeat: repeat, repeat, repeat, repeat, repeat, repeat, no-repeat; }
a { color: inherit; text-decoration: none; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.muted { color: var(--muted); }

.topbar { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 14px; min-height: 60px; padding: 0 20px;
          background: rgba(18,28,43,.92); border-bottom: 1px solid var(--line); position: relative; z-index: 20; }
.brand { display: flex; align-items: center; gap: 10px; }
.logo { width: 30px; height: 30px; flex: none; }
.brand-name { font-size: 20px; font-weight: 600; letter-spacing: .06em;
              background: linear-gradient(90deg, #e7edf5, #8fbaf7); -webkit-background-clip: text; background-clip: text;
              color: transparent; }
.brand-sub { font-size: 13px; color: var(--muted); white-space: nowrap; }
.topbar nav { display: flex; align-self: stretch; min-height: 60px; }
.topbar nav > a, .topbar nav details > summary { display: flex; align-items: center; padding: 0 9px; white-space: nowrap; color: var(--muted);
                border-bottom: 2px solid transparent; font-size: 13.5px; }
.topbar nav details { position: relative; display: flex; }
.topbar nav summary { cursor: pointer; list-style: none; gap: 4px; }
.topbar nav summary::-webkit-details-marker { display: none; }
.topbar nav summary::after { content: "\25BE"; font-size: 11px; }
.topbar nav details[open] > summary, .topbar nav summary:hover { color: var(--text); }
.topbar nav summary.active { color: var(--text); border-bottom-color: var(--accent); }
.more-menu { position: absolute; top: 100%; inset-inline-start: 0; min-width: 190px; background: var(--panel);
             border: 1px solid var(--line); border-radius: 8px; padding: 6px; box-shadow: 0 10px 28px rgba(0,0,0,.45); }
.more-menu a { display: block; padding: 8px 12px; border-radius: 6px; color: var(--muted); font-size: 14px; white-space: nowrap; }
.more-menu a:hover { background: var(--panel-2); color: var(--text); }
.more-menu a.active { color: var(--text); background: var(--panel-2); }
.topbar nav a:hover { color: var(--text); }
.topbar nav > a.active { color: var(--text); border-bottom-color: var(--accent); }
.sos-btn { font: inherit; font-size: 13px; color: #ffb3ae; background: rgba(229,83,75,.12); border: 1px solid rgba(229,83,75,.55);
           border-radius: 6px; padding: 4px 12px; cursor: pointer; white-space: nowrap; }
.sos-btn:hover { background: rgba(229,83,75,.25); }
.sos-btn.armed { color: #fff; background: var(--crit); border-color: var(--crit); }
.crew-alerts:empty { display: none; }
.crew-alerts { display: grid; gap: 1px; background: var(--crit); border-bottom: 1px solid var(--crit); }
.crew-alert { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 8px 24px; background: #2a1618; font-size: 14px; }
.crew-alert.help { background: #3a1517; }
.crew-alert.press, .crew-alert.log { background: #14283d; }
.crew-alert.press .ca-title, .crew-alert.log .ca-title { color: #9cc6fa; }
.crew-alert .ca-title { font-weight: 600; color: #ffb3ae; }
.crew-alert .ca-note { color: var(--muted); font-size: 13px; }
.crew-alert .btn { margin-inline-start: auto; }
.demo-banner { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
               padding: 8px 24px; background: rgba(226,169,59,.14); border-bottom: 1px solid var(--warn); font-size: 14px; }
.user { margin-inline-start: auto; display: flex; align-items: center; gap: 10px; white-space: nowrap; font-size: 14px; color: var(--muted); }
.user a { color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: 4px 12px; }
.user a:hover { border-color: var(--accent); }
.logout-btn { font: inherit; color: var(--text); background: none; border: 1px solid var(--line); border-radius: 6px;
              padding: 4px 12px; cursor: pointer; }
.logout-btn:hover { border-color: var(--accent); }
.inline-form { display: inline; }

.wrap { max-width: 1440px; margin: 0 auto; padding: 20px 28px 36px; display: grid; gap: 16px; }
.wrap > * { min-width: 0; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; }
.panel-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.panel-head h2 { font-size: 16px; font-weight: 600; }
.streak { display: flex; align-items: center; gap: 12px; border: 1px solid var(--line); border-radius: 10px; padding: 8px 14px; margin: 10px 0; width: fit-content; max-width: 100%; }
.streak .st-n { font-size: 30px; font-weight: 600; color: #f2784b; font-variant-numeric: tabular-nums; line-height: 1; }
.streak .st-t { font-size: 12px; color: var(--muted); }
.streak .st-m { font-size: 13px; }
.streak.on { border-color: #e2663f; background: rgba(226,102,63,.13); }
.panel-head span { font-size: 13px; }

/* شريط الحالة العامة */
.strip { --c: var(--ok); display: flex; justify-content: space-between; align-items: center; gap: 20px; flex-wrap: wrap;
         background: var(--panel); border: 1px solid var(--line); border-inline-start: 4px solid var(--c);
         border-radius: 10px; padding: 16px 20px; }
.strip.warning { --c: var(--warn); }
.strip.danger { --c: var(--crit); }
.strip-main { display: flex; align-items: center; gap: 14px; }
.dot { width: 12px; height: 12px; border-radius: 50%; background: var(--c); flex: none; }
.strip.danger .dot { animation: blink 1s ease-in-out infinite; }
@keyframes blink { 50% { opacity: .25; } }
@media (prefers-reduced-motion: reduce) { .strip.danger .dot { animation: none; } }
.strip-title { font-size: 18px; font-weight: 600; color: var(--c); }
.strip-reason { font-size: 14px; color: var(--muted); }
.strip-tools { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.pill { font-size: 13px; color: var(--muted); border: 1px solid var(--line); border-radius: 20px; padding: 3px 12px; }
.pill.on { color: var(--ok); border-color: rgba(63,182,139,.5); }
.seg { display: flex; align-items: center; gap: 0; }
.seg-label { font-size: 13px; color: var(--muted); margin-inline-end: 10px; }
.seg button { font: inherit; font-size: 13px; padding: 6px 16px; color: var(--muted); background: var(--panel-2);
              border: 1px solid var(--line); cursor: pointer; }
.seg button:first-of-type { border-radius: 0 6px 6px 0; }
.seg button:last-of-type { border-radius: 6px 0 0 6px; border-inline-start: 0; }
.seg button.active { color: var(--text); border-color: var(--accent); background: rgba(91,156,245,.18); }
.seg button.active.alarm { border-color: var(--crit); background: rgba(229,83,75,.2); }

/* بطاقات المؤشرات */
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.tile { font: inherit; color: inherit; text-align: start; cursor: pointer; background: var(--panel);
        border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.tile:hover { border-color: #35496a; }
.tile { transition: border-color .25s, box-shadow .25s; }
.tile.lv-warning { border-color: var(--warn); box-shadow: 0 0 0 1px rgba(226,169,59,.25); }
.tile.lv-danger { border-color: var(--crit); animation: tileglow 1.4s ease-in-out infinite; }
.tile.flash { animation: tileflash .6s ease-out; }
.tile.lv-danger.flash { animation: tileflash .6s ease-out, tileglow 1.4s ease-in-out .6s infinite; }
@keyframes tileglow { 0%, 100% { box-shadow: 0 0 0 1px rgba(229,83,75,.3); } 50% { box-shadow: 0 0 18px 2px rgba(229,83,75,.55); } }
@keyframes tileflash { 0% { transform: scale(1.04); } 100% { transform: scale(1); } }
@media (prefers-reduced-motion: reduce) { .tile.lv-danger, .tile.flash, .tile.lv-danger.flash { animation: none; } }
.tile.selected { border-color: var(--accent); background: var(--panel-2); }
.tile-top { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: var(--muted); }
.tile-state { font-size: 12px; }
.tile-state.warning { color: var(--warn); }
.tile-state.danger { color: var(--crit); }
.tile-state.normal { color: var(--ok); }
.tile-val { margin: 6px 0 12px; display: flex; align-items: baseline; gap: 6px; }
.tile-val .v { font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile-val .u { font-size: 13px; color: var(--muted); }
.range { position: relative; height: 6px; border-radius: 3px; direction: ltr; }
.range i { position: absolute; top: -4px; width: 3px; height: 14px; border-radius: 2px; background: var(--text); transform: translateX(-50%); }

.main-grid { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(320px, 1fr); gap: 16px; align-items: stretch; }
.chart-box { position: relative; height: 340px; }

/* المحادثة */
.chat { display: flex; flex-direction: column; }
.messages { flex: 1; min-height: 260px; max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-inline-end: 4px; }
.msg { max-width: 90%; padding: 8px 12px; border-radius: 8px; font-size: 14px; background: var(--panel-2); border: 1px solid var(--line); }
.msg .meta { font-size: 12px; color: var(--muted); margin-bottom: 2px; }
.msg.commander { align-self: flex-start; background: rgba(91,156,245,.16); border-color: rgba(91,156,245,.4); }
.msg.assistant { align-self: flex-end; }
.msg.system { align-self: center; max-width: 100%; text-align: center; background: transparent; border-style: dashed; color: var(--muted); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.chip { font: inherit; font-size: 13px; color: var(--muted); background: transparent; border: 1px solid var(--line);
        border-radius: 16px; padding: 3px 12px; cursor: pointer; }
.chip:hover { color: var(--text); border-color: var(--accent); }
.composer { display: flex; gap: 8px; }
.form-error { min-height: 20px; margin-top: 6px; font-size: 13px; color: var(--crit); }

/* عناصر عامة */
.btn { font: inherit; font-size: 14px; color: var(--text); background: var(--panel-2); border: 1px solid var(--line);
       border-radius: 6px; padding: 8px 16px; cursor: pointer; display: inline-block; text-align: center; }
.btn:hover { border-color: var(--accent); }
.btn-primary { background: var(--accent); border-color: var(--accent); color: #07111f; font-weight: 500; }
.btn-primary:hover { background: #7ab1fa; }
input[type=text], input[type=password], input[type=number], select { font: inherit; font-size: 14px; color: var(--text); background: var(--bg);
       border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; min-width: 0; }
.composer input { flex: 1; }
input:focus, select:focus { border-color: var(--accent); outline: none; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 9px 12px; text-align: start; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { color: var(--muted); font-weight: 500; font-size: 13px; }
td.num { font-variant-numeric: tabular-nums; }
.lvl-warning { color: var(--warn); }
.lvl-danger { color: var(--crit); }
.lvl-normal { color: var(--ok); }
.empty { color: var(--muted); line-height: 1.9; }
code { background: var(--panel-2); border: 1px solid var(--line); padding: 1px 6px; border-radius: 4px; font-size: 13px; }

/* الدخول */
.auth { min-height: 100vh; display: grid; place-items: center; padding: 20px; }
.auth-card { width: min(380px, 100%); background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 32px; }
.auth-card .brand-name { display: block; font-size: 24px; margin-bottom: 2px; }
.auth-card .brand-sub { display: block; margin-bottom: 24px; }
.auth-card label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.auth-card input { width: 100%; margin-bottom: 16px; }
.auth-card .row { display: flex; gap: 10px; }
.auth-card .row .btn { flex: 1; padding: 10px 8px; }
.auth-card .error { color: var(--crit); font-size: 14px; margin-bottom: 16px; }
.auth-card .hint { color: var(--muted); font-size: 13px; margin-top: 18px; }

[hidden] { display: none !important; }
.langsw { display: inline-block; color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: 4px 12px; font-size: 13px; }
.langsw:hover { border-color: var(--accent); }
[dir="ltr"] .seg button:first-of-type { border-radius: 6px 0 0 6px; }
[dir="ltr"] .seg button:last-of-type { border-radius: 0 6px 6px 0; border-inline-start: 0; }
.strip.unset { --c: var(--muted); }
.strip-link { display: inline-block; margin-top: 4px; font-size: 14px; color: var(--accent); }
.strip-link:hover { text-decoration: underline; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: 14px 0; }
.field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
.field input, .field select { width: 100%; }
.check { display: flex; align-items: center; gap: 8px; font-size: 14px; margin-bottom: 14px; }
.result { min-height: 24px; font-size: 14px; color: var(--text); margin-top: 6px; line-height: 1.8; }
.mt { margin-top: 12px; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #2b3d57; border-radius: 4px; }

@media (max-width: 1500px) { .brand-sub { display: none; } }
@media (max-width: 960px) {
    .main-grid { grid-template-columns: 1fr; }
    .topbar { padding: 6px 14px; }
    .topbar nav { flex-wrap: wrap; width: 100%; min-height: 0; order: 3; }
    .topbar nav > a, .topbar nav details > summary { min-height: 40px; }
    .topbar nav details { flex-wrap: wrap; }
    .panel { overflow-x: auto; }
    .main-grid > *, .panel > * { min-width: 0; }
    .chart-box { max-width: 100%; overflow: hidden; }
    input, select, textarea { max-width: 100%; min-width: 0; }
    .more-menu { position: static; box-shadow: none; flex-basis: 100%; min-width: 0; display: flex; flex-wrap: wrap; gap: 2px; }
    .brand-sub { display: none; }
    .wrap { padding: 14px; }
}
@page { size: A4; margin: 14mm; }
@media print {
    body { background: #fff; background-image: none; color: #000; }
    .topbar, .toolbar, .demo-banner, .crew-alerts { display: none; }
    .panel { border-color: #999; background: #fff; }
    th, td { color: #000; }
    .panel, .table-wrap { overflow: visible !important; }
    .sm-table { width: 100%; }
    .sm-table td, .sm-table th { font-size: 9px; padding: 3px 4px; white-space: normal !important; word-break: normal; overflow-wrap: break-word; }
    .sm-table td.num { white-space: nowrap !important; }
}
</style>
{% block head %}{% endblock %}
</head>
<body>
{% block body %}{% endblock %}
</body>
</html>
"""

TOPBAR_TEMPLATE = r"""<header class="topbar">
    <a class="brand" href="/"><svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><ellipse cx="16" cy="16" rx="14" ry="5.5" transform="rotate(-22 16 16)" fill="none" stroke="#5b9cf5" stroke-width="1.4" opacity=".8"/><circle cx="16" cy="16" r="8.5" fill="#182538" stroke="#5b9cf5" stroke-width="1.6"/><polyline points="9.5,16.5 13,16.5 14.6,12.5 17,20 18.8,16.5 22.5,16.5" fill="none" stroke="#3fb68b" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="brand-name">AstroHab</span><span class="brand-sub">مراقبة صحة الطاقم</span></a>
    <nav>
        {% if role == 'doctor' %}
        <a href="/crew" class="{{ 'active' if page == 'crew' }}">الطاقم</a>
        <a href="/summary" class="{{ 'active' if page == 'summary' }}">ملخص الطبيب</a>
        <a href="/hazards" class="{{ 'active' if page == 'hazards' }}">المخاطر الخمسة</a>
        <a href="/nasa" class="{{ 'active' if page == 'nasa' }}">بيانات ناسا</a>
        {% else %}
        <a href="/" class="{{ 'active' if page == 'dashboard' }}">لوحة المراقبة</a>
        <a href="/crew" class="{{ 'active' if page == 'crew' }}">الطاقم</a>
        <a href="/body" class="{{ 'active' if page == 'body' }}">المجسم التفاعلي</a>
        <a href="/checkin" class="{{ 'active' if page == 'checkin' }}">الفحص الذاتي</a>
        <a href="/hazards" class="{{ 'active' if page == 'hazards' }}">المخاطر الخمسة</a>
        <details class="more">
            <summary class="{{ 'active' if page in ('exercise', 'history', 'summary', 'nasa', 'admin') }}">المزيد</summary>
            <div class="more-menu">
                <a href="/exercise" class="{{ 'active' if page == 'exercise' }}">سجل التمارين</a>
                <a href="/history" class="{{ 'active' if page == 'history' }}">السجل والتقارير</a>
                <a href="/summary" class="{{ 'active' if page == 'summary' }}">ملخص الطبيب</a>
                <a href="/nasa" class="{{ 'active' if page == 'nasa' }}">بيانات ناسا</a>
                {% if role == 'admin' %}<a href="/admin" class="{{ 'active' if page == 'admin' }}">الإدارة</a>{% endif %}
            </div>
        </details>
        {% endif %}
    </nav>
    <div class="user">{% if role != 'doctor' %}<button type="button" class="sos-btn" id="sosBtn">{{ topui.sos }}</button>{% endif %}<span>{{ user }}</span><!--LANGSWITCH--><form method="post" action="/logout" class="inline-form"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><button type="submit" class="logout-btn">تسجيل الخروج</button></form></div>
</header>
<div class="crew-alerts" id="crewAlerts" role="alert" aria-live="assertive"></div>
<script>
(function () {
    const T = {{ topui|tojson }};
    const box = document.getElementById('crewAlerts'), sos = document.getElementById('sosBtn') || document.createElement('button');
    const csrf = document.querySelector('meta[name="csrf-token"]').content;
    let mine = false, armed = null, timer = null;
    function post(url, body) {
        return fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
                           body: JSON.stringify(body)}).then(r => r.json().catch(() => ({})));
    }
    function setSos() {
        sos.textContent = mine ? T.sos_cancel : (armed ? T.sos_confirm : T.sos);
        sos.classList.toggle('armed', !!armed || mine);
    }
    sos.addEventListener('click', () => {
        if (mine) { post('/api/crew/help', {action: 'cancel'}).then(refresh); return; }
        if (!armed) { armed = setTimeout(() => { armed = null; setSos(); }, 4000); setSos(); return; }
        clearTimeout(armed); armed = null;
        post('/api/crew/help', {action: 'call'}).then(refresh);
    });
    function render(data) {
        mine = !!data.help_active; setSos();
        box.textContent = '';
        data.alerts.forEach(a => {
            const row = document.createElement('div');
            row.className = 'crew-alert ' + a.kind;
            if (a.kind === 'press') {
                const t = document.createElement('span'); t.className = 'ca-title'; t.textContent = T.press;
                const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-primary'; b.textContent = T.press_claim;
                b.addEventListener('click', () => post('/api/crew/claim', {}).then(r => { if (r && r.ok) location.href = '/exercise'; else refresh(); }));
                row.append(t, b); box.append(row); return;
            }
            if (a.kind === 'log') {
                const t = document.createElement('span'); t.className = 'ca-title'; t.textContent = T.log_pending;
                const b = document.createElement('a'); b.className = 'btn btn-primary'; b.href = '/exercise'; b.textContent = T.log_open;
                row.append(t, b); box.append(row); return;
            }
            const text = document.createElement('span');
            let title;
            if (a.me && a.kind === 'help') title = T.help_mine;
            else title = (a.kind === 'help' ? T.help_other : T.danger_other).replace('{name}', a.user);
            text.className = 'ca-title'; text.textContent = title + (a.metric ? ' (' + a.metric + ')' : '');
            const note = document.createElement('span'); note.className = 'ca-note';
            note.textContent = a.acks.length ? T.ack_by.replace('{names}', a.acks.join(', ')) : T.ack_none;
            row.append(text, note);
            if (!a.me && a.can_ack) {
                if (a.acked) { const ok = document.createElement('span'); ok.className = 'ca-note'; ok.textContent = T.ack_you; row.append(ok); }
                else {
                    const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = T.ack;
                    b.addEventListener('click', () => post('/api/crew/ack', {target: a.user}).then(refresh));
                    row.append(b);
                }
            }
            box.append(row);
        });
    }
    function refresh() {
        return fetch('/api/crew/alerts').then(r => { if (!r.ok) throw 0; return r.json(); }).then(render).catch(() => {});
    }
    refresh(); timer = setInterval(refresh, 4000);
})();
</script>
{% if demo.active %}<div class="demo-banner" role="status"><span><strong>وضع العرض التجريبي:</strong> القيم المعروضة محاكاة مشتقة من حدود بيانات ناسا ولا تُحفظ في السجل. <span id="demoStep">{{ demo.text }}</span></span><form method="post" action="/demo/stop" class="inline-form"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="next" value="{{ path }}"><button type="submit" class="btn">إيقاف العرض</button></form></div>{% endif %}
"""

LOGIN_TEMPLATE = r"""{% extends "base" %}
{% block title %}تسجيل الدخول - AstroHab{% endblock %}
{% block body %}
<main class="auth">
    <div class="auth-card">
        <div style="text-align: end; margin-bottom: 10px"><!--LANGSWITCH--></div>
        <svg class="logo" viewBox="0 0 32 32" aria-hidden="true" style="width:46px;height:46px;display:block;margin-bottom:8px"><ellipse cx="16" cy="16" rx="14" ry="5.5" transform="rotate(-22 16 16)" fill="none" stroke="#5b9cf5" stroke-width="1.4" opacity=".8"/><circle cx="16" cy="16" r="8.5" fill="#182538" stroke="#5b9cf5" stroke-width="1.6"/><polyline points="9.5,16.5 13,16.5 14.6,12.5 17,20 18.8,16.5 22.5,16.5" fill="none" stroke="#3fb68b" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span class="brand-name">AstroHab</span>
        <span class="brand-sub">نظام مراقبة صحة طاقم المحطة الفضائية</span>
        {% if error %}<div class="error" role="alert">{{ error }}</div>{% endif %}
        <form method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <label for="username">اسم المستخدم</label>
            <input type="text" id="username" name="username" required minlength="3" maxlength="32" autocomplete="username">
            <label for="password">كلمة المرور</label>
            <input type="password" id="password" name="password" required autocomplete="current-password">
            {% if need_code %}<label for="invite_code">رمز الدعوة (عند إنشاء حساب فقط)</label>
            <input type="password" id="invite_code" name="invite_code" autocomplete="off">{% endif %}
            <div class="row">
                <button class="btn btn-primary" type="submit" name="action" value="login">تسجيل الدخول</button>
                <button class="btn" type="submit" name="action" value="register">إنشاء حساب</button>
            </div>
        </form>
        <p class="hint">أول حساب يتم إنشاؤه (من الحاسوب نفسه) يصبح مدير النظام.</p>
    </div>
</main>
{% endblock %}
"""

DASHBOARD_TEMPLATE = r"""{% extends "base" %}
{% block title %}لوحة المراقبة - AstroHab{% endblock %}
{% block head %}__CHART_JS__{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section id="strip" class="strip normal" aria-live="polite">
        <div class="strip-main">
            <span class="dot" aria-hidden="true"></span>
            <div>
                <div class="strip-title" id="stripTitle">جارٍ التحميل</div>
                <div class="strip-reason" id="stripReason"></div>
                <a class="strip-link" id="setupLink" href="/nasa" hidden>تحديد الحدود من بيانات ناسا</a>
            </div>
        </div>
        <div class="strip-tools">
            <span class="pill" id="hwPill">العتاد: --</span>
            <div class="seg" role="group" aria-label="جرس الإنذار">
                <span class="seg-label">جرس الإنذار</span>
                <button type="button" id="alarmOff" onclick="setBuzzer(0)">مطفأ</button>
                <button type="button" id="alarmOn" class="alarm" onclick="setBuzzer(1)">يعمل</button>
            </div>
        </div>
    </section>

    <section class="tiles" id="tiles" aria-label="المؤشرات الحيوية"></section>

    <section class="main-grid">
        <div class="panel">
            <div class="panel-head">
                <h2 id="chartTitle">المؤشر</h2>
                <span class="muted" id="chartSource"></span>
            </div>
            <div class="chart-box"><canvas id="chart"></canvas></div>
        </div>

        <div class="panel chat">
            <div class="panel-head"><h2>المساعد</h2>
                <label class="check" style="margin: 0"><input type="checkbox" id="voiceToggle"> صوت الردود على هذا الجهاز</label></div>
            <div class="messages" id="messages" aria-live="polite"></div>
            <div class="chips" id="chips"></div>
            <form class="composer" onsubmit="return send(event)">
                <input type="text" id="input" maxlength="500" placeholder="اكتب أمراً أو سؤالاً" autocomplete="off" aria-label="رسالة">
                <button class="btn btn-primary" type="submit">إرسال</button>
                <button class="btn" type="button" id="micBtn" onclick="dictate()">إملاء صوتي</button>
            </form>
            <div class="form-error" id="formError" role="alert"></div>
        </div>
    </section>
</main>

<script>
const LIMITS = {{ limits|tojson }};
let limitsVersion = {{ limits_version }};
const KEYS = Object.keys(LIMITS);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const LOCALE = '__LOCALE__';
const POINTS = 40;
const STATE_TEXT = {normal: 'مستقر', warning: 'تحذير', danger: 'خطر'};
const TITLES = {normal: 'الحالة مستقرة', warning: 'تحذير', danger: 'حالة خطر', unconfigured: 'الحدود المرجعية غير محددة'};
const SENDERS = {commander: 'القائد', assistant: 'المساعد', system: 'النظام'};
const ZONE = {normal: 'rgba(63,182,139,.55)', warning: 'rgba(226,169,59,.65)', danger: 'rgba(229,83,75,.7)', none: 'rgba(139,155,177,.35)'};
const PROMPTS = ['ما حالة المؤشرات الآن؟', 'لماذا الإنذار؟', 'شغل الإنذار', 'أوقف الإنذار'];

const series = {}, times = Array(POINTS).fill('');
KEYS.forEach(k => series[k] = Array(POINTS).fill(null));
let current = KEYS[0];

/* تصنيف قيمة حسب حدود المؤشر */
function classify(key, value) {
    for (const sev of ['danger', 'warning']) {
        const [lo, hi] = LIMITS[key][sev];
        if ((hi !== null && value > hi) || (lo !== null && value < lo)) return sev;
    }
    return 'normal';
}

/* شريط المجال: مناطق الأمان والتحذير والخطر على مجال العرض */
function rangeGradient(key) {
    const L = LIMITS[key], [smin, smax] = L.scale;
    const limited = ['warning', 'danger'].some(s => L[s].some(v => v !== null));
    if (!limited) return ZONE.none;
    const cuts = new Set([smin, smax]);
    ['warning', 'danger'].forEach(s => L[s].forEach(v => { if (v !== null && v > smin && v < smax) cuts.add(v); }));
    const pts = [...cuts].sort((a, b) => a - b), pct = x => ((x - smin) / (smax - smin) * 100).toFixed(2);
    const stops = [];
    for (let i = 0; i < pts.length - 1; i++) {
        const color = ZONE[classify(key, (pts[i] + pts[i + 1]) / 2)];
        stops.push(`${color} ${pct(pts[i])}%`, `${color} ${pct(pts[i + 1])}%`);
    }
    return `linear-gradient(to right, ${stops.join(', ')})`;
}

/* بناء البطاقات */
const tilesEl = document.getElementById('tiles');
KEYS.forEach(k => {
    const L = LIMITS[k], b = document.createElement('button');
    b.type = 'button'; b.className = 'tile' + (k === current ? ' selected' : ''); b.dataset.key = k;
    b.innerHTML = `<div class="tile-top"><span></span><span class="tile-state"></span></div>
        <div class="tile-val"><span class="v">--</span><span class="u"></span></div>
        <div class="range"><i></i></div>`;
    b.querySelector('.tile-top span').textContent = L.label;
    b.querySelector('.u').textContent = L.unit;
    b.querySelector('.range').style.background = rangeGradient(k);
    b.addEventListener('click', () => selectMetric(k));
    tilesEl.appendChild(b);
});

function updateTile(k, value) {
    const tile = tilesEl.querySelector(`[data-key="${k}"]`), L = LIMITS[k], [smin, smax] = L.scale;
    tile.querySelector('.v').textContent = value;
    const limited = ['warning', 'danger'].some(s => L[s].some(v => v !== null));
    const state = tile.querySelector('.tile-state'), cls = limited ? classify(k, value) : '';
    state.className = 'tile-state ' + cls;
    state.textContent = limited ? STATE_TEXT[cls] : '';
    tile.classList.remove('lv-warning', 'lv-danger');
    if (cls === 'warning' || cls === 'danger') tile.classList.add('lv-' + cls);
    if (tile.dataset.lv !== cls) {
        const first = tile.dataset.lv === undefined;
        tile.dataset.lv = cls;
        if (!first) { tile.classList.remove('flash'); void tile.offsetWidth; tile.classList.add('flash'); }
    }
    const p = Math.max(0, Math.min(100, (value - smin) / (smax - smin) * 100));
    tile.querySelector('.range i').style.left = p + '%';
}

/* الرسم البياني مع خطوط الحدود */
const chart = new Chart(document.getElementById('chart'), {
    type: 'line',
    data: {labels: times, datasets: []},
    options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        plugins: {legend: {display: false}},
        scales: {
            x: {ticks: {color: '#8b9bb1', maxTicksLimit: 8}, grid: {display: false}},
            y: {ticks: {color: '#8b9bb1'}, grid: {color: 'rgba(139,155,177,.12)'}}
        }
    }
});

function drawChart() {
    const L = LIMITS[current];
    const sets = [{label: L.label, data: series[current], borderColor: '#5b9cf5', backgroundColor: 'rgba(91,156,245,.10)',
                   borderWidth: 2, tension: .25, pointRadius: 0, fill: true}];
    [['warning', '#e2a93b'], ['danger', '#e5534b']].forEach(([sev, color]) => L[sev].forEach(v => {
        if (v !== null) sets.push({data: Array(POINTS).fill(v), borderColor: color, borderWidth: 1, borderDash: [6, 4], pointRadius: 0, fill: false});
    }));
    chart.data.datasets = sets;
    chart.options.scales.y.suggestedMin = L.scale[0];
    chart.options.scales.y.suggestedMax = L.scale[1];
    chart.update('none');
    document.getElementById('chartTitle').textContent = `${L.label} (${L.unit})`;
    const limited = ['warning', 'danger'].some(sv => L[sv].some(v => v !== null));
    document.getElementById('chartSource').textContent = limited
        ? `الخطوط المنقطة: حدود التحذير والخطر. المصدر: ${L.source}` : 'لا توجد حدود مرجعية لهذا المؤشر';
}

function selectMetric(k) {
    current = k;
    tilesEl.querySelectorAll('.tile').forEach(t => t.classList.toggle('selected', t.dataset.key === k));
    drawChart();
}

function post(url, body) {
    return fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(body)});
}

/* المحادثة */
let lastChatKey = '', lastSpokenId = null, awaitingReply = 0;

/* ردود المساعد تُنطق في الجهاز الذي أرسل الرسالة فقط */
function maybeSpeak(chat) {
    const assistants = chat.filter(m => m.sender === 'assistant');
    const newest = assistants.length ? assistants[assistants.length - 1] : null;
    if (lastSpokenId === null) { lastSpokenId = newest ? newest.id : 0; return; }  /* أول تحميل: لا نقرأ السجل القديم */
    if (newest && newest.id > lastSpokenId) {
        lastSpokenId = newest.id;
        if (awaitingReply && Date.now() < awaitingReply) { awaitingReply = 0; speakHere(newest.message); }
    }
}

function renderChat(chat) {
    maybeSpeak(chat);
    const key = chat.length + ':' + (chat.length ? chat[chat.length - 1].id : 0);
    if (key === lastChatKey) return;
    lastChatKey = key;
    const box = document.getElementById('messages');
    box.innerHTML = '';
    if (!chat.length) {
        const empty = document.createElement('div');
        empty.className = 'empty'; empty.textContent = 'لا توجد رسائل بعد. اسأل عن حالة المؤشرات أو تحكم بجرس الإنذار.';
        box.appendChild(empty);
    }
    chat.forEach(m => {
        const div = document.createElement('div'), meta = document.createElement('div'), body = document.createElement('div');
        div.className = 'msg ' + m.sender;
        meta.className = 'meta'; meta.textContent = `${SENDERS[m.sender] || m.sender}  ${m.time}`;
        body.textContent = m.message;
        div.append(meta, body);
        box.appendChild(div);
    });
    box.scrollTop = box.scrollHeight;
}

async function sync() {
    try {
        const res = await fetch('/api/data');
        if (res.status === 401) { location.href = '/login'; return; }
        if (!res.ok) return;
        const d = await res.json(), t = d.telemetry, stamp = new Date().toLocaleTimeString(LOCALE);
        if (d.limits_version !== limitsVersion) { location.reload(); return; }
        times.shift(); times.push(stamp);
        KEYS.forEach(k => { series[k].shift(); series[k].push(t[k]); updateTile(k, t[k]); });
        drawChart();

        document.getElementById('strip').className = 'strip ' + (d.level === 'unconfigured' ? 'unset' : d.level);
        document.getElementById('setupLink').hidden = d.level !== 'unconfigured';
        document.getElementById('stripTitle').textContent = TITLES[d.level];
        document.getElementById('stripReason').textContent = d.reason;
        const hw = document.getElementById('hwPill');
        hw.textContent = d.hardware ? 'العتاد: متصل' : 'العتاد: غير متصل (وضع المحاكاة)';
        hw.classList.toggle('on', d.hardware);
        document.getElementById('alarmOn').classList.toggle('active', !!d.buzzer);
        document.getElementById('alarmOff').classList.toggle('active', !d.buzzer);
        renderChat(d.chat);
    } catch (e) { console.error(e); }
}

function showError(text) { document.getElementById('formError').textContent = text || ''; }

async function sendText(text) {
    showError('');
    unlockVoice();
    awaitingReply = Date.now() + 60000;
    const res = await post('/api/send', {prompt: text});
    if (!res.ok) { awaitingReply = 0; const e = await res.json().catch(() => ({})); showError(e.message || e.error || 'تعذر إرسال الرسالة.'); }
    sync();
}
function send(ev) {
    ev.preventDefault();
    const input = document.getElementById('input'), text = input.value.trim();
    if (text) { input.value = ''; sendText(text); }
    return false;
}
async function setBuzzer(state) { await post('/api/buzzer', {state: state}); sync(); }

PROMPTS.forEach(p => {
    const c = document.createElement('button');
    c.type = 'button'; c.className = 'chip'; c.textContent = p; c.onclick = () => sendText(p);
    document.getElementById('chips').appendChild(c);
});

/* الصوت على هذا الجهاز */
const voiceToggle = document.getElementById('voiceToggle');
let voiceOn = localStorage.getItem('voiceOn') !== '0';
voiceToggle.checked = voiceOn;
voiceToggle.onchange = () => {
    voiceOn = voiceToggle.checked;
    localStorage.setItem('voiceOn', voiceOn ? '1' : '0');
    if (!voiceOn && 'speechSynthesis' in window) speechSynthesis.cancel();
};
function unlockVoice() {
    if (!voiceOn || !('speechSynthesis' in window)) return;
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0;
    speechSynthesis.speak(u);
}
function speakHere(text) {
    if (!voiceOn || !('speechSynthesis' in window) || !text) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = /[\u0600-\u06FF]/.test(text) ? 'ar-SA' : 'en-US';
    const prefix = u.lang.slice(0, 2).toLowerCase();
    const voice = speechSynthesis.getVoices().find(v => v.lang.toLowerCase().startsWith(prefix));
    if (voice) u.voice = voice;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
}

/* الإملاء الصوتي: يحتاج اتصالاً آمناً (localhost أو https) */
const MIC_IDLE = 'إملاء صوتي';
let recActive = null;
function micMessage(code) {
    const denied = 'الميكروفون ممنوع. اسمح للموقع باستخدامه من إعدادات المتصفح (رمز القفل بجانب العنوان).';
    const m = {
        'not-allowed': denied,
        'service-not-allowed': denied,
        'no-speech': 'لم يتم التقاط صوت. حاول مرة أخرى.',
        'audio-capture': 'لا يوجد ميكروفون متاح في هذا الجهاز.',
        'network': 'الإملاء الصوتي يحتاج اتصالاً بالإنترنت.',
        'language-not-supported': 'لغة الإملاء غير مدعومة في هذا المتصفح.'
    };
    return m[code] || ('تعذر الإملاء الصوتي: ' + code);
}
function dictate() {
    const btn = document.getElementById('micBtn');
    if (recActive) { recActive.stop(); return; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { showError('المتصفح لا يدعم الإملاء الصوتي. استخدم Chrome أو Edge.'); return; }
    if (!window.isSecureContext) {
        showError('الإملاء الصوتي يحتاج اتصالاً آمناً. على الحاسوب افتح http://localhost:5000 ومن الجوال افتح رابط https الظاهر في نافذة تشغيل البرنامج.');
        return;
    }
    unlockVoice();
    showError('');
    const rec = new SR();
    let heard = false, failed = false, timer = null;
    recActive = rec;
    rec.lang = LOCALE;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    const finish = () => { clearTimeout(timer); recActive = null; btn.textContent = MIC_IDLE; };
    rec.onresult = e => { heard = true; sendText(e.results[0][0].transcript); };
    rec.onerror = e => { failed = true; showError(micMessage(e.error)); finish(); };
    rec.onspeechend = () => rec.stop();
    rec.onend = () => { if (!heard && !failed) showError('لم يتم التقاط صوت. حاول مرة أخرى.'); finish(); };
    btn.textContent = 'جارٍ الاستماع';
    timer = setTimeout(() => rec.abort(), 12000);
    try { rec.start(); } catch (e) { failed = true; showError(micMessage(e.name)); finish(); }
}

drawChart();
sync();
setInterval(sync, 2000);
</script>
{% endblock %}
"""

HISTORY_TEMPLATE = r"""{% extends "base" %}
{% block title %}السجل والتقارير - AstroHab{% endblock %}
{% block head %}__CHART_JS__{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel">
        <div class="panel-head"><h2>تطور المؤشر</h2></div>
        <div class="toolbar">
            <select id="metric" aria-label="المؤشر" onchange="draw()"></select>
            <a class="btn" href="/export.csv">تصدير CSV</a>
            <button class="btn" type="button" onclick="window.print()">طباعة التقرير</button>
        </div>
        <div class="chart-box"><canvas id="chart"></canvas></div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>التنبيهات</h2></div>
        <div class="table-wrap"><table>
            <thead><tr><th>الوقت</th><th>المستوى</th><th>السبب</th></tr></thead>
            <tbody id="alertRows"></tbody>
        </table></div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>آخر القراءات</h2><span class="muted">آخر 50 قراءة</span></div>
        <div class="table-wrap"><table>
            <thead id="head"></thead>
            <tbody id="rows"></tbody>
        </table></div>
    </section>
</main>

<script>
const LIMITS = {{ limits|tojson }};
const KEYS = Object.keys(LIMITS);
const LEVEL = {normal: 'مستقر', warning: 'تحذير', danger: 'خطر', unconfigured: 'بدون حدود'};
let rows = [];

const select = document.getElementById('metric');
KEYS.forEach(k => select.add(new Option(`${LIMITS[k].label} (${LIMITS[k].unit})`, k)));

const chart = new Chart(document.getElementById('chart'), {
    type: 'line', data: {labels: [], datasets: []},
    options: {responsive: true, maintainAspectRatio: false, animation: false, plugins: {legend: {display: false}},
        scales: {x: {ticks: {color: '#8b9bb1', maxTicksLimit: 8}, grid: {display: false}},
                 y: {ticks: {color: '#8b9bb1'}, grid: {color: 'rgba(139,155,177,.12)'}}}}
});

function draw() {
    const k = select.value, L = LIMITS[k];
    const sets = [{data: rows.map(r => r[k]), borderColor: '#5b9cf5', backgroundColor: 'rgba(91,156,245,.10)',
                   borderWidth: 2, tension: .25, pointRadius: 0, fill: true}];
    [['warning', '#e2a93b'], ['danger', '#e5534b']].forEach(([sev, color]) => L[sev].forEach(v => {
        if (v !== null) sets.push({data: rows.map(() => v), borderColor: color, borderWidth: 1, borderDash: [6, 4], pointRadius: 0, fill: false});
    }));
    chart.data.labels = rows.map(r => r.ts.slice(11));
    chart.data.datasets = sets;
    chart.options.scales.y.suggestedMin = L.scale[0];
    chart.options.scales.y.suggestedMax = L.scale[1];
    chart.update('none');
}

function cell(text, cls) { const td = document.createElement('td'); td.textContent = text; if (cls) td.className = cls; return td; }
function headCell(text) { const th = document.createElement('th'); th.textContent = text; return th; }

const head = document.getElementById('head'), hr = document.createElement('tr');
hr.append(headCell('الوقت'), ...KEYS.map(k => headCell(LIMITS[k].label)), headCell('الحالة'));
head.appendChild(hr);

async function load() {
    const res = await fetch('/api/history?limit=300');
    if (!res.ok) return;
    const data = await res.json();
    rows = data.rows;
    draw();

    const body = document.getElementById('rows');
    body.innerHTML = '';
    rows.slice(-50).reverse().forEach(r => {
        const tr = document.createElement('tr');
        tr.append(cell(r.ts), ...KEYS.map(k => cell(r[k], 'num')), cell(LEVEL[r.level] || r.level, 'lvl-' + r.level));
        body.appendChild(tr);
    });
    if (!rows.length) {
        const tr = document.createElement('tr'), td = cell('لا توجد قراءات بعد. افتح لوحة المراقبة لبدء التسجيل.', 'empty');
        td.colSpan = KEYS.length + 2; tr.appendChild(td); body.appendChild(tr);
    }

    const ab = document.getElementById('alertRows');
    ab.innerHTML = '';
    if (!data.alerts.length) {
        const tr = document.createElement('tr'), td = cell('لا توجد تنبيهات مسجلة.', 'empty');
        td.colSpan = 3; tr.appendChild(td); ab.appendChild(tr);
    }
    data.alerts.forEach(a => {
        const tr = document.createElement('tr');
        tr.append(cell(a.ts), cell(LEVEL[a.level] || a.level, 'lvl-' + a.level), cell(a.reason));
        ab.appendChild(tr);
    });
}
load();
setInterval(load, 15000);
</script>
{% endblock %}
"""

NASA_TEMPLATE = r"""{% extends "base" %}
{% block title %}بيانات ناسا - AstroHab{% endblock %}
{% block head %}__CHART_JS__{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel">
        <div class="panel-head"><h2>الحدود المرجعية المعتمدة</h2><span class="muted">تُستخدم لإعلان التحذير والخطر</span></div>
        <div class="table-wrap"><table>
            <thead><tr><th>المؤشر</th><th>تحذير أدنى</th><th>تحذير أعلى</th><th>خطر أدنى</th><th>خطر أعلى</th>
                <th>الوحدة</th><th>المصدر</th><th>قراءة من ناسا</th>{% if role == 'admin' %}<th></th>{% endif %}</tr></thead>
            <tbody>
            {% for key, s in limits_all.items() %}
                <tr><td>{{ s.label }}</td>
                    {% for v in [s.warning[0], s.warning[1], s.danger[0], s.danger[1]] %}<td class="num">{{ v if v is not none else '-' }}</td>{% endfor %}
                    <td>{{ s.unit }}</td><td>{{ s.source if s.configured else 'غير محدد' }}</td><td>{{ 'نعم' if s.replay else 'لا' }}</td>
                    {% if role == 'admin' %}<td>{% if s.configured %}<button class="btn" type="button" onclick="clearLimit('{{ key }}')">مسح</button>{% endif %}</td>{% endif %}
                </tr>
            {% endfor %}
            </tbody>
        </table></div>
        {% if limits_all.values()|selectattr('configured')|list|length == 0 %}
        <p class="empty mt">لا توجد حدود بعد، ولن يعلن النظام خطراً حتى تُحدد. {% if role != 'admin' %}اطلب من مدير النظام تحديدها.{% endif %}</p>
        {% endif %}
    </section>

{% if role == 'admin' %}
    <section class="panel">
        <div class="panel-head"><h2>استيراد حدود صريحة</h2></div>
        <p class="empty">إذا كانت بيانات ناسا تتضمن حدوداً جاهزة، ضعها في <code>data/nasa/limits.csv</code> بالأعمدة
        <code>metric,warning_low,warning_high,danger_low,danger_high,unit,source</code>
        وأسماء المؤشرات المقبولة: <code>{{ limits_all.keys()|join(', ') }}</code>. اترك الخانة فارغة إن لم يوجد حد في ذلك الاتجاه.</p>
        <div class="toolbar mt"><button class="btn" type="button" onclick="importLimits()">استيراد limits.csv</button><span class="muted" id="importMsg"></span></div>
    </section>
{% endif %}

{% if datasets %}
    <section class="panel">
        <div class="panel-head"><h2>استعراض البيانات</h2></div>
        <div class="toolbar">
            <select id="file" aria-label="الملف" onchange="fillColumns()">
                {% for d in datasets %}<option value="{{ d.file }}">{{ d.file }} ({{ d.rows }} صف)</option>{% endfor %}
            </select>
            <select id="column" aria-label="العمود" onchange="plot()"></select>
        </div>
        <div class="chart-box"><canvas id="chart"></canvas></div>
    </section>
  {% if role == 'admin' %}
    <section class="panel">
        <div class="panel-head"><h2>اشتقاق الحدود من العمود المحدد</h2></div>
        <p class="empty">يُحسب الحد من توزيع قيم العمود: مثلاً تحذير عند النسبة المئوية 95 وخطر عند 99 للقيم العالية.
        اختر النسب بما يناسب طبيعة البيانات، وعاين النتيجة على الرسم قبل الاعتماد.</p>
        <div class="form-grid">
            <div class="field"><label for="metric">المؤشر</label>
                <select id="metric">{% for key, s in limits_all.items() %}<option value="{{ key }}">{{ s.label }}</option>{% endfor %}</select></div>
            <div class="field"><label for="direction">الاتجاه الخطر</label>
                <select id="direction"><option value="high">القيم العالية</option><option value="low">القيم المنخفضة</option><option value="both">الاتجاهان</option></select></div>
            <div class="field"><label for="warn">نسبة التحذير المئوية</label><input type="number" id="warn" value="95" min="50" max="99.9" step="0.1"></div>
            <div class="field"><label for="danger">نسبة الخطر المئوية</label><input type="number" id="danger" value="99" min="50.1" max="100" step="0.1"></div>
            <div class="field"><label for="unit">الوحدة (اختياري)</label><input type="text" id="unit" maxlength="16"></div>
        </div>
        <label class="check"><input type="checkbox" id="replay" checked> استخدام هذا العمود كمصدر لقراءات هذا المؤشر</label>
        <div class="toolbar">
            <button class="btn" type="button" onclick="preview()">معاينة</button>
            <button class="btn btn-primary" type="button" onclick="saveLimits()">اعتماد الحدود</button>
        </div>
        <div class="result" id="result" role="status"></div>
    </section>
  {% endif %}
{% else %}
    <section class="panel">
        <div class="panel-head"><h2>بيانات ناسا المفتوحة</h2></div>
        <p class="empty">لا توجد ملفات بيانات بعد. ضع ملفات <code>CSV</code> داخل المجلد <code>data/nasa</code> ثم حدّث الصفحة،
        وستظهر أعمدتها الرقمية مع رسم بياني، ويمكن اشتقاق الحدود منها.</p>
    </section>
{% endif %}
</main>

<script>
const csrf = document.querySelector('meta[name="csrf-token"]').content;
async function call(url, body) {
    const res = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(body || {})});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'تعذر تنفيذ الطلب.');
    return data;
}
async function clearLimit(metric) {
    if (!confirm('مسح الحد المرجعي لهذا المؤشر؟')) return;
    try { await call('/api/reference/clear', {metric: metric}); location.reload(); } catch (e) { alert(e.message); }
}
async function importLimits() {
    const msg = document.getElementById('importMsg');
    try { const r = await call('/api/reference/import'); msg.textContent = `تم استيراد ${r.imported} مؤشر.`; setTimeout(() => location.reload(), 700); }
    catch (e) { msg.textContent = e.message; }
}
</script>

{% if datasets %}
<script>
const datasets = {{ datasets|tojson }};
const val = id => document.getElementById(id).value;
const chart = new Chart(document.getElementById('chart'), {
    type: 'line', data: {labels: [], datasets: [{data: [], borderColor: '#5b9cf5', backgroundColor: 'rgba(91,156,245,.10)',
              borderWidth: 2, tension: .25, pointRadius: 0, fill: true}]},
    options: {responsive: true, maintainAspectRatio: false, animation: false, plugins: {legend: {display: false}},
        scales: {x: {ticks: {color: '#8b9bb1', maxTicksLimit: 8}, grid: {display: false}},
                 y: {ticks: {color: '#8b9bb1'}, grid: {color: 'rgba(139,155,177,.12)'}}}}
});
function fillColumns() {
    const cols = datasets.find(d => d.file === val('file')).columns, sel = document.getElementById('column');
    sel.innerHTML = '';
    cols.forEach(c => sel.add(new Option(c, c)));
    plot();
}
async function plot() {
    const res = await fetch('/api/nasa/series?file=' + encodeURIComponent(val('file')) + '&column=' + encodeURIComponent(val('column')));
    const s = res.ok ? await res.json() : {labels: [], values: []};
    chart.data.labels = s.labels;
    chart.data.datasets.length = 1;
    chart.data.datasets[0].data = s.values;
    chart.update('none');
}
function payload() {
    const el = id => document.getElementById(id);
    return {metric: val('metric'), file: val('file'), column: val('column'), direction: val('direction'),
            warn_pct: Number(val('warn')), danger_pct: Number(val('danger')), unit: val('unit').trim(), replay: el('replay').checked};
}
const fmt = v => v === null ? '-' : v;
async function preview() {
    const out = document.getElementById('result');
    try {
        const r = await call('/api/reference/preview', payload());
        chart.data.datasets.length = 1;
        [['warning', '#e2a93b'], ['danger', '#e5534b']].forEach(([sev, color]) => r[sev].forEach(v => {
            if (v !== null) chart.data.datasets.push({data: chart.data.labels.map(() => v), borderColor: color, borderWidth: 1, borderDash: [6, 4], pointRadius: 0, fill: false});
        }));
        chart.update('none');
        out.textContent = `تحذير: أدنى ${fmt(r.warning[0])} / أعلى ${fmt(r.warning[1])}. خطر: أدنى ${fmt(r.danger[0])} / أعلى ${fmt(r.danger[1])}. عدد القراءات: ${r.count}.`;
    } catch (e) { out.textContent = e.message; }
}
async function saveLimits() {
    const out = document.getElementById('result');
    try { await call('/api/reference/save', payload()); out.textContent = 'تم اعتماد الحدود.'; setTimeout(() => location.reload(), 700); }
    catch (e) { out.textContent = e.message; }
}
fillColumns();
</script>
{% endif %}
{% endblock %}
"""

ADMIN_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ adm.users }} - AstroHab{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel">
        <div class="panel-head"><h2>{{ adm.users }}</h2></div>
        <p class="muted">{{ adm.doctor_note }}</p>
        <div class="table-wrap"><table>
            <thead><tr><th>{{ adm.col_name }}</th><th>{{ adm.col_role }}</th><th>{{ adm.col_created }}</th><th>{{ adm.col_readings }}</th><th>{{ adm.col_change }}</th></tr></thead>
            <tbody>
            {% for u in users %}
                <tr><td>{{ u.username }}</td><td>{{ u.role_label }}</td>
                    <td>{{ u.created_at }}</td><td class="num">{{ u.readings }}</td>
                    <td>{% if u.role != 'admin' %}<select data-user="{{ u.username }}" aria-label="{{ adm.col_change }}">{% for value, label in role_options %}<option value="{{ value }}" {{ 'selected' if value == u.role }}>{{ label }}</option>{% endfor %}</select>
                        <button class="btn role-save" type="button" data-user="{{ u.username }}">{{ adm.save }}</button> <span class="muted role-msg" data-user="{{ u.username }}"></span>{% endif %}</td></tr>
            {% endfor %}
            </tbody>
        </table></div>
    </section>
    <section class="panel">
        <div class="panel-head"><h2>{{ adm.alerts }}</h2><span class="muted">{{ adm.all_users }}</span></div>
        <div class="table-wrap"><table>
            <thead><tr><th>{{ adm.col_time }}</th><th>{{ adm.col_user }}</th><th>{{ adm.col_level }}</th><th>{{ adm.col_reason }}</th></tr></thead>
            <tbody>
            {% for a in alerts %}
                <tr><td>{{ a.ts }}</td><td>{{ a.username }}</td>
                    <td class="lvl-{{ a.level }}">{{ adm.danger if a.level == 'danger' else adm.warning }}</td><td>{{ a.reason }}</td></tr>
            {% else %}
                <tr><td colspan="4" class="empty">{{ adm.no_alerts }}</td></tr>
            {% endfor %}
            </tbody>
        </table></div>
    </section>
</main>
<script>
const MSG = {saved: {{ adm.saved|tojson }}, failed: {{ adm.failed|tojson }}};
const csrf = document.querySelector('meta[name="csrf-token"]').content;
document.querySelectorAll('.role-save').forEach(btn => btn.addEventListener('click', async () => {
    const user = btn.dataset.user;
    const select = document.querySelector('select[data-user="' + user + '"]');
    const msg = document.querySelector('.role-msg[data-user="' + user + '"]');
    const res = await fetch('/api/admin/role', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
                                                body: JSON.stringify({username: user, role: select.value})});
    msg.textContent = res.ok ? MSG.saved : MSG.failed;
    if (res.ok) {
        btn.closest('tr').children[1].textContent = select.options[select.selectedIndex].text;  // update the role cell at once
        setTimeout(() => { msg.textContent = ''; }, 2500);
    }
}));
</script>
{% endblock %}
"""

EXERCISE_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ ui.ex_title }} - AstroHab{% endblock %}
{% block head %}<style>
.ex-grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; }
@media (max-width: 960px) { .ex-grid { grid-template-columns: 1fr; } }
.bars { display: flex; align-items: flex-end; gap: 6px; height: 140px; direction: ltr; }
.bar { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; font-size: 11px; color: var(--muted); }
.bar i { display: block; width: 100%; max-width: 34px; background: var(--accent); border-radius: 4px 4px 0 0; min-height: 2px; opacity: .9; }
.bar.zero i { background: var(--line); }
.bar b { color: var(--text); font-size: 12px; }
.spark { width: 100%; height: 90px; display: block; }
.ex-row { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid var(--line); font-size: 14px; flex-wrap: wrap; }
.ex-form { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.ex-form input, .ex-form select { width: 150px; }
.ex-form input.note { width: 100%; max-width: 360px; }
.pend { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; display: grid; gap: 8px; }
.big { font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; }
.ex-lbl { font-size: 13px; }
.ex-picks { display: grid; gap: 8px; }
.ex-group { border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px 8px; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.ex-group legend { font-size: 12px; color: var(--muted); padding: 0 4px; }
.ex-pick { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; direction: ltr; cursor: pointer; }
.ex-pick input { width: auto; }
</style>{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel">
        <div class="panel-head"><h2>{{ ui.ex_title }}</h2></div>
        <p class="muted">{{ ui.ex_intro }}</p>
        <p><strong>{{ ui.ex_week }}:</strong> <span id="weekLine">-</span></p>
        <p class="muted">{{ ui.ex_risk }}: <a href="{{ fitness_risk.url }}" target="_blank" rel="noopener noreferrer" dir="ltr">{{ fitness_risk.name }}</a></p>
        <div id="streak"></div>
    </section>
    <div class="ex-grid">
        <section class="panel">
            <div class="panel-head"><h2>{{ ui.ex_days }}</h2></div>
            <div class="bars" id="bars"></div>
        </section>
        <section class="panel">
            <div class="panel-head"><h2>{{ ui.ex_bone }}</h2><span class="muted">{{ ui.ex_bone_now }}: <span class="big" id="boneNow">-</span> %</span></div>
            <svg class="spark" id="spark" viewBox="0 0 300 90" preserveAspectRatio="none" aria-hidden="true"></svg>
            <p class="muted" id="boneNote">{{ ui.ex_bone_note }}</p>
        </section>
    </div>
    <div class="ex-grid">
        <section class="panel">
            <div class="panel-head"><h2>{{ ui.ex_log_title }}</h2></div>
            <div id="pending"></div>
            <div class="form-error" id="msg" role="status"></div>
        </section>
        <section class="panel">
            <div class="panel-head"><h2>{{ ui.ex_recent }}</h2></div>
            <div id="recent"></div>
        </section>
    </div>
</main>
<script>
const UI = {{ ui|tojson }};
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const $ = id => document.getElementById(id);
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function drawStreak(box, title, s) {
    box.textContent = '';
    const c = el('div', 'streak' + (s.today ? ' on' : ''));
    const body = el('div');
    body.append(el('div', 'st-t', title),
                el('div', 'st-m', s.today ? UI.st_done : (s.current ? UI.st_keep : UI.st_start)));
    if (s.best > 1) body.append(el('div', 'st-t', UI.st_best.replace('{n}', s.best)));
    const n = el('div', 'st-n', s.current), u = el('div', 'st-t', UI.st_days);
    const num = el('div'); num.append(n, u);
    c.append(num, body); box.append(c);
}
function draw(d) {
    drawStreak($('streak'), UI.st_title_ex, d.streak);
    $('weekLine').textContent = UI.ex_week_line.replace('{s}', d.week.sessions).replace('{d}', d.week.days_active).replace('{m}', d.week.minutes);
    const max = Math.max(1, ...d.days.map(x => x.sessions));
    const bars = $('bars'); bars.textContent = '';
    d.days.forEach(x => {
        const b = el('div', 'bar' + (x.sessions ? '' : ' zero'));
        b.append(el('b', '', x.sessions || ''));
        const i = el('i'); i.style.height = Math.max(2, x.sessions / max * 100) + '%'; i.title = x.date + ': ' + x.sessions;
        b.append(i, el('span', '', x.date.slice(8)));
        bars.append(b);
    });
    $('boneNow').textContent = d.bone.current === null ? '-' : d.bone.current;
    const pts = d.bone.series, svg = $('spark'); svg.textContent = '';
    if (pts.length > 1) {
        const lo = Math.min(...pts.map(x => x.value)), hi = Math.max(...pts.map(x => x.value)), span = (hi - lo) || 1;
        const path = pts.map((x, n) => (n ? 'L' : 'M') + (n / (pts.length - 1) * 300).toFixed(1) + ' ' + (80 - (x.value - lo) / span * 70).toFixed(1)).join(' ');
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        line.setAttribute('d', path); line.setAttribute('fill', 'none'); line.setAttribute('stroke', '#5b9cf5'); line.setAttribute('stroke-width', '2');
        line.setAttribute('vector-effect', 'non-scaling-stroke'); svg.append(line);
    }
    $('boneNote').textContent = UI.ex_bone_note + (d.bone.configured ? '' : ' ' + UI.ex_bone_nolimits);
    const rec = $('recent'); rec.textContent = '';
    if (!d.recent.length) rec.append(el('p', 'muted', UI.ex_none));
    d.recent.forEach(r => {
        const row = el('div', 'ex-row');
        const parts = r.minutes ? [r.minutes + ' ' + UI.ex_min, r.activity, r.note].filter(Boolean) : [UI.ex_no_details];
        row.append(el('span', '', r.ts), el('span', 'muted', UI.ex_kind_button + ' - ' + parts.join(' - ')));
        rec.append(row);
    });
    drawPending(d);
}
let pendingKey = null;
function drawPending(d) {
    const key = d.pending.map(x => x.id).join(',');
    if (key === pendingKey) return;  // do not rebuild the forms while the user is typing
    pendingKey = key;
    const box = $('pending'); box.textContent = '';
    if (!d.pending.length) { box.append(el('p', 'muted', UI.ex_pending_none)); return; }
    d.pending.forEach(p => {
        const f = el('div', 'pend');
        f.append(el('strong', '', UI.ex_session_at.replace('{t}', p.ts)));
        const row = el('div', 'ex-form');
        const mins = el('input'); mins.type = 'number'; mins.min = 1; mins.max = 300; mins.step = 1; mins.inputMode = 'numeric';
        mins.setAttribute('aria-label', UI.ex_minutes); mins.placeholder = UI.ex_minutes;
        const picks = el('div', 'ex-picks'); picks.setAttribute('role', 'group'); picks.setAttribute('aria-label', UI.ex_type);
        const boxes = [];
        d.groups.forEach(g => {
            const grp = el('fieldset', 'ex-group'); grp.append(el('legend', '', g.label));
            g.items.forEach(it => {
                const lab = el('label', 'ex-pick'); const cb = el('input'); cb.type = 'checkbox'; cb.value = it.key;
                boxes.push(cb); lab.append(cb, el('span', '', it.label)); grp.append(lab);
            });
            picks.append(grp);
        });
        const note = el('input', 'note'); note.type = 'text'; note.maxLength = d.note_max; note.placeholder = UI.ex_note;
        const save = el('button', 'btn btn-primary', UI.ex_save); save.type = 'button';
        row.append(mins, save); f.append(row, el('strong', 'ex-lbl', UI.ex_type), picks, note);
        save.addEventListener('click', async () => {
            const res = await fetch('/api/exercise', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
                                                      body: JSON.stringify({id: p.id, minutes: mins.value, activities: boxes.filter(b => b.checked).map(b => b.value), note: note.value})});
            const data = await res.json();
            $('msg').style.color = res.ok ? 'var(--ok)' : '';
            if (!res.ok) { $('msg').textContent = data.error || ''; return; }
            $('msg').textContent = UI.ex_saved; pendingKey = null; draw(data);
        });
        box.append(f);
    });
}
async function load() { const r = await fetch('/api/exercise'); if (r.ok) draw(await r.json()); }
load(); setInterval(load, 5000);
</script>
{% endblock %}
"""

LEVEL_CSS = r"""
.lv-normal { --c: var(--ok); } .lv-warning { --c: var(--warn); } .lv-danger { --c: var(--crit); }
.lv-unconfigured, .lv-nodata { --c: var(--muted); }
.badge { display: inline-block; font-size: 12px; color: var(--c); border: 1px solid var(--c); border-radius: 12px; padding: 1px 10px; white-space: nowrap; }
.tier { --c: var(--muted); background: var(--panel); border: 1px solid var(--line); border-inline-start: 4px solid var(--c);
        border-radius: 10px; padding: 14px 18px; display: grid; gap: 4px; }
.tier.t0 { --c: var(--ok); } .tier.t1 { --c: var(--warn); } .tier.t2 { --c: var(--crit); }
.tier-label { font-weight: 600; color: var(--c); }
.demo-ctl { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 14px; }
.mtrend { font-size: 13px; color: var(--warn); }
.due { border: 1px dashed var(--warn); border-radius: 10px; padding: 10px 16px; color: var(--text); }
.disclaimer { font-size: 13px; color: var(--muted); }
"""

BODY_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ ui.body_title }} - AstroHab{% endblock %}
{% block head %}<style>
""" + LEVEL_CSS + r"""
.body-grid { display: grid; grid-template-columns: minmax(260px, 400px) minmax(0, 1fr); gap: 16px; align-items: start; }
.figure svg { width: 100%; height: auto; max-height: 76vh; display: block; margin: 0 auto; }
.region { cursor: pointer; outline: none; transition: opacity .2s; }
.region .shape { fill: var(--c); stroke: var(--c); fill-opacity: .38; stroke-width: 2; transition: fill-opacity .2s; }
.region:hover .shape, .region:focus-visible .shape { fill-opacity: .62; }
.region.selected .shape { stroke: var(--text); stroke-width: 3; fill-opacity: .7; }
.region:focus-visible { filter: drop-shadow(0 0 4px var(--accent)); }
.region[data-region="body"] { opacity: .35; }
.region[data-region="body"] .shape { fill-opacity: 1; stroke: none; }
.region[data-region="body"]:hover, .region[data-region="body"]:focus-visible { opacity: .5; }
.region[data-region="body"].selected { opacity: .62; }
.region.lv-nodata .shape { stroke-dasharray: 5 4; fill-opacity: .15; }
.region.lv-danger:not([data-region="body"]) .shape { animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { fill-opacity: .12; } }
@media (prefers-reduced-motion: reduce) { .region.lv-danger .shape { animation: none; } }
.region.dim { opacity: .18; }
.outline { fill: none; stroke: #3a4c68; stroke-width: 2; pointer-events: none; }
.chip.lv-normal, .chip.lv-warning, .chip.lv-danger { border-color: var(--c); }
.chip.active { color: var(--text); background: var(--panel-2); border-color: var(--accent); }
.mcard { border: 1px solid var(--line); border-inline-start: 4px solid var(--c); border-radius: 10px; background: var(--panel-2); padding: 12px 14px; margin-top: 12px; }
.mhead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.mname { font-weight: 600; }
.mval .v { font-size: 26px; font-weight: 600; font-variant-numeric: tabular-nums; }
.mval .u { font-size: 13px; color: var(--muted); margin-inline-start: 4px; }
.mrow { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 6px 0; font-size: 13px; }
details { border-top: 1px solid var(--line); padding: 6px 0; }
details summary { cursor: pointer; font-size: 14px; color: var(--text); }
details p { color: var(--muted); font-size: 14px; margin: 6px 0 4px; }
details.esc summary { color: var(--warn); }
.mlinks { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
.hazard-card { border: 1px solid var(--accent); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; background: rgba(91,156,245,.08); }
@media (max-width: 960px) { .body-grid { grid-template-columns: 1fr; } }
</style>{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <div id="tier" class="tier" role="status" aria-live="polite">
        <span class="muted">{{ ui.tier_title }}</span>
        <span class="tier-label" id="tierLabel"></span>
        <span id="tierText"></span>
    </div>
    <div id="due" class="due" hidden></div>
    <div class="demo-ctl" id="demoCtl"><button class="btn" type="button" id="demoBtn">{{ ui.demo_start }}</button>
        <span class="muted" id="demoMsg">{{ ui.demo_hint }}</span></div>

    <section class="body-grid">
        <div class="panel figure">
            <div class="panel-head"><h2>{{ ui.body_title }}</h2></div>
            <p class="muted" style="margin-bottom: 8px">{{ ui.body_intro }}</p>
            <svg viewBox="0 0 320 660" role="group" aria-label="{{ ui.body_title }}">
                <defs>
                    <g id="sil">
                        <circle cx="160" cy="62" r="38"/>
                        <rect x="146" y="96" width="28" height="26" rx="10"/>
                        <path d="M118 124 Q160 110 202 124 Q234 130 238 162 L228 302 Q224 340 216 382 L104 382 Q96 340 92 302 L82 162 Q86 130 118 124 Z"/>
                        <rect x="40" y="140" width="32" height="214" rx="16" transform="rotate(7 56 247)"/>
                        <rect x="248" y="140" width="32" height="214" rx="16" transform="rotate(-7 264 247)"/>
                        <rect x="104" y="372" width="52" height="250" rx="26"/>
                        <rect x="164" y="372" width="52" height="250" rx="26"/>
                    </g>
                </defs>
                <g class="region lv-nodata" data-region="body" tabindex="0" role="button"><title></title>
                    <use href="#sil" class="shape"/>
                </g>
                <use href="#sil" class="outline"/>
                <g class="region lv-nodata" data-region="bones" tabindex="0" role="button"><title></title>
                    <rect class="shape" x="153" y="128" width="14" height="236" rx="7"/>
                    <ellipse class="shape" cx="160" cy="372" rx="46" ry="15"/>
                    <rect class="shape" x="123" y="392" width="14" height="200" rx="7"/>
                    <rect class="shape" x="183" y="392" width="14" height="200" rx="7"/>
                </g>
                <g class="region lv-nodata" data-region="lungs" tabindex="0" role="button"><title></title>
                    <ellipse class="shape" cx="124" cy="190" rx="24" ry="42"/>
                    <ellipse class="shape" cx="196" cy="190" rx="24" ry="42"/>
                </g>
                <g class="region lv-nodata" data-region="abdomen" tabindex="0" role="button"><title></title>
                    <ellipse class="shape" cx="160" cy="284" rx="42" ry="32"/>
                </g>
                <g class="region lv-nodata" data-region="heart" tabindex="0" role="button"><title></title>
                    <path class="shape" d="M168 228 C136 206 146 176 168 192 C190 176 200 206 168 228 Z"/>
                </g>
                <g class="region lv-nodata" data-region="head" tabindex="0" role="button"><title></title>
                    <ellipse class="shape" cx="160" cy="58" rx="27" ry="31"/>
                </g>
            </svg>
            <p class="muted" style="font-size: 13px; margin-top: 8px">{{ ui.legend }}</p>
            <div class="chips" id="regionChips" role="group" aria-label="{{ ui.regions_title }}"></div>
        </div>

        <aside class="panel" id="panel" aria-live="polite">
            <div id="hazardCard" class="hazard-card" hidden></div>
            <div class="panel-head"><h2 id="pTitle"></h2><span class="badge" id="pBadge"></span></div>
            <p class="muted" id="pFunction"></p>
            <div id="pMetrics"></div>
        </aside>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.hazards_title }}</h2><span class="muted">{{ ui.hazards_hint }}</span></div>
        <div class="chips" id="hazardChips"></div>
    </section>
    <p class="disclaimer">{{ ui.disclaimer }}</p>
</main>

<script>
const UI = {{ ui|tojson }}, INFO = {{ knowledge|tojson }}, REGIONS = {{ regions|tojson }}, HAZARDS = {{ hazards|tojson }};
const RANK = {danger: 3, warning: 2, normal: 1, unconfigured: 0, nodata: -1};
const SECTIONS = [['what', 's_what'], ['space', 's_space'], ['action', 's_action'], ['escalate', 's_escalate']];
const $ = id => document.getElementById(id);
const OPEN = new Set();
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let STATE = null, selected = null, hazard = null, refs = {};

function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
}
function ago(m) {
    if (m.age_minutes === null) return UI.never;
    const a = m.age_minutes;
    if (a < 1) return UI.ago_now;
    if (a < 60) return UI.ago_min.replace('{n}', a);
    if (a < 2880) return UI.ago_hour.replace('{n}', Math.floor(a / 60));
    return UI.ago_day.replace('{n}', Math.floor(a / 1440));
}
function regionLevel(r) {
    let best = 'nodata';
    r.metrics.forEach(k => { const m = STATE.metrics[k]; if (m && RANK[m.level] > RANK[best]) best = m.level; });
    return best;
}
function hazardObj() { return HAZARDS.find(h => h.id === hazard) || null; }
function isDim(id) { const h = hazardObj(); return !!(h && h.regions.length && !h.regions.includes(id)); }

function selectRegion(id) { if (!STATE) return; selected = id; hazard = null; buildPanel(); paint(); }
function selectHazard(id) {
    if (!STATE) return;
    hazard = hazard === id ? null : id;
    const h = hazardObj();
    if (h && h.regions.length) selected = h.regions[0];
    buildPanel(); paint();
}

/* لوحة المعلومات: تُبنى مرة عند تغيير الاختيار، ثم تُحدَّث قيمها فقط (حتى لا يضيع التركيز ولا تنغلق الأقسام) */
function buildPanel() {
    const r = REGIONS.find(x => x.id === selected);
    refs = {};
    const box = $('pMetrics'); box.textContent = '';
    const hc = $('hazardCard'), h = hazardObj();
    hc.hidden = !h;
    hc.textContent = '';
    if (h) {
        hc.append(el('strong', '', h.name), el('div', 'muted', h.regions.length ? h.text : h.text + ' ' + UI.hazard_none));
    }
    if (!r) { $('pTitle').textContent = ''; $('pFunction').textContent = ''; return; }
    $('pTitle').textContent = r.name;
    $('pFunction').textContent = r.function;
    const linked = HAZARDS.filter(x => x.regions.includes(r.id)).map(x => x.name);
    if (linked.length) box.append(el('div', 'muted', UI.linked_hazards + ': ' + linked.join(' · ')));
    r.metrics.forEach(k => {
        const m = STATE.metrics[k], info = INFO[k] || {};
        const card = el('div', 'mcard');
        const head = el('div', 'mhead'), name = el('div'), val = el('div', 'mval');
        name.append(el('div', 'mname', m.label), el('div', 'muted', m.kind === 'live' ? UI.kind_live : UI.kind_manual));
        const v = el('span', 'v'), u = el('span', 'u', m.unit);
        val.append(v, u);
        head.append(name, val);
        const row = el('div', 'mrow'), badge = el('span', 'badge'), when = el('span', 'muted');
        row.append(badge, when);
        const src = el('div', 'muted'), trend = el('div', 'mtrend');
        src.style.fontSize = '13px';
        card.append(head, row, src, trend);
        SECTIONS.forEach(([part, label]) => {
            if (!info[part]) return;
            const d = el('details', part === 'escalate' ? 'esc' : ''), s = el('summary', '', UI[label]);
            const id = k + ':' + part;
            d.open = OPEN.has(id);
            d.addEventListener('toggle', () => { d.open ? OPEN.add(id) : OPEN.delete(id); });
            d.append(s, el('p', '', info[part]));
            card.append(d);
        });
        if (info.risk) {
            const rk = el('div', 'muted'); rk.style.fontSize = '13px'; rk.append(UI.risk_label + ': ');
            const ra = el('a', '', info.risk.name); ra.href = info.risk.url; ra.target = '_blank'; ra.rel = 'noopener noreferrer'; ra.style.direction = 'ltr'; ra.style.unicodeBidi = 'isolate';
            rk.append(ra); card.append(rk);
        }
        const links = el('div', 'mlinks'), a = el('a', 'btn', m.kind === 'manual' ? UI.record_now : UI.go_dashboard);
        a.href = m.kind === 'manual' ? '/checkin' : '/';
        links.append(a);
        card.append(links);
        box.append(card);
        refs[k] = {card, v, badge, when, src, trend};
    });
    updatePanel();
}
function updatePanel() {
    const r = REGIONS.find(x => x.id === selected);
    if (!r) return;
    const lv = regionLevel(r), pb = $('pBadge');
    pb.className = 'badge lv-' + lv; pb.textContent = UI['lv_' + lv];
    Object.keys(refs).forEach(k => {
        const m = STATE.metrics[k], f = refs[k];
        f.card.className = 'mcard lv-' + m.level;
        f.v.textContent = m.value === null ? UI.no_data : m.value;
        f.badge.className = 'badge lv-' + m.level; f.badge.textContent = UI['lv_' + m.level];
        f.when.textContent = m.kind === 'manual' ? UI.measured + ': ' + ago(m) : '';
        f.src.textContent = m.configured ? UI.source + ': ' + m.source : UI.no_limits;
        f.trend.textContent = m.trend || '';
    });
}

function paint() {
    REGIONS.forEach(r => {
        const g = document.querySelector('[data-region="' + r.id + '"]'), lv = regionLevel(r);
        g.setAttribute('class', 'region lv-' + lv + (selected === r.id ? ' selected' : '') + (isDim(r.id) ? ' dim' : ''));
        g.setAttribute('aria-label', r.name + ': ' + UI['lv_' + lv]);
        g.setAttribute('aria-pressed', selected === r.id ? 'true' : 'false');
        g.querySelector('title').textContent = r.name + ' - ' + UI['lv_' + lv];
        const chip = refs_chips[r.id];
        chip.className = 'chip lv-' + lv + (selected === r.id ? ' active' : '');
        chip.setAttribute('aria-pressed', selected === r.id ? 'true' : 'false');
    });
    HAZARDS.forEach(h => {
        const chip = refs_hazards[h.id];
        chip.className = 'chip' + (hazard === h.id ? ' active' : '');
        chip.setAttribute('aria-pressed', hazard === h.id ? 'true' : 'false');
    });
    const esc = STATE.escalation, tier = $('tier'), t = esc.tier;
    tier.className = 'tier ' + (t === null ? 'tnone' : 't' + t);
    $('tierLabel').textContent = UI['tier_label_' + (t === null ? 'none' : t)];
    $('tierText').textContent = esc.text;
    const due = $('due');
    due.hidden = !STATE.due.length;
    if (STATE.due.length) {
        due.textContent = '';
        const a = el('a', 'btn', UI.record_now);
        a.href = '/checkin'; a.style.marginInlineStart = '10px';
        due.append(el('strong', '', UI.due_title + ': '), document.createTextNode(UI.due_text + ' ' + STATE.due.map(k => STATE.metrics[k].label).join(', ')), a);
    }
    $('demoCtl').hidden = STATE.demo.active;
    if (STATE.demo.active && $('demoStep')) $('demoStep').textContent = STATE.demo.text;
    updatePanel();
}

$('demoBtn').addEventListener('click', async () => {
    $('demoMsg').textContent = '';
    try {
        const res = await fetch('/api/demo', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify({action: 'start'})});
        const data = await res.json();
        if (!res.ok) { $('demoMsg').textContent = data.error; return; }
        location.reload();  // shows the demo banner on every page
    } catch (e) { $('demoMsg').textContent = String(e); }
});

const refs_chips = {}, refs_hazards = {};
REGIONS.forEach(r => {
    const g = document.querySelector('[data-region="' + r.id + '"]');
    g.addEventListener('click', () => selectRegion(r.id));
    g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectRegion(r.id); } });
    const chip = el('button', 'chip', r.name); chip.type = 'button';
    chip.addEventListener('click', () => selectRegion(r.id));
    $('regionChips').append(chip); refs_chips[r.id] = chip;
});
HAZARDS.forEach(h => {
    const chip = el('button', 'chip', h.name); chip.type = 'button';
    chip.addEventListener('click', () => selectHazard(h.id));
    $('hazardChips').append(chip); refs_hazards[h.id] = chip;
});

async function refresh() {
    try {
        const res = await fetch('/api/body');
        if (res.status === 401) { location.href = '/login'; return; }
        if (!res.ok) return;
        const first = STATE === null, wasDemo = STATE !== null && STATE.demo.active;
        STATE = await res.json();
        if (wasDemo && !STATE.demo.active) { location.reload(); return; }  // demo finished: drop the banner
        if (first) {
            const worst = REGIONS.reduce((a, r) => RANK[regionLevel(r)] > RANK[regionLevel(a)] ? r : a, REGIONS.find(r => r.id === 'heart'));
            selected = RANK[regionLevel(worst)] >= 2 ? worst.id : 'heart';
            buildPanel();
            const hz = new URLSearchParams(location.search).get('hazard');
            if (hz && HAZARDS.some(h => h.id === hz)) selectHazard(hz);
        }
        paint();
    } catch (e) { console.error(e); }
}
refresh();
setInterval(refresh, 3000);
</script>
{% endblock %}
"""

CHECKIN_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ ui.checkin_title }} - AstroHab{% endblock %}
{% block head %}__CHART_JS__<style>
""" + LEVEL_CSS + r"""
.pair { display: flex; align-items: center; gap: 8px; direction: ltr; }
.pair input { flex: 1; }
.field small { display: block; margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.5; }
.moods { display: flex; gap: 8px; flex-wrap: wrap; }
.mood { position: relative; display: grid; gap: 2px; justify-items: center; text-align: center; border: 1px solid var(--line); border-radius: 10px;
        padding: 8px 10px; min-width: 76px; cursor: pointer; font-size: 12px; color: var(--muted); }
.mood b { font-size: 20px; color: var(--text); }
.mood:has(input:checked) { border-color: var(--accent); background: rgba(91,156,245,.15); color: var(--text); }
.mood input { position: absolute; opacity: 0; pointer-events: none; }
.mood:has(input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
.result-row { display: grid; gap: 4px; padding: 10px 0; border-top: 1px solid var(--line); }
.result-row:first-child { border-top: 0; }
.result-top { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.latest { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.latest div { border: 1px solid var(--line); border-inline-start: 3px solid var(--c); border-radius: 8px; padding: 8px 12px; background: var(--panel-2); }
.latest .v { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
</style>{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel">
        <div class="panel-head"><h2>{{ ui.checkin_title }}</h2><a class="btn" href="/body">{{ ui.see_body }}</a></div>
        <p class="muted">{{ ui.checkin_intro }}</p>
        <div id="streak"></div>
        <form id="form" novalidate>
            <div class="form-grid">
                <div class="field">
                    <label for="bp_sys">{{ ui.f_bp }} ({{ climits.bp_sys.unit }})</label>
                    <div class="pair">
                        <input type="number" id="bp_sys" inputmode="numeric" min="{{ valid.bp_sys[0] }}" max="{{ valid.bp_sys[1] }}" step="1" placeholder="{{ ui.f_sys }}" aria-label="{{ ui.f_sys }}">
                        <span>/</span>
                        <input type="number" id="bp_dia" inputmode="numeric" min="{{ valid.bp_dia[0] }}" max="{{ valid.bp_dia[1] }}" step="1" placeholder="{{ ui.f_dia }}" aria-label="{{ ui.f_dia }}">
                    </div>
                    <small>{{ ui.h_bp }}</small>
                </div>
                <div class="field">
                    <label for="glucose">{{ climits.glucose.label }} ({{ climits.glucose.unit }})</label>
                    <input type="number" id="glucose" inputmode="decimal" min="{{ valid.glucose[0] }}" max="{{ valid.glucose[1] }}" step="1">
                    <small>{{ ui.h_glucose }}</small>
                </div>
                <div class="field">
                    <label for="sleep">{{ climits.sleep.label }} ({{ climits.sleep.unit }})</label>
                    <input type="number" id="sleep" inputmode="decimal" min="{{ valid.sleep[0] }}" max="{{ valid.sleep[1] }}" step="0.1">
                    <small>{{ ui.h_sleep }}</small>
                    <small>{{ ui.sleep_nasa }}</small>
                </div>
            </div>
            <div class="field" role="radiogroup" aria-label="{{ climits.mood.label }}">
                <label>{{ climits.mood.label }}</label>
                <div class="moods">
                {% for n in [1, 2, 3, 4, 5] %}
                    <label class="mood"><input type="radio" name="mood" value="{{ n }}"><b>{{ n }}</b><span>{{ ui['mood_' ~ n] }}</span></label>
                {% endfor %}
                </div>
                <small>{{ ui.h_mood }}</small>
            </div>
            <div class="toolbar mt">
                <button class="btn btn-primary" type="submit" id="saveBtn">{{ ui.save }}</button>
                <button class="btn" type="button" id="clearBtn">{{ ui["clear"] }}</button>
            </div>
            <div class="form-error" id="formError" role="alert"></div>
        </form>
    </section>

    <section class="panel" id="resultPanel" hidden aria-live="polite">
        <div class="panel-head"><h2>{{ ui.result_title }}</h2></div>
        <div id="results"></div>
        <div class="tier mt" id="resultTier"><span class="tier-label" id="resultTierLabel"></span><span id="resultTierText"></span></div>
    </section>

    <section class="panel" id="trendPanel" hidden>
        <div class="panel-head"><h2>{{ ui.trends_title }}</h2></div>
        <p class="muted">{{ ui.trends_note }}</p>
        <div id="trends"></div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.latest_title }}</h2></div>
        <div class="latest" id="latest"></div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.trend_title }}</h2></div>
        <div class="toolbar"><select id="metric" aria-label="{{ ui.trend_title }}"></select></div>
        <div class="chart-box"><canvas id="chart"></canvas></div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.history_title }}</h2><a class="btn" href="/export_checkins.csv">{{ ui.export_csv }}</a></div>
        <div class="table-wrap"><table><thead id="head"></thead><tbody id="rows"></tbody></table></div>
    </section>
    <p class="disclaimer">{{ ui.disclaimer }}</p>
</main>

<script>
const UI = {{ ui|tojson }}, LIMITS = {{ climits|tojson }}, KEYS = {{ keys|tojson }};
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const $ = id => document.getElementById(id);
let rows = [];
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

const select = $('metric');
KEYS.forEach(k => select.add(new Option(LIMITS[k].label + ' (' + LIMITS[k].unit + ')', k)));
select.onchange = draw;

const chart = new Chart($('chart'), {
    type: 'line', data: {labels: [], datasets: []},
    options: {responsive: true, maintainAspectRatio: false, animation: false, plugins: {legend: {display: false}},
        scales: {x: {ticks: {color: '#8b9bb1', maxTicksLimit: 8}, grid: {display: false}},
                 y: {ticks: {color: '#8b9bb1'}, grid: {color: 'rgba(139,155,177,.12)'}}}}
});
function draw() {
    const k = select.value, L = LIMITS[k], pts = rows.filter(r => r[k] !== null);
    const sets = [{data: pts.map(r => r[k]), borderColor: '#5b9cf5', backgroundColor: 'rgba(91,156,245,.10)', borderWidth: 2, pointRadius: 3, fill: true}];
    [['warning', '#e2a93b'], ['danger', '#e5534b']].forEach(([sev, color]) => L[sev].forEach(v => {
        if (v !== null) sets.push({data: pts.map(() => v), borderColor: color, borderWidth: 1, borderDash: [6, 4], pointRadius: 0, fill: false});
    }));
    chart.data.labels = pts.map(r => r.ts.slice(5, 16));
    chart.data.datasets = sets;
    chart.options.scales.y.suggestedMin = L.scale[0];
    chart.options.scales.y.suggestedMax = L.scale[1];
    chart.update('none');
}

function levelOf(k, v) {
    if (v === null || v === undefined) return 'nodata';
    const L = LIMITS[k];
    if (!['warning', 'danger'].some(s => L[s].some(x => x !== null))) return 'unconfigured';
    for (const sev of ['danger', 'warning']) {
        const [lo, hi] = L[sev];
        if ((hi !== null && v > hi) || (lo !== null && v < lo)) return sev;
    }
    return 'normal';
}
function ago(ts) {
    const a = Math.max(0, Math.floor((Date.now() - new Date(ts.replace(' ', 'T')).getTime()) / 60000));
    if (a < 1) return UI.ago_now;
    if (a < 60) return UI.ago_min.replace('{n}', a);
    if (a < 2880) return UI.ago_hour.replace('{n}', Math.floor(a / 60));
    return UI.ago_day.replace('{n}', Math.floor(a / 1440));
}

function drawStreak(box, title, s) {
    box.textContent = '';
    const c = el('div', 'streak' + (s.today ? ' on' : ''));
    const body = el('div');
    body.append(el('div', 'st-t', title),
                el('div', 'st-m', s.today ? UI.st_done : (s.current ? UI.st_keep : UI.st_start)));
    if (s.best > 1) body.append(el('div', 'st-t', UI.st_best.replace('{n}', s.best)));
    const n = el('div', 'st-n', s.current), u = el('div', 'st-t', UI.st_days);
    const num = el('div'); num.append(n, u);
    c.append(num, body); box.append(c);
}

async function load() {
    const res = await fetch('/api/checkins?limit=200');
    if (res.status === 401) { location.href = '/login'; return; }
    if (!res.ok) return;
    const payload = await res.json();
    drawStreak($('streak'), UI.st_title_chk, payload.streak);
    rows = payload.rows;
    const tr = $('trends'); tr.textContent = '';
    Object.entries(payload.trends || {}).forEach(([k, t]) => tr.append(el('div', 'result-row lv-warning', t.message)));
    $('trendPanel').hidden = !tr.children.length;
    draw();
    const latest = $('latest'); latest.textContent = '';
    KEYS.forEach(k => {
        const last = [...rows].reverse().find(r => r[k] !== null);
        const box = el('div'); box.className = 'lv-' + (last ? levelOf(k, last[k]) : 'nodata');
        const v = el('div', 'v', last ? last[k] + ' ' + LIMITS[k].unit : UI.no_data);
        box.append(el('div', 'muted', LIMITS[k].label), v, el('div', 'muted', last ? ago(last.ts) : UI.never));
        latest.append(box);
    });
    const head = $('head'); head.textContent = '';
    const hr = el('tr'); hr.append(el('th', '', UI.col_time), ...KEYS.map(k => el('th', '', LIMITS[k].label)));
    head.append(hr);
    const body = $('rows'); body.textContent = '';
    rows.slice(-15).reverse().forEach(r => {
        const tr = el('tr'); tr.append(el('td', '', r.ts));
        KEYS.forEach(k => { const td = el('td', 'num ' + (r[k] === null ? '' : 'lvl-' + levelOf(k, r[k])), r[k] === null ? '-' : r[k]); tr.append(td); });
        body.append(tr);
    });
    if (!rows.length) { const tr = el('tr'), td = el('td', 'empty', UI.empty_history); td.colSpan = KEYS.length + 1; tr.append(td); body.append(tr); }
}

function showResult(data) {
    const box = $('results'); box.textContent = '';
    data.results.forEach(r => {
        const row = el('div', 'result-row lv-' + r.level), top = el('div', 'result-top');
        top.append(el('strong', '', r.label + ': ' + r.value + ' ' + r.unit), el('span', 'badge', UI['lv_' + r.level]));
        row.append(top);
        if (r.message) row.append(el('div', '', r.message));
        if (r.advice) row.append(el('div', 'muted', UI.advice + ': ' + r.advice));
        if (r.risk) {
            const rk = el('div', 'muted'); rk.style.fontSize = '13px'; rk.append(UI.risk_label + ': ');
            const ra = el('a', '', r.risk.name); ra.href = r.risk.url; ra.target = '_blank'; ra.rel = 'noopener noreferrer'; ra.style.unicodeBidi = 'isolate';
            rk.append(ra); row.append(rk);
        }
        box.append(row);
    });
    const t = data.escalation.tier;
    $('resultTier').className = 'tier mt ' + (t === null ? 'tnone' : 't' + t);
    $('resultTierLabel').textContent = UI['tier_label_' + (t === null ? 'none' : t)] + ' ';
    $('resultTierText').textContent = data.escalation.text;
    $('resultPanel').hidden = false;
    $('resultPanel').scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

$('clearBtn').onclick = () => { $('form').reset(); $('formError').textContent = ''; };
$('form').onsubmit = async ev => {
    ev.preventDefault();
    const err = $('formError'), btn = $('saveBtn'), body = {};
    err.textContent = '';
    ['bp_sys', 'bp_dia', 'glucose', 'sleep'].forEach(k => { const v = $(k).value.trim(); if (v) body[k] = v; });
    const mood = document.querySelector('input[name="mood"]:checked');
    if (mood) body.mood = mood.value;
    btn.disabled = true; btn.textContent = UI.saving;
    try {
        const res = await fetch('/api/checkin', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: JSON.stringify(body)});
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { err.textContent = data.error || UI.save_failed; return; }
        showResult(data);
        $('form').reset();
        await load();
    } catch (e) { err.textContent = UI.save_failed; }
    finally { btn.disabled = false; btn.textContent = UI.save; }
};
load();
</script>
{% endblock %}
"""

HAZARDS_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ ui.hz_title }} - AstroHab{% endblock %}
{% block head %}<style>
""" + LEVEL_CSS + r"""
.hz-grid { display: grid; gap: 16px; }
.hz-card { border-inline-start: 4px solid var(--accent); }
.hz-card h3 { margin-bottom: 4px; }
.hz-sec { margin-top: 10px; }
.hz-sec h4 { font-size: 14px; color: var(--muted); font-weight: 600; margin-bottom: 2px; }
.hz-sec.esc h4 { color: var(--warn); }
.hz-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.hz-chip { border: 1px solid var(--c); border-radius: 10px; padding: 4px 10px; font-size: 13px; }
.hz-rg { font-size: 14px; color: var(--muted); font-weight: 600; margin: 12px 0 4px; }
.hz-risks { list-style: none; display: grid; gap: 4px; direction: ltr; text-align: left; }
.hz-risks li { font-size: 14px; }
.hz-risks li.watched a { font-weight: 600; }
.hz-links { margin-top: 8px; display: grid; gap: 4px; font-size: 13px; }
.hz-links a { direction: ltr; unicode-bidi: plaintext; }
.dose-nums { display: flex; gap: 28px; flex-wrap: wrap; margin: 8px 0; }
.dose-nums strong { display: block; font-size: 22px; }
.dose-bar { height: 12px; border-radius: 8px; background: rgba(127,127,127,.25); overflow: hidden; }
.dose-bar div { height: 100%; width: 0; background: var(--accent); transition: width .4s; }
.dose-bar div.warning { background: var(--warn); }
.dose-bar div.danger { background: #d64545; }
</style>{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel"><div class="panel-head"><h2>{{ ui.hz_title }}</h2></div><p class="muted">{{ ui.hz_intro }}</p></section>
    <section class="panel" id="dosePanel"><div class="panel-head"><h2>{{ ui.dose_title }}</h2></div>
        <p class="muted">{{ ui.dose_intro }}</p>
        <div class="dose-nums"><div><span class="muted">{{ ui.dose_total }}</span><strong id="doseTotal">--</strong></div>
            <div><span class="muted">{{ ui.dose_rate }}</span><strong id="doseRate">--</strong></div>
            <div><span class="muted">{{ ui.dose_limit }}</span><strong id="doseLimit">--</strong></div></div>
        <div class="dose-bar"><div id="doseFill"></div></div>
        <p class="muted" id="doseNote"></p>
        <div class="toolbar mt"><button class="btn" type="button" id="stormBtn">{{ ui.dose_storm_btn }}</button><span class="muted" id="stormMsg"></span></div>
    </section>
    <div class="hz-grid" id="grid"></div>
    <section class="panel"><div class="panel-head"><h2>{{ ui.hz_risks_title }}</h2></div><p class="muted">{{ ui.hz_risks_intro }}</p>
        {% for g in risk_groups %}<h4 class="hz-rg">{{ g.group }}</h4><ul class="hz-risks">
            {% for r in g['items'] %}<li{{ ' class=watched' if r.watched }}><a href="{{ r.url }}" target="_blank" rel="noopener noreferrer">{{ r.name }}</a>{% if r.watched %} <span class="badge">{{ ui.hz_watched }}</span>{% endif %}</li>{% endfor %}
        </ul>{% endfor %}
    </section>
    <p class="disclaimer">{{ ui.disclaimer }}</p>
</main>
<script>
const UI = {{ ui|tojson }}, HAZ = {{ hazards|tojson }};
const grid = document.getElementById('grid'), chipRefs = {};
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function section(cls, title, text) { const s = el('div', 'hz-sec ' + cls); s.append(el('h4', '', title), el('p', '', text)); return s; }
HAZ.forEach(h => {
    const card = el('section', 'panel hz-card'), head = el('div', 'panel-head');
    card.id = h.id; head.append(el('h3', '', h.name)); card.append(head, el('p', 'muted', h.what));
    card.append(section('', UI.hz_effects, h.effects), section('', UI.hz_prevent, h.prevent), section('esc', UI.hz_escalate, h.escalate));
    if (h.facts) card.append(section('', UI.hz_facts, h.facts));
    const m = el('div', 'hz-sec'); m.append(el('h4', '', UI.hz_metrics));
    if (h.metrics.length) {
        const chips = el('div', 'hz-chips'); m.append(chips); chipRefs[h.id] = chips;
    } else { m.append(el('p', 'muted', UI.hz_no_metrics)); }
    card.append(m);
    const links = el('div', 'hz-links');
    const np = el('a', '', UI.hz_nasa_page); np.href = h.nasa_url; np.target = '_blank'; np.rel = 'noopener noreferrer'; links.append(np);
    if (h.risks.length) {
        links.append(el('span', 'muted', UI.hz_related_risks + ':'));
        h.risks.forEach(r => { const ra = el('a', '', r.name); ra.href = r.url; ra.target = '_blank'; ra.rel = 'noopener noreferrer'; links.append(ra); });
    }
    card.append(links);
    const a = el('a', 'btn', UI.hz_open_map); a.href = '/body?hazard=' + h.id; a.style.marginTop = '10px'; a.style.display = 'inline-block';
    card.append(a); grid.append(card);
});
async function refresh() {
    try {
        const res = await fetch('/api/body');
        if (res.status === 401) { location.href = '/login'; return; }
        if (!res.ok) return;
        const st = await res.json();
        HAZ.forEach(h => {
            const box = chipRefs[h.id]; if (!box) return;
            box.textContent = '';
            h.metrics.forEach(k => {
                const m = st.metrics[k]; if (!m) return;
                const chip = el('span', 'hz-chip lv-' + m.level, m.label + ': ' + (m.value === null ? UI.no_data : m.value + ' ' + m.unit) + ' · ' + UI['lv_' + m.level]);
                box.append(chip);
            });
        });
    } catch (e) { console.error(e); }
}
async function refreshDose() {
    try {
        const res = await fetch('/api/dose');
        if (!res.ok) return;
        const d = await res.json();
        document.getElementById('doseTotal').textContent = d.dose + ' ' + d.unit;
        document.getElementById('doseRate').textContent = d.rate === null ? '--' : d.rate + ' ' + d.unit + '/d';
        document.getElementById('doseLimit').textContent = d.configured ? d.limit + ' ' + d.unit : '--';
        const fill = document.getElementById('doseFill');
        fill.style.width = d.configured ? Math.round(d.fraction * 100) + '%' : '0%';
        fill.className = d.level === 'danger' || d.level === 'warning' ? d.level : '';
        let note = d.configured ? UI.dose_source + ': ' + d.source : UI.dose_not_set;
        if (d.level === 'danger') note = UI.dose_over + '. ' + note;
        if (d.storm > 0) note = UI.dose_storm_on + '. ' + note;
        document.getElementById('doseNote').textContent = note;
    } catch (e) { console.error(e); }
}
document.getElementById('stormBtn').addEventListener('click', async () => {
    await fetch('/api/storm', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content}, body: '{}'}); refreshDose();
});
refresh(); refreshDose(); setInterval(refresh, 5000); setInterval(refreshDose, 2000);
</script>
{% endblock %}
"""

SUMMARY_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ ui.sm_title }} - AstroHab{% endblock %}
{% block head %}<style>
""" + LEVEL_CSS + r"""
.sm-meta { display: flex; gap: 18px; flex-wrap: wrap; margin: 6px 0 10px; font-size: 14px; }
.sm-tools { display: flex; gap: 8px; flex-wrap: wrap; }
.sm-table td, .sm-table th { font-size: 13px; vertical-align: top; }
.sm-sub { font-size: 14px; margin: 10px 0 4px; color: var(--muted); }
.sm-alert { padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
.sm-alert .badge { margin-inline-end: 8px; }
@media print { .no-print { display: none !important; } .tier { border-color: #999; background: #fff; } }
</style>{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <section class="panel">
        <div class="panel-head"><h2>{{ ui.sm_title }}</h2>
            <div class="sm-tools no-print">
                {% if crew %}<select id="memberSel" aria-label="{{ ui.sm_member }}">{% for n in crew %}<option value="{{ n }}" {{ 'selected' if n == s.user }}>{{ n }}</option>{% endfor %}</select>{% endif %}
                {% for d in (1, 7, 30) %}<a class="btn" href="/summary?days={{ d }}&user={{ s.user|urlencode }}">{{ ui.sm_days.replace('{n}', d|string) }}</a>{% endfor %}
                <a class="btn" href="/summary.csv?days={{ s.days }}&user={{ s.user|urlencode }}">{{ ui.sm_csv }}</a>
                <a class="btn" href="/summary.pdf?days={{ s.days }}&user={{ s.user|urlencode }}">{{ ui.sm_pdf }}</a>
            </div>
        </div>
        <p class="muted no-print">{{ ui.sm_intro }}</p>
        <div class="sm-meta"><span><strong>{{ ui.sm_user }}:</strong> {{ s.user }}</span>
            <span><strong>{{ ui.sm_period }}:</strong> {{ s["from"] }} → {{ s.to }}</span></div>
        <p>{{ ui.sm_counts.replace('{r}', s.readings|string).replace('{c}', s.checkins|string).replace('{w}', s.alert_counts.warning|string).replace('{d}', s.alert_counts.danger|string) }}</p>
        <p>{{ ui.sm_exercise.replace('{s}', s.exercise.sessions|string).replace('{m}', s.exercise.minutes|string).replace('{d}', s.exercise.days_active|string) }}</p>
        <h3 class="sm-sub">{{ ui.sm_ex_log }}</h3>
        <div class="table-wrap"><table class="sm-table"><thead><tr><th>{{ ui.sm_ex_time }}</th><th>{{ ui.sm_ex_min }}</th><th>{{ ui.sm_ex_type }}</th><th>{{ ui.sm_ex_note }}</th></tr></thead><tbody>
        {% for e in s.exercise.log %}<tr><td>{{ e.ts }}</td><td class="num">{{ e.minutes if e.minutes else '-' }}</td><td>{{ e.activity or ui.sm_ex_nodetails }}</td><td>{{ e.note }}</td></tr>
        {% else %}<tr><td colspan="4" class="muted">{{ ui.sm_ex_none }}</td></tr>{% endfor %}
        </tbody></table></div>
        <div class="tier t{{ s.tier if s.tier is not none else '' }}{{ ' tnone' if s.tier is none }}">
            <span class="muted">{{ ui.sm_current }}</span><span>{{ s.tier_text }}</span>
        </div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.sm_metrics }}</h2></div>
        <div class="table-wrap"><table class="sm-table"><thead><tr>
            <th>{{ ui.sm_col_metric }}</th><th>{{ ui.sm_col_source }}</th><th>{{ ui.sm_col_n }}</th><th>{{ ui.sm_col_min }}</th><th>{{ ui.sm_col_max }}</th>
            <th>{{ ui.sm_col_mean }}</th><th>{{ ui.sm_col_last }}</th><th>{{ ui.sm_col_warn }}</th><th>{{ ui.sm_col_danger }}</th>
            <th>{{ ui.sm_col_limits }}</th><th>{{ ui.sm_col_limit_source }}</th></tr></thead><tbody>
        {% for m in s.metrics %}<tr><td>{{ m.label }} ({{ m.unit }})</td><td>{{ m.reading_source }}</td><td class="num">{{ m.n }}</td>
            <td class="num">{{ '-' if m.min is none else m.min }}</td><td class="num">{{ '-' if m.max is none else m.max }}</td>
            <td class="num">{{ '-' if m.mean is none else m.mean }}</td><td class="num">{{ '-' if m.last is none else m.last }}</td>
            <td class="num">{{ m.warning_n }}</td><td class="num">{{ m.danger_n }}</td><td>{{ m.limits }}</td><td>{{ m.limit_source }}</td></tr>{% endfor %}
        </tbody></table></div>
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.sm_trends }}</h2></div>
        {% for t in s.trends %}<p class="sm-alert">{{ t }}</p>{% else %}<p class="muted">{{ ui.sm_no_trends }}</p>{% endfor %}
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.sm_alerts }}</h2></div>
        {% for a in s.alerts %}<div class="sm-alert lv-{{ a.level }}"><span class="badge">{{ ui['lv_' + a.level] }}</span><span class="muted">{{ a.ts }}</span> {{ a.reason }}</div>
        {% else %}<p class="muted">{{ ui.sm_no_alerts }}</p>{% endfor %}
    </section>

    <section class="panel">
        <div class="panel-head"><h2>{{ ui.sm_notes }}</h2></div>
        <p class="muted">{{ ui.sm_note_limits }}</p><p class="muted">{{ ui.sm_note_trend }}</p>
    </section>
    <p class="disclaimer">{{ ui.disclaimer }}</p>
</main>
<script>
const sel = document.getElementById('memberSel');
if (sel) sel.addEventListener('change', () => { location.href = '/summary?days={{ s.days }}&user=' + encodeURIComponent(sel.value); });
</script>
{% endblock %}
"""

CREW_TEMPLATE = r"""{% extends "base" %}
{% block title %}{{ ui.crew_title }} - AstroHab{% endblock %}
{% block head %}<style>
""" + LEVEL_CSS + r"""
.crew-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.member { background: var(--panel); border: 1px solid var(--line); border-inline-start: 4px solid var(--c); border-radius: 12px; padding: 14px 16px; display: grid; gap: 6px; }
.member h3 { font-size: 16px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.member .row { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 14px; }
.member .vals { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.member .vals span { border: 1px solid var(--line); border-radius: 8px; padding: 1px 8px; font-size: 12px; color: var(--muted); }
.member.inactive { opacity: .8; }
.tag { font-size: 12px; color: var(--muted); border: 1px solid var(--line); border-radius: 10px; padding: 0 8px; }
.crew-note { font-size: 14px; }
</style>{% endblock %}
{% block body %}
{% include "topbar" %}
<main class="wrap">
    <div id="tier" class="tier" role="status" aria-live="polite">
        <span class="muted">{{ ui.tier_title }}</span>
        <span class="tier-label" id="tierLabel"></span>
        <span id="tierText"></span>
        <span class="crew-note muted" id="summary"></span>
    </div>
    <p class="muted">{{ ui.crew_intro_doctor if role == 'doctor' else (ui.crew_intro_admin if role == 'admin' else ui.crew_intro_member) }}</p>
    <section class="crew-grid" id="grid" aria-live="polite"></section>
    <p class="disclaimer">{{ ui.disclaimer }}</p>
</main>
<script>
const UI = {{ ui|tojson }};
const $ = id => document.getElementById(id);
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function ago(m) {
    if (m === null || m === undefined) return null;
    if (m < 1) return UI.ago_now;
    if (m < 60) return UI.ago_min.replace('{n}', m);
    if (m < 2880) return UI.ago_hour.replace('{n}', Math.floor(m / 60));
    return UI.ago_day.replace('{n}', Math.floor(m / 1440));
}
function render(d) {
    const t = d.tier, tier = $('tier');
    tier.className = 'tier ' + (t === null ? 'tnone' : 't' + t);
    $('tierLabel').textContent = UI['tier_label_' + (t === null ? 'none' : t)];
    $('tierText').textContent = d.tier_text;
    $('summary').textContent = UI.crew_active.replace('{a}', d.active).replace('{n}', d.total) + ' · ' +
        UI.crew_counts.replace('{d}', d.counts.danger).replace('{w}', d.counts.warning).replace('{k}', d.counts.normal) + ' · ' +
        (d.buzzer ? UI.crew_buzzer_on : UI.crew_buzzer_off);
    const grid = $('grid'); grid.textContent = '';
    d.members.forEach(m => {
        const card = el('article', 'member lv-' + m.level + (m.active ? '' : ' inactive'));
        const h = el('h3', '', m.name);
        if (m.me) h.append(el('span', 'tag', UI.crew_you));
        h.append(el('span', 'tag', m.role === 'admin' ? UI.crew_admin : UI.crew_commander));
        card.append(h);
        const top = el('div', 'row'), badge = el('span', 'badge lv-' + m.level, UI['lv_' + m.level]);
        top.append(badge, el('span', 'tier-label', UI['tier_label_' + (m.tier === null ? 'none' : m.tier)]));
        card.append(top);
        if (m.metric) card.append(el('div', 'row', UI.crew_worst + ': ' + m.metric));
        const seen = ago(m.seen_minutes);
        card.append(el('div', 'row muted', UI.crew_activity + ': ' + (m.active ? UI.crew_online : (seen ? UI.crew_offline + ' · ' + seen : UI.crew_never_seen))));
        const ci = ago(m.checkin_minutes);
        card.append(el('div', 'row muted', UI.crew_checkin + ': ' + (ci || UI.never)));
        if (m.buzzer) card.append(el('div', 'row', UI.crew_buzzer_member));
        if (m.demo) card.append(el('div', 'row muted', UI.crew_demo));
        if (m.values && Object.keys(m.values).length) {
            const v = el('div', 'vals');
            Object.values(m.values).forEach(x => v.append(el('span', '', x.label + ': ' + x.value + ' ' + x.unit)));
            card.append(v);
        } else if (m.values && !m.active) { card.append(el('div', 'muted', UI.crew_no_data)); }
        grid.append(card);
    });
}
async function refresh() {
    try {
        const res = await fetch('/api/crew');
        if (res.status === 401) { location.href = '/login'; return; }
        if (res.ok) render(await res.json());
    } catch (e) { console.error(e); }
}
refresh(); setInterval(refresh, 3000);
</script>
{% endblock %}
"""

TEMPLATES = {
    "base": BASE_TEMPLATE, "topbar": TOPBAR_TEMPLATE, "login": LOGIN_TEMPLATE, "exercise": EXERCISE_TEMPLATE,
    "dashboard": DASHBOARD_TEMPLATE, "history": HISTORY_TEMPLATE,
    "nasa": NASA_TEMPLATE, "admin": ADMIN_TEMPLATE,
    "body": BODY_TEMPLATE, "checkin": CHECKIN_TEMPLATE,
    "hazards": HAZARDS_TEMPLATE, "summary": SUMMARY_TEMPLATE, "crew": CREW_TEMPLATE,
}


def _make_env(templates):
    # autoescape مفعّل: أسماء المستخدمين وأسباب التنبيه تُعرض كنص آمن
    return Environment(loader=DictLoader(templates), autoescape=True)


ENVS = {"ar": _make_env(TEMPLATES),
        "en": _make_env({name: translate_template(src) for name, src in TEMPLATES.items()})}
