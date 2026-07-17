"""Generate the exact CardioTrack CT-200 V1 and V2 PDFs.

This matches the text, structures, and irregularities in the screenshots:
  1. Out-of-order subsections: 3.4 Auto Shutoff appears before 3.3 Result Display
  2. Skipped levels: 2.1.1.1 Battery Life under 2.1 (without 2.1.1)
  3. Tables in 2.1 (General Specs) and 4.2 (Error Codes)
  4. Changes in V2:
     - 2.1.1.1 Battery life cycles: 300 -> 250, threshold: 15% -> 10%
     - 3.2 Inflation increments: 40 mmHg -> 30 mmHg, extra sentence added
     - 4.2 Error Codes table: E3 time: 2s -> 1.5s, E6 added
     - 4.3 Alarm thresholds mentions E1-E6 instead of E1-E5
     - 5.3 Data Export added as a new section
"""

import os
import fitz

# Font sizing
FONT_TITLE = 18
FONT_H1 = 15
FONT_H2 = 13
FONT_H3 = 11.5
FONT_H4 = 10.5
FONT_BODY = 10
FONT_TABLE = 9

BLACK = (0, 0, 0)
TABLE_BORDER = (0.4, 0.4, 0.4)
TABLE_HEADER_BG = (0.9, 0.9, 0.95)


def _write_text(page, x, y, text, fontsize=FONT_BODY, bold=False, color=BLACK):
    fontname = "helv" if not bold else "hebo"
    line_height = fontsize * 1.4
    lines = text.splitlines()
    for i, line_text in enumerate(lines):
        tw = fitz.TextWriter(page.rect)
        try:
            tw.append((x, y + i * line_height), line_text, fontsize=fontsize, font=fitz.Font(fontname))
        except Exception:
            tw.append((x, y + i * line_height), line_text, fontsize=fontsize)
        tw.write_text(page, color=color)
    return y + (line_height * len(lines))


def _draw_table(page, x, y, headers, rows, col_widths):
    row_height = 18
    shape = page.new_shape()
    cur_x = x
    for i, header in enumerate(headers):
        rect = fitz.Rect(cur_x, y, cur_x + col_widths[i], y + row_height)
        shape.draw_rect(rect)
        shape.finish(color=TABLE_BORDER, fill=TABLE_HEADER_BG)
        _write_text(page, cur_x + 4, y + 13, header, fontsize=FONT_TABLE, bold=True)
        cur_x += col_widths[i]
    y += row_height
    for row in rows:
        cur_x = x
        for i, cell in enumerate(row):
            rect = fitz.Rect(cur_x, y, cur_x + col_widths[i], y + row_height)
            shape.draw_rect(rect)
            shape.finish(color=TABLE_BORDER)
            _write_text(page, cur_x + 4, y + 13, cell, fontsize=FONT_TABLE)
            cur_x += col_widths[i]
        y += row_height
    shape.commit()
    return y + 10


def generate_ct200_pdf(version: int, output_path: str):
    doc = fitz.open()

    # ──────────────────────────────────────────────────────────────────
    # PAGE 1 — Title, Section 1, 1.1, 1.2, Section 2
    # ──────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    y = 80

    y = _write_text(page, 72, y, "CardioTrack CT-200 Home Blood\nPressure Monitor — Technical &\nUser Manual", fontsize=FONT_TITLE, bold=True)
    y += 20

    y = _write_text(page, 72, y, "1. Device Overview", fontsize=FONT_H1, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The CardioTrack CT-200 is an oscillometric, upper-arm blood pressure\nmonitor intended for home use by adult users. It measures systolic\npressure, diastolic pressure, and pulse rate, and stores up to 200\nreadings across two user profiles.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "1.1 Intended Use", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The CT-200 is intended to non-invasively measure blood pressure and\npulse rate in adults with an arm circumference of 22–42 cm. It is not\nintended for use on neonates, infants, or pregnant users, and is not a\ndiagnostic device — readings should be interpreted by a qualified\nclinician.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "1.2 Indications and Contraindications", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The device should not be used on the arm ipsilateral to a mastectomy,\non limbs with an active intravenous line, or on users with severe\narrhythmia without clinician guidance, since oscillometric measurement\ncan be unreliable in these cases.", fontsize=FONT_BODY)
    y += 20

    y = _write_text(page, 72, y, "2. Physical and Electrical Specifications", fontsize=FONT_H1, bold=True)

    # ──────────────────────────────────────────────────────────────────
    # PAGE 2 — Section 2.1, Table, 2.1.1.1, 2.2, Section 3, 3.1
    # ──────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "2.1 General Specifications", fontsize=FONT_H2, bold=True)
    y += 5

    # General Specifications Table
    y = _draw_table(
        page, 72, y,
        headers=["Parameter", "Value"],
        rows=[
            ["Measurement method", "Oscillometric"],
            ["Pressure range", "0–299 mmHg"],
            ["Pulse range", "40–199 bpm"],
            ["Accuracy (pressure)", "±3 mmHg"],
            ["Accuracy (pulse)", "±5%"],
            ["Power source", "4x AA batteries or 6V DC adapter"],
            ["Display", "Backlit LCD"],
        ],
        col_widths=[150, 250]
    )
    y += 10

    # 2.1.1.1 Battery Life (skipped level, changes in V2!)
    y = _write_text(page, 72, y, "2.1.1.1 Battery Life Under Typical Use", fontsize=FONT_H4, bold=True)
    y += 5
    if version == 1:
        y = _write_text(page, 72, y, "Under typical use (three measurements per day), four AA alkaline\nbatteries provide approximately 300 measurement cycles before\nrequiring replacement. The device displays a low‑battery icon once\nremaining capacity falls below 15%.", fontsize=FONT_BODY)
    else:
        y = _write_text(page, 72, y, "Under typical use (three measurements per day), four AA alkaline\nbatteries provide approximately 250 measurement cycles before\nrequiring replacement — revised downward from earlier estimates after\nextended field testing. The device displays a low‑battery icon once\nremaining capacity falls below 10%.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "2.2 Cuff Specifications", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The standard cuff supplied with the CT‑200 fits arm circumferences of\n22–32 cm. A separate large cuff (part number CT200‑LC) is available for\n32–42 cm and must be ordered separately; using the standard cuff\noutside its rated range will produce inaccurate readings.", fontsize=FONT_BODY)
    y += 20

    y = _write_text(page, 72, y, "3. Device Operation", fontsize=FONT_H1, bold=True)
    y += 5
    y = _write_text(page, 72, y, "3.1 Powering On and Profile Selection", fontsize=FONT_H2, bold=True)

    # ──────────────────────────────────────────────────────────────────
    # PAGE 3 — 3.1 continued, 3.2, 3.4 (out of order!), 3.3
    # ──────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "Press and hold the power button for one second to power on the device.\nUse the profile button to select User 1 or User 2 before beginning a\nmeasurement; readings are stored against whichever profile is active at\nthe time of measurement.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "3.2 Cuff Inflation Sequence", fontsize=FONT_H2, bold=True)
    y += 5
    if version == 1:
        y = _write_text(page, 72, y, "On starting a measurement, the device inflates the cuff to an initial target\nof 180 mmHg. If the user's pulse is not detected by 180 mmHg, the\ndevice inflates in 40 mmHg increments up to a maximum of 299 mmHg\nbefore aborting with an error. Deflation occurs in controlled steps of\napproximately 3 mmHg to capture oscillometric pulse data.", fontsize=FONT_BODY)
    else:
        y = _write_text(page, 72, y, "On starting a measurement, the device inflates the cuff to an initial target\nof 180 mmHg. If the user's pulse is not detected by 180 mmHg, the\ndevice inflates in 30 mmHg increments up to a maximum of 299 mmHg\nbefore aborting with an error. Deflation occurs in controlled steps of\napproximately 3 mmHg to capture oscillometric pulse data. Increment\nsize was reduced from the original 40 mmHg to improve pulse-detection\nreliability in field testing.", fontsize=FONT_BODY)
    y += 15

    # 3.4 Auto Shutoff (appears before 3.3 in reading order!)
    y = _write_text(page, 72, y, "3.4 Auto Shutoff", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "To conserve battery, the CT‑200 automatically powers off after 60\nseconds of inactivity on the home screen, and after 3 minutes of\ninactivity if a measurement screen is left open without starting a reading.", fontsize=FONT_BODY)
    y += 15

    # 3.3 Result Display
    y = _write_text(page, 72, y, "3.3 Result Display and Classification", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "After a completed measurement, the device displays systolic pressure,\ndiastolic pressure, and pulse rate simultaneously, along with a\nclassification indicator (see 2.1, 4.3 for related specifications and alarm\nthresholds) based on the most recent joint clinical guidance available at\ntime of manufacture.", fontsize=FONT_BODY)
    y += 5
    y = _write_text(page, 90, y, "1. Normal: systolic < 120 and diastolic < 80\n2. Elevated: systolic 120–129 and diastolic < 80\n3. Hypertension Stage 1: systolic 130–139 or diastolic 80–89\n4. Hypertension Stage 2: systolic ≥ 140 or diastolic ≥ 90\n5. Hypertensive Crisis: systolic > 180 or diastolic > 120 — device\nrecommends seeking immediate medical attention", fontsize=FONT_BODY)

    # ──────────────────────────────────────────────────────────────────
    # PAGE 4 — Section 4, 4.1, 4.2 (Table), 4.3
    # ──────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "4. Alarms and Safety Behavior", fontsize=FONT_H1, bold=True)
    y += 10

    y = _write_text(page, 72, y, "4.1 Overpressure Protection", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "If cuff pressure exceeds 299 mmHg at any point, or exceeds 300 mmHg\nfor longer than 3 seconds due to sensor fault, the device immediately\ntriggers an emergency deflation valve, halting inflation and venting the\ncuff within 2 seconds, independent of the main firmware control loop.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "4.2 Error Codes", fontsize=FONT_H2, bold=True)
    y += 5

    # Error Codes Table
    if version == 1:
        rows = [
            ["E1", "Cuff not connected or leak detected", "Aborts measurement, displays E1"],
            ["E2", "Motion artifact detected during measurement", "Aborts measurement, displays E2, prompts retry"],
            ["E3", "Overpressure condition", "Auto-deflates within 2 seconds, displays E3"],
            ["E4", "Low battery during measurement", "Aborts measurement, displays E4"],
            ["E5", "Internal sensor fault", "Device disables measurement function, displays E5 until serviced"],
        ]
    else:
        rows = [
            ["E1", "Cuff not connected or leak detected", "Aborts measurement, displays E1"],
            ["E2", "Motion artifact detected during measurement", "Aborts measurement, displays E2, prompts retry"],
            ["E3", "Overpressure condition", "Auto-deflates within 1.5 seconds, displays E3"],  # changed
            ["E4", "Low battery during measurement", "Aborts measurement, displays E4"],
            ["E5", "Internal sensor fault", "Device disables measurement function, displays E5 until serviced"],
            ["E6", "Bluetooth sync failure", "Displays E6 on next sync attempt; does not affect measurement"],  # added
        ]

    y = _draw_table(
        page, 72, y,
        headers=["Code", "Meaning", "Device Behavior"],
        rows=rows,
        col_widths=[60, 190, 200]
    )
    y += 10

    y = _write_text(page, 72, y, "4.3 Alarm Thresholds", fontsize=FONT_H2, bold=True)
    y += 5
    if version == 1:
        y = _write_text(page, 72, y, "The device does not sound an audible alarm for elevated readings by\ndefault; audible alarms are limited to the E1–E5 error conditions above\nand are user‑configurable in the settings menu, except for E3\n(overpressure), which cannot be silenced for safety reasons.", fontsize=FONT_BODY)
    else:
        y = _write_text(page, 72, y, "The device does not sound an audible alarm for elevated readings by\ndefault; audible alarms are limited to the E1–E6 error conditions above\nand are user‑configurable in the settings menu, except for E3\n(overpressure), which cannot be silenced for safety reasons.", fontsize=FONT_BODY)

    # ──────────────────────────────────────────────────────────────────
    # PAGE 5 — Section 5, 5.1, 5.2, 5.3 (V2 only), Section 6, 6.1
    # ──────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "5. Data Management", fontsize=FONT_H1, bold=True)
    y += 5

    y = _write_text(page, 72, y, "5.1 Local Storage", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The CT‑200 stores up to 100 readings per user profile in non‑volatile\nmemory. When storage is full, the oldest reading for that profile is\noverwritten automatically; there is no user‑facing warning before this\noccurs.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "5.2 Bluetooth Sync", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The device can pair with the CardioTrack companion app via Bluetooth\nLow Energy. Readings sync automatically when the app is open and the\ndevice is within range; there is no manual \"sync now\" trigger in firmware\nversion 1.x.", fontsize=FONT_BODY)
    y += 15

    if version == 2:
        y = _write_text(page, 72, y, "5.3 Data Export", fontsize=FONT_H2, bold=True)
        y += 5
        y = _write_text(page, 72, y, "Starting with firmware 1.4, the companion app supports exporting stored\nreadings as a CSV file containing timestamp, profile, systolic, diastolic,\npulse, and classification columns. Export requires the device to have\ncompleted at least one successful Bluetooth sync in the current session.", fontsize=FONT_BODY)
        y += 15

    y = _write_text(page, 72, y, "6. Maintenance and Cleaning", fontsize=FONT_H1, bold=True)
    y += 5

    y = _write_text(page, 72, y, "6.1 Cleaning Instructions", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "Wipe the device body and cuff exterior with a soft, dry cloth or one lightly\ndampened with water. Do not submerge the device or cuff, and do not\nuse alcohol, solvents, or abrasive cleaners on the display.", fontsize=FONT_BODY)

    # ──────────────────────────────────────────────────────────────────
    # PAGE 6 — 6.2, Section 7, 7.1, 7.2, Section 8, 8.1
    # ──────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "6.2 Calibration", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "Anthropic recommends professional recalibration every 2 years or after\nany drop or significant impact. The device does not perform\nself‑calibration; there is no field calibration procedure available to end\nusers.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "7. Troubleshooting", fontsize=FONT_H1, bold=True)
    y += 5

    y = _write_text(page, 72, y, "7.1 Error Codes", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "If a code from Section 4.2 appears and persists after following the\non‑screen retry prompt twice, users should discontinue use and contact\nCardioTrack support rather than attempting further self‑diagnosis,\nparticularly for E5, which indicates an internal sensor fault.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "7.2 Inconsistent Readings", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "Inconsistent readings between measurements are most commonly\ncaused by cuff mispositioning, talking or moving during measurement, or\nmeasuring within 30 minutes of exercise, caffeine, or smoking; the\nmanual recommends resting quietly for 5 minutes before remeasuring.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "8. Regulatory Information", fontsize=FONT_H1, bold=True)
    y += 5

    y = _write_text(page, 72, y, "8.1 Classification", fontsize=FONT_H2, bold=True)
    y += 5
    y = _write_text(page, 72, y, "The CT‑200 is classified as a Class II medical device under applicable\nregulations for non‑invasive blood pressure monitors and has been\nvalidated against relevant clinical accuracy standards for oscillometric\ndevices.", fontsize=FONT_BODY)

    doc.save(output_path)
    doc.close()


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    generate_ct200_pdf(1, "data/ct200_manual_v1.pdf")
    generate_ct200_pdf(2, "data/ct200_manual_v2.pdf")
    print("Generated CardioTrack CT-200 V1 and V2 PDFs successfully!")
