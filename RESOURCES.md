# AstroHab resources

Sources for every exercise name, number and dataset used in AstroHab. Every health limit in the project comes from NASA data or from a named US government source (NIH); anything else is labelled as a project design choice or a simulation value.

**Status:** `verified` = the source was read directly. `summarized` = obtained through a summary and not yet checked against the original document. `unconfirmed` = sources conflict or the source was not opened.

## 1. Exercise names

Names are shown in English exactly as they appear in the sources. A session can include several exercises.

| Name in the app | Device | Source | Status |
|---|---|---|---|
| Back squat, Single-leg squat, Sumo squat | ARED | [npj Microgravity 2020 (Sprint)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7434884) | summarized |
| Deadlift, Romanian deadlift, Sumo deadlift | ARED | same paper | summarized |
| Heel raise, Single-leg heel raise | ARED | same paper | summarized |
| Front squat, Bench press, Shoulder press, Bent-over row, Upright row, Single leg knee extension | ARED | [NTRS 20090013286](https://ntrs.nasa.gov/api/citations/20090013286/downloads/20090013286.pdf) (Ploutz-Snyder, proposed 3-day program) | summarized; a proposal, not confirmed as flown |
| Treadmill (T2): continuous / interval | T2 (COLBERT) | same paper; [ESA: T2 treadmill](https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Node-3_Cupola/T2_Colbert_Treadmill) | summarized |
| Cycle ergometer (CEVIS): continuous / interval | CEVIS | same paper; [NASA: Astronaut Exercise](https://www.nasa.gov/general/astronaut-exercise/) | summarized |

Published interval formats: 8 x 30 s, 6 x 2 min, 4 x 4 min (Sprint paper).

## 2. Exercise hardware and schedule

| Item | Value | Source | Status |
|---|---|---|---|
| Schedule | 2.5 h per day, 6 days a week including setup; about 1.5 to 2 h of actual exercise | [NASA](https://www.nasa.gov/?p=407627), [PMC7434884](https://pmc.ncbi.nlm.nih.gov/articles/PMC7434884) | unconfirmed (page title and date not captured) |
| Devices in service | ARED, T2, CEVIS | [NASA: Astronaut Exercise](https://www.nasa.gov/general/astronaut-exercise/), [NTRS 20170011470](https://ntrs.nasa.gov/api/citations/20170011470/downloads/20170011470.pdf) | summarized |
| Retired devices | iRED, TVIS | same sources | unconfirmed (retirement dates differ between sources) |
| Orion device | Flywheel Exercise Device, 30 min per day per crew member | [NTRS HRP 2023](https://ntrs.nasa.gov/api/citations/20230001466/downloads/Flywheel%20Dev%20and%20Eval%20Poster-HRP_IWS-2023.pptx.pdf) | summarized |

Figures that differ between sources: ARED install date (2008 or January 2009), T2 install date (September 2009 or October 2010), ARED maximum load (600 or 650 lb), CEVIS maximum load (350 or 300 W), treadmill harness load (75 to 80% or 85% of body weight), number of ARED exercises (29 or more than 45).

## 3. Health limits

| Metric | NASA limit? | Source | Status in the app |
|---|---|---|---|
| Radiation (cumulative dose) | Yes: 600 mSv career (V1 4030), 250 mSv reference solar particle event (V1 4031), 20 mSv per year for nuclear technologies (V1 4032), organ limits in Table 4.8-1 | [NASA-STD-3001 Vol 1 Rev C](https://standards.nasa.gov/sites/default/files/standards/NASA/C//nasa-std-3001-vol-1-rev-c-signature.pdf), [OCHMO-TB-020](https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf) | verified 2026-11-13 against the standard's text: V1 4030 (section 4.8.2, p. 40) 600 mSv, V1 4031 (4.8.3, p. 43) 250 mSv, V1 4032 (4.8.4, pp. 44-45) 20 mSv per mission year. Organ limits and the habitat GCR figure (0.9 vs 0.8 mSv/day, from OCHMO-TB-020) not re-checked |
| Bone density | Yes, relative: at or above 95% of the pre-mission hip and spine value (V1 4027) | same standard | verified 2026-11-13: V1 4027 (section 4.7.2, p. 39) hip and spine at or above 95% of pre-mission values, femoral neck at or above 90%. Loss rate of 1 to 1.5% per month: [NTRS 20170004597](https://ntrs.nasa.gov/api/citations/20170004597/downloads/20170004597.pdf) (summarized) |
| Sleep | Target only: 8.5 h planned sleep period; no minimum | [NASA Section 6.0](https://www.nasa.gov/reference/6-0-medical-operations/), [Sleep brief](https://www.nasa.gov/wp-content/uploads/2023/03/sleep-accomodations-technical-brief-ochmo.pdf) | verified 2026-11-13: Vol 1 section 6.1 (p. 52) gives a recommended 8.5 h sleep period (plus 2 h pre-sleep and 1.5 h post-sleep) in the rationale text, not as a numbered requirement. Shown as a note on the self check-in page, no alert. "7 to 9 hours" is a general recommendation quoted by NASA, not a NASA limit |
| Heart rate | Selection standard only: above 130 at rest (sustained), below 30 outside sleep (OCHMO-STD-100.1A App. A, pp. 76-77); context: mean about 96 bpm for Apollo commanders during lunar descent ([NTRS 20200001709](https://ntrs.nasa.gov/api/citations/20200001709/downloads/20200001709.pdf)) | [OCHMO-STD-100.1A](https://www.nasa.gov/wp-content/uploads/2023/04/ochmo-std-100.1a.pdf) | verified 2026-11-13; warning limit derived from NASA data (section 3b) |
| Systolic and diastolic blood pressure | Selection standard only: sustained 140 systolic or 90 diastolic mmHg or higher (OCHMO-STD-100.1A App. A, G.3, p. 75); context: 116/75 mmHg pre-flight, n=11 ([NTRS 20040201532](https://ntrs.nasa.gov/api/citations/20040201532/downloads/20040201532.pdf)) | [OCHMO-STD-100.1A](https://www.nasa.gov/wp-content/uploads/2023/04/ochmo-std-100.1a.pdf) | verified 2026-11-13; used as warning limits |
| Blood oxygen | No. NASA gives cabin oxygen partial pressure only, which is not SpO2 | [Vol 2 Sec 6.0](https://www.nasa.gov/reference/6-0-natural-and-induced-environments-vol-2), [OCHMO-TB-003](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-003-habitable-atmosphere.pdf) | US government reference used (section 3c) |
| Body temperature, blood glucose | None in the text read. OCHMO-STD-100.1A Appendix A was read on 2026-11-14: no numeric value for body temperature or blood glucose (tests are listed without ranges) | [OCHMO-STD-100.1A](https://www.nasa.gov/wp-content/uploads/2023/04/ochmo-std-100.1a.pdf) | US government reference used (section 3c) |
| Stress, mood | No. V1 4011 is qualitative; the measurement tools (VAS, POMS) are defined without limits | [NTRS 20170005421](https://ntrs.nasa.gov/api/citations/20170005421/downloads/20170005421.pdf) | limits not set |

## 3b. How the heart rate limits were derived from NASA data

The numbers in this section come from NASA. The few limits NASA does not publish come from US government sources and are listed in section 3c. Each source is labelled in the app.

**Warning limit: derived from NASA data (83 bpm).**

1. Input: NASA "Flight Crew Physiological Data for Crew State Monitoring", 17 subjects (5, 6, 9-14, 17-19, 21-26), three recordings each (CA, DA, SS), 256 Hz ECG, about 4.6 hours of signal.
2. `tools/prepare_csm.py` cuts every recording into 30 s windows every 10 s (1,652 windows).
3. Per window: the ECG is band-pass filtered (5 to 25 Hz), R peaks are detected, and heart rate = 60 / median beat interval. A window is rejected unless it has at least 12 clean beats, a relative spread of at most 0.25, and intervals between 0.4 and 1.5 s. A recording whose ECG is flat is rejected as a sensor fault (subject 5 DA).
4. Result: 1,546 valid windows, 50 to 97 bpm, median 61 bpm, 5th to 95th percentile 54 to 83 bpm.
5. The warning limit is the 95th percentile (83 bpm): the rate that only 1 window in 20 of this NASA data exceeds. The admin can change the percentile on the NASA Data page.

Median heart rate per subject (bpm): 10: 54, 24: 56, 26: 56, 19: 57, 11: 60, 17: 60, 14: 61, 18: 61, 25: 61, 23: 62, 13: 63, 9: 66, 21: 67, 22: 70, 6: 70, 5: 75, 12: 86. The spread between people (54 to 86) is why a personal baseline would be more precise than one shared limit.

**Danger limits: NASA's own numbers.** NASA OCHMO-STD-100.1A (astronaut medical standard) Appendix A, read 2026-11-13: sustained sinus tachycardia at rest above 130 beats/min (G.8.A.i(5), p. 76) and heart rate below 30 beats/min not during sleep (G.8.C.i(8), p. 77). These are astronaut medical selection standards, not in-flight alarm thresholds; the app labels them that way.

**Blood pressure.** Same standard, G.3, p. 75: sustained systolic 140 mmHg or higher, or diastolic 90 mmHg or higher. The app uses them as warning limits because one self check-in reading is not "sustained".

**Cumulative radiation dose and bone density.** NASA-STD-3001 Volume 1 Rev C: V1 4030 (career dose less than 600 mSv), V1 4027 (hip and spine at or above 95% of the pre-mission value). The 250 mSv figure (V1 4031, design solar particle event) is kept as reference text, not an alarm.

**Caveats, stated plainly.**
- The recordings are flight-simulator tasks (channelized attention, diverted attention, startle), not rest, and the maximum heart rate seen is 97 bpm, so the data cannot support a derived danger limit.
- 17 subjects is a small sample; the range describes them, not all astronauts.
- Skin conductance (GSR) is uncalibrated and is not used for any limit.
- The limits are loaded through `limits.csv` by the admin; the project ships `data/nasa/limits.csv` with only these sourced limits, imported by the admin. The derived file is included as `data/nasa/csm_vitals.csv` (with `csm_vitals_SOURCES.txt`), so the raw 1 GB recordings are not needed to repeat the percentile step. Reproduce from the raw files: `python tools/prepare_csm.py <folder with the CSV files> -o data/nasa/csm_vitals.csv`.

## 3c. Limits from US government sources

Used only where NASA publishes no number. The challenge allows US government data. Read directly on 2026-11-14; each row is shown in the app as "US government reference".

| Metric | Limit used | Exact source wording | Source |
|---|---|---|---|
| Blood oxygen (SpO2) | warning below 93, danger below 89 | "A normal oxygen saturation level ranges between 95% and 100%." "Contact your provider if your oxygen saturation level is 92% or lower." "If it falls to 88% or lower, seek immediate medical attention." The app compares with "below", so for whole-number readings 93 and 89 give the same result as "92 or lower" and "88 or lower". | [MedlinePlus: Pulse Oximetry](https://medlineplus.gov/lab-tests/pulse-oximetry/) |
| Blood glucose | warning below 70 mg/dL | "a blood glucose reading lower than 70 milligrams per deciliter (mg/dL)" | [NIDDK: Low Blood Glucose](https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/low-blood-glucose-hypoglycemia) |
| Body temperature | warning above 37.5 C, danger above 39.4 C | "An adult probably has a fever when the temperature measured in the mouth is above 99F to 99.5F (37.2C to 37.5C)." Contact a provider right away for a fever that "stays at or keeps rising above 103F (39.4C)". | [MedlinePlus: Fever](https://medlineplus.gov/ency/article/003090.htm) |
| Blood pressure, danger | above 180 systolic or above 120 diastolic | "Higher than 180 systolic pressure OR Higher than 120 diastolic pressure" (hypertensive crisis); the warning stays at NASA's 140/90 | [NHLBI: High Blood Pressure Diagnosis](https://www.nhlbi.nih.gov/health/high-blood-pressure/diagnosis) |

Read but not used as limits: normal resting pulse 60 to 100 beats per minute ([MedlinePlus: Pulse](https://medlineplus.gov/ency/article/003399.htm)), because the heart-rate warning is derived from NASA data (section 3b); fasting glucose 99 or below normal and 126 or above in the diabetes range ([NIDDK: Tests & Diagnosis](https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis)), because the values depend on fasting, which the app does not record. No source gave a number for stress or mood, which stay "limits not set".

## 4. Data

| Source | Used for | Link | Status |
|---|---|---|---|
| Flight Crew Physiological Data for Crew State Monitoring (256 Hz ECG, respiration, GSR, EEG) | `tools/prepare_csm.py`, then import of the derived ranges | [data.nasa.gov](https://data.nasa.gov/dataset/flight-crew-physiological-data-for-crew-state-monitoring) | verified from the files used (17 subjects: 5, 6, 9-14, 17-19, 21-26; recordings CA, DA, SS; about 4.6 h of signal; LOFT files not used; subject 5 DA has a flat ECG so no heart rate from it). Heart rate in these windows: 50 to 97 bpm, median 61; breathing 4 to 32 per minute, median 18. The recordings are flight-simulator tasks, not rest. Ranges derived from it are labelled "derived from NASA data", not official limits. GSR units are uncalibrated |
| OSDR RadLab | candidate dose data | [RadLab](https://visualization.osdr.nasa.gov/radlab/gui/data-overview/) | unconfirmed (formats, units and license not tested) |
| OSDR Environmental Data App (temperature, humidity, CO2, radiation) | candidate | [EDA](https://visualization.osdr.nasa.gov/eda/) | unconfirmed |
| DONKI (space weather) | candidate context layer | [api.nasa.gov](https://api.nasa.gov/) | unconfirmed |
| NLSP / LSDA (real crew data) | available by formal request | [nlsp.nasa.gov/data-request](https://nlsp.nasa.gov/data-request) | processing time unknown |
| Mendeley "Blood Pressures In Spaceflight" | third party; used only to find primary sources | [Mendeley Data](https://data.mendeley.com/datasets/pz6nt4cpxs) | not used for any limit |

## 5. The five hazards and NASA's 17 risks

Read directly from NASA on 2026-11-13 (status: verified).

| Page | Used for |
|---|---|
| [5 Hazards of Human Spaceflight](https://www.nasa.gov/hrp/hazards/) (updated 2026-06-12) | the five hazards; the only numbers it gives: Mars about 140 million miles from Earth on average, a lunar trip about three days, a Mars mission roughly three years, Mars gravity three-eighths of Earth's |
| [Space radiation](https://www.nasa.gov/hrp/hazard-space-radiation/), [Isolation and confinement](https://www.nasa.gov/hrp/hazard-isolation-and-confinement/), [Distance from Earth](https://www.nasa.gov/hrp/hazard-distance-from-earth/), [Gravity fields](https://www.nasa.gov/hrp/hazard-gravity-fields/), [Hostile and closed environments](https://www.nasa.gov/hrp/hazard-hostile-closed-environments/) | the link on each hazard card |
| [Risks of Human Spaceflight](https://www.nasa.gov/hrp/risks/) (updated 2026-07-21) | the 17 risks: 11 human physiology, 5 behavioral performance and human factors, 1 space radiation; each has its own page under `nasa.gov/reference/` |
| [Ongoing HRP Research](https://www.nasa.gov/hrp/ongoing-hrp-research/) | studies relevant to this project: [ARCHeR](https://www.nasa.gov/reference/archer/) (wrist actigraphy: motion, sleep, light), [Standard Measures](https://www.nasa.gov/reference/standard-measures/) and [Artemis II Standard Measures](https://www.nasa.gov/reference/artemis-ii-standard-measures/) (physiological and psychological measures kept in a data bank), [Zero T2](https://www.nasa.gov/reference/zero-t2/) (exercise without a treadmill), [Tempus Pro](https://www.nasa.gov/reference/tempus-pro/) (telemedicine device) |
| [CSA: Monitoring radiation for astronaut health](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp) | context only: neutrons are about 30% of total radiation on the ISS; instruments CANS and bubble detectors. It gives no dose figures |
| [CSA: Why do we conduct science experiments in space?](https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp) | context only: about 200 experiments aboard the ISS at any time; health topics bone, cardiovascular, metabolic (Type 2 diabetes) and accelerated-aging-like effects; no numbers for limits |

None of these pages gives a numeric health limit.

Pairing of AstroHab metrics with NASA risks (project design; NASA's pages do not state it):

| Metric | NASA risk |
|---|---|
| Heart rate, systolic and diastolic blood pressure | Risk of Cardiovascular Adaptations |
| Bone density | Risk of Spaceflight-Induced Bone Changes |
| Exercise | Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness |
| Sleep | Risk of Inadequate Sleep and Irregular Schedules |
| Mood, stress | Risk of Behavioral Changes and Psychiatric Disorders |
| Radiation | Risk of Radiation-Induced Cancers |
| Oxygen | Risk of Hypoxia (NASA ties it to spacewalk procedures, so the pairing is approximate) |
| Blood glucose, body temperature | none: no NASA risk title matches |

## 6. Not from NASA (project design)

| Item | Value | Note |
|---|---|---|
| Bone density baseline | the simulation starts at 100 (= the pre-mission value) so the relative NASA limit (V1 4027) can be applied; `data/nasa/limits.csv` (imported by the admin) sets the 95% line | simulation value |
| Cumulative dose | the radiation reading counts as mSv per simulated day and one update equals one simulated day (`SIM_DAYS_PER_TICK`); the limit is loaded only from `limits.csv` as metric `radiation_total`; the solar storm button (`STORM_TICKS`) raises the reading within the simulation's usual spike range | simulation values |
| Bone density gain per exercise button press | +2.5 points | illustrative simulation value |
| Bone density decay (`BONE_DECAY_PER_TICK`) | constant in the code | simulation value |
| Escalation to the flight surgeon and trend rules | in the code | NASA publishes no standard for when a crew member contacts the flight surgeon |
| Trends (mood, stress, sleep and others) | a steady change over consecutive readings of the same person; needs no limit and does not change any level | project design; not a medical limit |
| Streak | one count per day with an exercise session or a self check-in | encouragement feature; the streak stays alive until a whole day is missed |
| Exercise details window | 12 hours after a button press (`EXERCISE_DETAILS_HOURS`) | configuration |
| Who pressed the button | claim banner, 60 seconds (`EXERCISE_CLAIM_SECONDS`) | configuration |
