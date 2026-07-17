"""Generate a v2 of the medical device manual with deliberate changes.

Changes from v1:
  1. MODIFIED: Section 1.1 — Intended Use updated (expanded scope)
  2. MODIFIED: Section 3.1 — Power On Sequence (changed from 2 to 3 seconds)
  3. ADDED:   Section 3.5 — Data Export (entirely new section)
  4. REMOVED: Section 4.3 — Factory Reset (deleted)
  5. MOVED:   Section 3.3 now appears BEFORE 3.4 (order fixed from v1)
  6. UNCHANGED: Sections 1, 1.2, 2, 2.1, 2.1.1.1, 3.2, 3.3.1, 3.4, 4.1, 4.2, 5, 5.1, 5.2
  7. MODIFIED: Error code table — E003 action changed
  8. ADDED:   New error code E006 to the table
"""

import fitz


# Font constants (same as v1)
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
    tw = fitz.TextWriter(page.rect)
    try:
        tw.append((x, y), text, fontsize=fontsize, font=fitz.Font(fontname))
    except Exception:
        tw.append((x, y), text, fontsize=fontsize)
    tw.write_text(page, color=color)
    line_count = text.count("\n") + 1
    return y + (fontsize * 1.4 * line_count)


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


def generate_test_pdf_v2(output_path: str) -> str:
    """Generate v2 of the medical device manual with known changes from v1.

    Returns the output file path.
    """
    doc = fitz.open()

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 1 — Title + Section 1, 2 (with modifications)
    # ═══════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 80

    y = _write_text(page, 72, y, "MedDevice Pro X200", fontsize=FONT_TITLE, bold=True)
    y += 5
    # CHANGE: Revision bumped to 4.0
    y = _write_text(page, 72, y, "User Manual — Revision 4.0", fontsize=FONT_H2)
    y += 5
    y = _write_text(page, 72, y, "Document ID: MDX200-UM-2024-07", fontsize=FONT_BODY)
    y += 20

    # Section 1 — UNCHANGED
    y = _write_text(page, 72, y, "1  Introduction", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(page, 72, y, "The MedDevice Pro X200 is a portable blood glucose monitoring system", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "designed for professional clinical use. This manual covers operation,", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "maintenance, and troubleshooting procedures.", fontsize=FONT_BODY)
    y += 15

    # Section 1.1 — MODIFIED (expanded scope)
    y = _write_text(page, 72, y, "1.1  Intended Use", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "This device is intended for in-vitro diagnostic use by healthcare", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "professionals in clinical, point-of-care, and home-care settings.", fontsize=FONT_BODY)
    y += 2
    # ADDED LINE: new capability
    y = _write_text(page, 72, y, "Now supports continuous glucose monitoring (CGM) mode.", fontsize=FONT_BODY)
    y += 15

    # Section 1.2 — UNCHANGED
    y = _write_text(page, 72, y, "1.2  Contraindications", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Do not use this device for neonatal screening without additional", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "calibration per Protocol NB-400.", fontsize=FONT_BODY)
    y += 20

    # Section 2 — UNCHANGED
    y = _write_text(page, 72, y, "2  Components", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(page, 72, y, "The X200 system consists of the analyzer unit, test strips, and", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "control solution.", fontsize=FONT_BODY)
    y += 15

    # Section 2.1 — UNCHANGED
    y = _write_text(page, 72, y, "2.1  Analyzer Unit", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "The analyzer unit houses the optical sensor, microprocessor, and", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "LCD display module.", fontsize=FONT_BODY)
    y += 15

    # Section 2.1.1.1 — UNCHANGED (still has skipped level)
    y = _write_text(page, 72, y, "2.1.1.1  Electrode Specifications", fontsize=FONT_H4, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Platinum-coated carbon electrodes with 0.5mm spacing. Impedance", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "range: 100-500 ohms at 1kHz test frequency.", fontsize=FONT_BODY)

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 2 — Section 3 (order FIXED: 3.3 now before 3.4 + new 3.5)
    # ═══════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "3  Operation", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Follow these procedures for standard glucose measurement.", fontsize=FONT_BODY)
    y += 15

    # 3.1 — MODIFIED (changed from 2 seconds to 3 seconds)
    y = _write_text(page, 72, y, "3.1  Power On Sequence", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Press and hold the power button for 3 seconds. The device performs", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "a self-test displaying firmware version and last calibration date.", fontsize=FONT_BODY)
    y += 15

    # 3.2 — UNCHANGED
    y = _write_text(page, 72, y, "3.2  Sample Application", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Apply 0.5 uL of whole blood to the test strip sample port.", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "The device will beep when sufficient sample is detected.", fontsize=FONT_BODY)
    y += 15

    # 3.3 — NOW IN CORRECT ORDER (was after 3.4 in v1) — content UNCHANGED
    y = _write_text(page, 72, y, "3.3  Result Display", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Results appear within 5 seconds. Values are displayed in mg/dL", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "or mmol/L depending on device configuration.", fontsize=FONT_BODY)
    y += 15

    # 3.3.1 — UNCHANGED
    y = _write_text(page, 72, y, "3.3.1  Display Symbols", fontsize=FONT_H3, bold=True)
    y += 3
    y = _write_text(page, 72, y, "HI = result above measurable range (>600 mg/dL).", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "LO = result below measurable range (<20 mg/dL).", fontsize=FONT_BODY)
    y += 15

    # 3.4 — UNCHANGED content (but now AFTER 3.3, order fixed)
    y = _write_text(page, 72, y, "3.4  Auto Shutoff", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "The device automatically powers off after 3 minutes of inactivity", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "to conserve battery life. All results are saved before shutdown.", fontsize=FONT_BODY)
    y += 15

    # 3.5 — ADDED (new section)
    y = _write_text(page, 72, y, "3.5  Data Export", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Connect the device via USB-C to export results to a computer.", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "Compatible with MedDevice DataManager v2.0 and later.", fontsize=FONT_BODY)

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 3 — Section 4 (4.3 REMOVED, table MODIFIED)
    # ═══════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "4  Troubleshooting", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Refer to the following sections for common issues.", fontsize=FONT_BODY)
    y += 15

    # 4.1 — UNCHANGED
    y = _write_text(page, 72, y, "4.1  Error Messages", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Error codes are displayed as E followed by a three-digit number.", fontsize=FONT_BODY)
    y += 15

    # 4.2 — MODIFIED table (E003 action changed, E006 added)
    y = _write_text(page, 72, y, "4.2  Error Code Reference", fontsize=FONT_H2, bold=True)
    y += 5
    y = _draw_table(
        page, x=72, y=y,
        headers=["Code", "Description", "Action"],
        rows=[
            ["E001", "Strip not detected", "Reinsert test strip"],
            ["E002", "Insufficient sample", "Apply more blood"],
            ["E003", "Temperature out of range", "Wait 10 min then retry"],  # CHANGED
            ["E004", "Battery critically low", "Replace batteries"],
            ["E005", "Sensor malfunction", "Contact service"],
            ["E006", "CGM sensor expired", "Replace CGM sensor"],  # NEW
        ],
        col_widths=[80, 180, 200],
    )
    y += 10

    # 4.2 duplicate — UNCHANGED
    y = _write_text(page, 72, y, "4.2  Warning Indicators", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Warning indicators are shown as yellow triangles on the display.", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "These do not prevent measurement but may affect accuracy.", fontsize=FONT_BODY)

    # NOTE: Section 4.3 (Factory Reset) is REMOVED in v2

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 4 — Section 5 (UNCHANGED)
    # ═══════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "5  Maintenance", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Regular maintenance ensures measurement accuracy and device longevity.", fontsize=FONT_BODY)
    y += 15

    y = _write_text(page, 72, y, "5.1  Maintenance Schedule", fontsize=FONT_H2, bold=True)
    y += 5
    y = _draw_table(
        page, x=72, y=y,
        headers=["Task", "Frequency", "Procedure"],
        rows=[
            ["Clean sensor", "Weekly", "Use lint-free cloth with 70% IPA"],
            ["Run QC test", "Daily", "Use Level 1 and Level 2 controls"],
            ["Replace batteries", "Monthly", "Use only AA lithium cells"],
            ["Calibration check", "Quarterly", "Send to authorized service"],
        ],
        col_widths=[120, 120, 220],
    )
    y += 10

    y = _write_text(page, 72, y, "5.2  Cleaning Procedure", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(page, 72, y, "Power off the device before cleaning. Use only approved cleaning", fontsize=FONT_BODY)
    y += 2
    y = _write_text(page, 72, y, "agents listed in Appendix B. Do not immerse the device.", fontsize=FONT_BODY)

    doc.save(output_path)
    doc.close()
    return output_path
