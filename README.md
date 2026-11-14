# AstroHab

**Crew health monitoring for a space station.** AstroHab tracks six vital signs in real time, raises an alarm on a physical Arduino buzzer when something is wrong, and lets the commander talk to an AI assistant by voice in Arabic or English.

Built for the NASA hackathon.

## Code layout

`astrohab.py` is the entry point: it holds the imports, loads the parts below in order into one shared module namespace, and starts the server (`python astrohab.py`). Keeping one namespace means every part sees the same settings and state.

| Part (`astrohab_parts/`) | Content |
|---|---|
| `01_settings.py` | settings read from `.env` or the environment |
| `02_vitals_model.py` | metrics, limits, evaluation, simulation |
| `03_database.py` | SQLite: users, history, alerts, chat, exercises |
| `04_engine.py` | per-user state, automatic alarm and silence |
| `05_arduino_and_voice.py` | serial link to the Arduino, optional spoken alerts |
| `06_assistant.py` | Gemini assistant, offline local assistant |
| `07_nasa_data.py` | CSV files from `data/nasa`, limit derivation, NASA risk links |
| `08_templates.py` | HTML/CSS/JS pages, Arabic and English |
| `09_web_app.py` | Flask routes, login, roles, security headers |
| `10_startup.py` | event hooks, HTTPS port, background threads |

## How this project was built

The software was built with **Claude (Anthropic)** as the AI coding assistant.

## Features

- **Six live vital signs:** heart rate, body temperature, stress, radiation, oxygen, bone density, with live charts and a clear status bar (stable, warning, danger).
- **Alarm limits come from NASA open data.** No thresholds are hard-coded. The admin derives them from a NASA CSV column (percentiles) or imports an explicit `limits.csv`. Every alarm shows the source of the limit that triggered it. Until limits are set, the system declares no danger.
- **Physical alarm.** On danger, an Arduino buzzer starts automatically and the reason is spoken. It silences itself after 3 calm readings. The buzzer is one shared device: it rings while **any** crew member is in danger, and silencing it from any account acknowledges it for everyone for 30 seconds (then automatic control resumes if the danger is still there).
- **Fail-safe buzzer.** The computer re-sends the wanted buzzer state every second (a heartbeat). If the heartbeats stop (program closed, cable pulled) the Arduino silences the buzzer by itself after 5 seconds instead of ringing forever.
- **Voice assistant (Gemini).** Dictate a question, get a spoken answer on the same device you used. The assistant sees the live readings and the last few messages of the conversation, explains why an alarm is on, and understands **explicit commands** such as "turn off the alarm" / "اطفي الإنذار". Questions and negations ("why can't I turn off the alarm?", "don't stop the alarm", "هل الإنذار مطفأ؟") never change the buzzer.
- **Exercise button.** Pressing the board's button confirms an exercise session: bone density improves and the assistant encourages the person. The button is shared, so the app finds out who pressed it: with one person online it is credited to them at once; with several, everyone online sees a blue bar "The exercise button was pressed. Was it you?" and the first to press **It was me** gets the session. If nobody claims it within a minute it is dropped and a note appears in the chat.
- **Crew status** (`/crew`): one card per crew member with their level (normal, warning, danger), recommendation tier, main metric, whether they are active, how long since their last self check-in, and whether their buzzer is on, plus a crew-wide recommendation and the shared buzzer state. Everyone sees statuses; the numbers are shown only to their owner and to the admin. Someone running the demo is shown with their real readings, never the simulated demo values.
- **Early warning.** If a self check-in metric is still normal but its steady trend would reach a reference limit within about 3 more readings, the trend text says so (a simple linear projection on your own readings and the imported limits, not a medical prediction). `Config.EARLY_HORIZON_READINGS`.
- **Crew alerts and help call.** A red bar appears on every page when a crew member who is active is in danger or has pressed **Call for help** (the button in the top bar asks for a second press to confirm and can be cancelled; calls expire after `Config.HELP_CALL_MINUTES`). Anyone else can press **I am with them**, and everyone sees who is on the way. Only the name and the metric are shown, never numbers. A help call is also saved in the alert log. It does not ring the physical buzzer.
- **PDF for the flight surgeon.** The doctor summary has a **Download PDF** button (`/summary.pdf?days=N`): one click downloads an A4 landscape file with the metrics table, trends, alerts and notes, in Arabic or English according to the page language. It is built on the server with `reportlab`; Arabic letter joining and right-to-left ordering are done in the code, and the bundled DejaVu Sans font (`static/fonts`, free license in `DEJAVU-LICENSE.txt`) is used, with system fonts as a fallback. Without `reportlab` installed the button answers with a short message telling you to run `pip install reportlab`.
- **Flight surgeon account.** A flight surgeon registers like anyone else, then the **admin** opens the Admin page and changes that account's role to "Flight surgeon". The change applies at once, even to an open session. A flight surgeon is read-only: sees the crew screen with the numbers, the doctor summary (with a selector to pick any crew member, plus CSV and PDF), the five hazards and the NASA data page; cannot change anything, is not counted as crew, and cannot press the SOS button.
- **Exercise log.** Every press of the Arduino exercise button confirms a session (and raises bone density in the simulation by an illustrative 2.5 points, not a NASA value). The person who pressed it (see the claim banner) then gets a strip that opens the page `/exercise` (under "More"), where they log that session's minutes (1 to 300), the exercises they did (one or more of the NASA exercise names, in English: the ARED lifts such as Back squat, Deadlift and Heel raise, and treadmill or cycle work, continuous or interval) and an optional note. The flight surgeon sees time, minutes, exercises and note in the doctor summary (and the PDF).
- **NASA risk links.** Every metric is paired with the official NASA Human Research Program risk it relates to (for example heart rate and blood pressure with *Risk of Cardiovascular Adaptations*), shown as a link on the body-map metric card, under each self check-in result and on the Exercise page. The Five hazards page links each hazard to its NASA page, adds the figures NASA gives (distance to Mars, mission length, Mars gravity) and lists all 17 NASA risks, marking the ones the app watches. The pairing is the project's own and the page says so.
- **Limits only from NASA and US government sources.** `data/nasa/limits.csv` (the admin imports it from the NASA Data page) holds the limits for heart rate, blood pressure, bone density and cumulative radiation dose (from NASA, each with its source and page) and for blood oxygen, blood glucose, body temperature and the blood-pressure danger level (US government references: NIH MedlinePlus, NIDDK, NHLBI). The site labels each source. No limit is written in the code. The heart-rate warning limit is shown as "Derived from NASA data"; how it was derived is in `RESOURCES.md` section 3b.
- **Cumulative radiation dose.** The Five hazards page adds up the radiation readings per crew member (NASA's limit is about the total dose, not the instantaneous reading) and shows the total against the limit if the admin loaded one (`radiation_total` in `limits.csv`). A button simulates a solar storm so the counter visibly rises.
- **Streaks (encouragement).** A small card on the Exercise page and another on the Self check-in page counts the days in a row with at least one exercise session, or at least one self check-in. A day counts once however many entries it has; the streak stays alive until a whole day is missed, and the card also shows the best streak.
- **Self check-in** (`/checkin`): record blood pressure, blood glucose, sleep hours and mood (any subset). Each value is colored against its NASA-derived limit (no limit means gray, never a guess), with the limit's source, a simple preventive tip, and a three-level recommendation: self-care, tell the crew, or contact the flight surgeons on Earth. Includes a trend chart, history table and CSV export.
- **Interactive body map** (`/body`): a clickable (and keyboard-accessible) body where each region (head, lungs, heart, abdomen, bones, whole body) takes the color of its worst metric. Selecting a region explains each metric (what it is, how spaceflight affects it, what to do, when to ask for help), and the five spaceflight hazards can be highlighted. It reminds you when a manual metric is older than 24 hours (`Config.MANUAL_DUE_HOURS`).
- **Trend alerts.** If your last readings of a check-in metric move the same way (at least 3 in a row, changing by at least 10% of the metric's display range) you get a plain-language heads-up, and it says when the metric is moving toward a reference limit. It compares you with yourself, uses no outside numbers, and never changes the recommendation by itself. The thresholds are `Config.TREND_MIN_READINGS` and `Config.TREND_MIN_CHANGE_PCT`: they are detection settings, not medical limits.
- **Demo mode** (button on the Body map page). Walks the readings through normal, warning, danger (the buzzer rings) and recovery in about 32 seconds, so the recommendation steps up from self-care to tell the crew to contact Earth. One lead metric moves; its values are computed from the limits you imported (no outside numbers), so the demo needs limits first and says so if there are none. A banner shows on every page while it runs, a button stops it, and nothing from the demo is saved to the history or alert log. Phase length: `Config.DEMO_PHASE_TICKS`.
- **Five hazards page** (`/hazards`): one card for each spaceflight hazard (radiation, isolation and confinement, distance from Earth, gravity fields, hostile closed environment) with what it is, how it affects the body, what to do and when to get help, plus the linked metrics with their live status and a link that highlights the affected parts on the body map. The texts are general education and contain no medical numbers.
- **Doctor summary** (`/summary`, last 1, 7 or 30 days; print or CSV): per-metric count, min, max, mean, last value, number of warning and danger readings, the reference limits and their source, how each metric is read (simulated, NASA replay or typed in), the trends, the alerts, and the current recommendation. It uses saved readings only (never the demo), so it is safe to hand to a flight surgeon, and the simulated readings are labelled as such.
- **Arabic / English interface** with a one-click switch (layout direction, labels, alerts and errors).
- **History and reports:** stored readings (every 10 seconds), alert log (a new alert is logged when the level changes *or* when a different metric causes it), CSV export and print.
- **Works offline.** Charts are drawn by a small built-in renderer, so the dashboard needs no CDN. (Optionally add the original Chart.js, see below.)
- **Runs from any device** on the same network. Each user has a private account, data and chat.

## Quick start

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.example .env        # on Windows: copy .env.example .env
python astrohab.py
```

Open **http://localhost:5000**, register, and use the dashboard. The **first account is the admin and can only be created from the computer that runs AstroHab** (localhost), so nobody else on the network can claim it first.

The app works **without any keys or hardware**:
- without `GEMINI_API_KEYS`, or when Gemini cannot be reached, the **local assistant** answers instead (see below);
- without an Arduino it runs in simulation and retries the connection every 5 seconds.

To try Gemini, put a key in `.env` (`GEMINI_API_KEYS=your_key`).

**Local assistant (works offline).** Gemini is always asked first. If there is no key, the network is cut, the quota is used up or the service stays busy, a rule-based assistant answers from the station's own data and tags the reply "(Local reply)" / "(رد محلي)". It understands, in Arabic and English: current status, why the alarm sounded, an explanation of each metric and what to do about it, when to contact the flight surgeon, the five hazards, the reference limits and their source, due check-ins, trends, and the buzzer commands. It never diagnoses and never invents limits: limits come only from NASA data or your `limits.csv`. If it does not understand a question it says so and lists example questions. To demo an outage, unplug the network (or leave the key empty) and ask "what is my status?".

Run the tests with `python -m unittest discover -s tests -v`.

### Optional: the original Chart.js

The built-in chart renderer is enough for every page. If you prefer Chart.js, download the UMD build of Chart.js 4 once and save it as `static/vendor/chart.umd.js` (for example `curl -L https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.js -o static/vendor/chart.umd.js`). It is then served locally, never from a CDN.

### Using it from a phone

Set `HOST=0.0.0.0` in `.env`. **Create the admin account on the computer first**, then others can register from their phones. On start the program prints two addresses:

- `http://<computer-ip>:5000` works but the **microphone is blocked** by the browser.
- `https://<computer-ip>:5443` uses a self-signed certificate. Accept the browser warning (Advanced, then Continue) and the microphone works.

On the computer itself use `http://localhost:5000`; the microphone works there too. Allow ports 5000 and 5443 in the firewall if the phone cannot connect. To limit who can create accounts, set `REGISTRATION_CODE` in `.env`: new accounts then need that invite code.

## NASA data and limits

1. Put the NASA CSV files in `data/nasa/`.
2. Open the **NASA Data** page as admin.
3. Either derive the limits from a column (choose the direction and the warning/danger percentiles, preview, then approve; at least 30 numeric readings are required), or import `data/nasa/limits.csv` with the columns:

   ```
   metric,warning_low,warning_high,danger_low,danger_high,unit,source
   ```

   Metric names: `bpm`, `temp`, `stress`, `radiation`, `oxygen`, `bone_health` (live) and `bp_sys`, `bp_dia`, `glucose`, `sleep`, `mood` (self check-in). The project ships **no** limits of its own: every limit must come from your NASA data, either derived from a column or listed in your own `limits.csv` with its source. Optional extra columns `scale_min,scale_max` set the display range. Importing keeps the metric's existing "read from NASA" source.

A column can also be used as the reading source for a metric, so the dashboard replays the NASA values instead of random simulation. `limits.csv` itself is not listed as a data file.

**How to read these limits.** Percentile limits mean "unusual compared with the chosen NASA data", not "medically dangerous": with a warning percentile of 95 and danger at 99, about 5% / 1% of the chosen data is by definition in warning / danger, and replaying that same column will trigger alarms at those rates. Pick a column that really measures the metric (the first column of a file is usually a time index). For clinical thresholds, import an explicit `limits.csv` from a published reference and put its citation in the `source` column.

### Using the NASA crew-state-monitoring recordings

The NASA data set [Flight Crew Physiological Data for Crew State Monitoring](https://data.nasa.gov/dataset/flight-crew-physiological-data-for-crew-state-monitoring) has one ZIP per subject. The raw files (for example `26_CA.csv`) are 256 Hz signals (ECG, breathing, skin conductance, 20 EEG channels), not ready-made numbers, so convert them first, once, on your computer:

```
pip install -r tools/requirements.txt          # numpy and scipy, only for this tool
python tools/prepare_csm.py PATH_TO_FOLDER_WITH_THE_RAW_FILES -o data/nasa/csm_vitals.csv
```

It reads every `<subject>_CA|DA|SS.csv` (add `--with-loft` for the long simulator files, which can be hundreds of MB), cuts each recording into 30 s windows every 10 s, and writes one small CSV with `heart_rate_bpm`, `breaths_per_min`, `gsr_raw`, `gsr_vs_subject_median` and the `state` (none, startle, channelized, diverted) taken from the file's `Event` column. A `csm_vitals_SOURCES.txt` next to it records the data set, link, date and method for your references. Recordings whose ECG is flat or too noisy get no heart rate (for example, one subject's DA file in our tests is all zeros). The tool adds no limits and no outside numbers. Then on the **NASA Data** page choose `csm_vitals.csv` and a column: `heart_rate_bpm` for heart rate; `gsr_vs_subject_median` is the safer stress column because the raw GSR baseline differs from person to person. Use files from as many subjects as you can: limits derived from one person describe that person.

## Arduino

Sketch: `astrohab_arduino.ino` (Seeed XIAO ESP32-C5, 115200 baud; button on D1, buzzer on D6; in Arduino IDE set Tools > USB CDC On Boot = Enabled).

| Direction | Message | Meaning |
|---|---|---|
| computer to Arduino | `BUZZER_ON` / `BUZZER_OFF` | wanted buzzer state, sent on every change and again every second (heartbeat) |
| Arduino to computer | `exercise_confirmed` | the exercise button was pressed |

If the buzzer is on and no `BUZZER_ON` arrives for 5 seconds, the Arduino turns it off. In the sketch, set `PASSIVE_BUZZER` to `1` if your buzzer is a passive one (needs a tone) instead of an active one. Set the serial port with `SERIAL_PORT` in `.env`.

## Configuration

All settings are environment variables (read from `.env`). **Real environment variables win over the file**, and a trailing ` # comment` in `.env` is ignored. See `.env.example` for the full list.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEYS` | Gemini keys, comma separated; the next key is used on quota errors |
| `GEMINI_MODEL` | model name (default `gemini-3.6-flash`) |
| `GEMINI_FALLBACK_MODEL` | optional backup model if the main one stays busy |
| `GEMINI_TIMEOUT_MS` | wait for Gemini before the local assistant answers (default 15000) |
| `SECRET_KEY` | signs login sessions (set it, otherwise everyone is signed out on each restart) |
| `SERIAL_PORT`, `SERIAL_ENABLED` | Arduino serial port; set `SERIAL_ENABLED=false` for no hardware |
| `VOICE_ENABLED` | enables the host speaker thread |
| `SPEAK_AUTO` | `false` by default: alerts and automatic assistant replies only appear in the chat; set `true` to also speak them on the host computer. Replies to a user's own question are always spoken in that user's browser |
| `HOST`, `PORT` | listening address and port (default 127.0.0.1:5000) |
| `HTTPS_ENABLED`, `HTTPS_PORT` | extra HTTPS port (default 5443) |
| `REGISTRATION_CODE` | optional invite code required to create accounts after the admin |
| `ALLOW_REMOTE_FIRST_ADMIN` | `true` lets the first account be created from another machine (e.g. inside Docker); default `false` |

## Security notes

- Passwords (8 characters or more) are hashed. Sign-in is rate limited: 5 failed attempts per device and username (20 per device) lock sign-in for 5 minutes; account creation is limited per device; assistant messages are limited per user (30 per 10 minutes) to protect the shared Gemini quota.
- The first (admin) account can only be created from localhost, and the check is atomic, so two simultaneous sign-ups cannot both become admin.
- All requests that change data are CSRF-protected, including sign-out (a POST); the language switch is a harmless GET. Admin pages are role-protected.
- Page output is escaped, so usernames and alert text cannot inject HTML. Responses carry `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` and `Referrer-Policy` headers, and request bodies are capped at 64 KB.
- NASA file access is confined to `data/nasa/`.
- API keys and secrets live in `.env`, which is git-ignored. Do not commit it.
- AstroHab runs on the Flask development server, which is fine for a lab or demo network but not for the open internet.

## Limitations

- Check-in values are typed in by the user, and check-in metrics have no limits until you import some. Nothing here is validated against spaceflight medical standards.
- Vital signs are **simulated** unless a NASA column is attached to a metric. No real sensor is connected yet.
- AstroHab is a research and education prototype. It is **not a medical device** and gives no medical advice.
- Gemini needs internet access and a valid key; without them the local assistant answers with fixed texts and keywords, so it is less flexible than Gemini. Voice dictation depends on the browser (Chrome or Edge recommended); spoken replies need an installed voice for the chosen language. Arabic spoken alerts on the host use gTTS (internet) and `playsound3` or `playsound` for playback.
- One physical buzzer serves all accounts, and the exercise button is shared; with several people online the first to say "It was me" gets the session.

## Project layout

```
astrohab.py              the whole application (Flask backend, engine, assistant, web UI)
astrohab_arduino.ino     Arduino sketch
requirements.txt         Python dependencies
.env.example             configuration template
tests/test_astrohab.py   automated tests of the application
tests/test_prepare_csm.py   tests of the NASA data converter (skipped without numpy and scipy)
RESOURCES.md            sources of every exercise name, number and dataset the project uses
tools/prepare_csm.py     converter for the NASA crew-state-monitoring recordings (see above)
tools/requirements.txt   numpy and scipy, only for the converter
static/vendor/           optional: chart.umd.js (Chart.js)
static/fonts/            DejaVu Sans (regular and bold) used for the PDF, with its license
data/nasa/               NASA CSV files go here
data/cert/               generated HTTPS certificate (created on first run)
```
