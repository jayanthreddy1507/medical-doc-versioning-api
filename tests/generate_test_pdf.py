"""Generate a realistic medical device manual PDF with known irregularities.

This creates a test PDF that exercises every edge case the parser must handle:
  1. Out-of-order subsections (3.4 appears before 3.3 in reading order)
  2. Skipped heading levels (2.1.1.1 with no 2.1.1)
  3. Duplicate numbering (two sections labeled 4.2)
  4. Tables embedded in sections
  5. Multi-page content
  6. Varying font sizes for heading hierarchy
  7. Bold vs regular font weight differences
"""

import fitz  # PyMuPDF


# ── Font size constants (mimic a real medical manual) ───────────────────
FONT_TITLE = 18
FONT_H1 = 15
FONT_H2 = 13
FONT_H3 = 11.5
FONT_H4 = 10.5
FONT_BODY = 10
FONT_TABLE = 9

# ── Colors ──────────────────────────────────────────────────────────────
BLACK = (0, 0, 0)
DARK_GRAY = (0.2, 0.2, 0.2)
TABLE_BORDER = (0.4, 0.4, 0.4)
TABLE_HEADER_BG = (0.9, 0.9, 0.95)


def _write_text(
    page: fitz.Page,
    x: float,
    y: float,
    text: str,
    fontsize: float = FONT_BODY,
    bold: bool = False,
    color: tuple = BLACK,
) -> float:
    """Write text at (x, y) and return the new y position after the text."""
    fontname = "helv" if not bold else "hebo"
    # fitz uses "helv" for Helvetica regular, "hebo" for Helvetica-Bold
    tw = fitz.TextWriter(page.rect)
    try:
        tw.append((x, y), text, fontsize=fontsize, font=fitz.Font(fontname))
    except Exception:
        # Fallback if font not available
        tw.append((x, y), text, fontsize=fontsize)
    tw.write_text(page, color=color)
    line_count = text.count("\n") + 1
    return y + (fontsize * 1.4 * line_count)


def _draw_table(
    page: fitz.Page,
    x: float,
    y: float,
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float],
) -> float:
    """Draw a simple table and return the y position after it."""
    row_height = 18
    shape = page.new_shape()

    # Header row
    cur_x = x
    for i, header in enumerate(headers):
        rect = fitz.Rect(cur_x, y, cur_x + col_widths[i], y + row_height)
        shape.draw_rect(rect)
        shape.finish(color=TABLE_BORDER, fill=TABLE_HEADER_BG)
        _write_text(page, cur_x + 4, y + 13, header, fontsize=FONT_TABLE, bold=True)
        cur_x += col_widths[i]
    y += row_height

    # Data rows
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


def generate_test_pdf(output_path: str) -> str:
    """Generate a medical device manual PDF with intentional irregularities.

    Returns the output file path.

    Irregularities embedded:
      1. Section 3.4 "Auto Shutoff" appears BEFORE 3.3 "Result Display"
      2. Section 2.1.1.1 "Electrode Specs" exists without 2.1.1
      3. Two sections numbered 4.2 (duplicate numbering)
      4. Tables in sections 4.2 (error codes) and 5.1 (maintenance schedule)
      5. Content spans multiple pages
    """
    doc = fitz.open()

    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 1 — Title page + Section 1
    # ═══════════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)  # US Letter
    y = 80

    # Title
    y = _write_text(page, 72, y, "MedDevice Pro X200", fontsize=FONT_TITLE, bold=True)
    y += 5
    y = _write_text(page, 72, y, "User Manual — Revision 3.1", fontsize=FONT_H2)
    y += 5
    y = _write_text(
        page, 72, y, "Document ID: MDX200-UM-2024-03", fontsize=FONT_BODY
    )
    y += 20

    # Section 1 — Introduction
    y = _write_text(page, 72, y, "1  Introduction", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "The MedDevice Pro X200 is a portable blood glucose monitoring system",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "designed for professional clinical use. This manual covers operation,",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "maintenance, and troubleshooting procedures.",
        fontsize=FONT_BODY,
    )
    y += 15

    # Section 1.1
    y = _write_text(page, 72, y, "1.1  Intended Use", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "This device is intended for in-vitro diagnostic use by healthcare",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "professionals in clinical laboratory and point-of-care settings.",
        fontsize=FONT_BODY,
    )
    y += 15

    # Section 1.2
    y = _write_text(
        page, 72, y, "1.2  Contraindications", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Do not use this device for neonatal screening without additional",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "calibration per Protocol NB-400.",
        fontsize=FONT_BODY,
    )
    y += 20

    # Section 2 — Components
    y = _write_text(page, 72, y, "2  Components", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "The X200 system consists of the analyzer unit, test strips, and",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page, 72, y, "control solution.", fontsize=FONT_BODY
    )
    y += 15

    # Section 2.1
    y = _write_text(page, 72, y, "2.1  Analyzer Unit", fontsize=FONT_H2, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "The analyzer unit houses the optical sensor, microprocessor, and",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page, 72, y, "LCD display module.", fontsize=FONT_BODY
    )
    y += 15

    # ── IRREGULARITY #2: Skipped heading level ──
    # 2.1.1.1 exists WITHOUT a 2.1.1 parent
    y = _write_text(
        page,
        72,
        y,
        "2.1.1.1  Electrode Specifications",
        fontsize=FONT_H4,
        bold=True,
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Platinum-coated carbon electrodes with 0.5mm spacing. Impedance",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "range: 100-500 ohms at 1kHz test frequency.",
        fontsize=FONT_BODY,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 2 — Section 3 with out-of-order subsections
    # ═══════════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "3  Operation", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Follow these procedures for standard glucose measurement.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 3.1
    y = _write_text(
        page, 72, y, "3.1  Power On Sequence", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Press and hold the power button for 2 seconds. The device performs",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "a self-test displaying firmware version and last calibration date.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 3.2
    y = _write_text(
        page, 72, y, "3.2  Sample Application", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Apply 0.5 uL of whole blood to the test strip sample port.",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "The device will beep when sufficient sample is detected.",
        fontsize=FONT_BODY,
    )
    y += 15

    # ── IRREGULARITY #1: 3.4 appears BEFORE 3.3 in reading order ──
    y = _write_text(
        page, 72, y, "3.4  Auto Shutoff", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "The device automatically powers off after 3 minutes of inactivity",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "to conserve battery life. All results are saved before shutdown.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 3.3 comes AFTER 3.4 — out of numeric order
    y = _write_text(
        page, 72, y, "3.3  Result Display", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Results appear within 5 seconds. Values are displayed in mg/dL",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "or mmol/L depending on device configuration.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 3.3.1
    y = _write_text(
        page,
        72,
        y,
        "3.3.1  Display Symbols",
        fontsize=FONT_H3,
        bold=True,
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "HI = result above measurable range (>600 mg/dL).",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "LO = result below measurable range (<20 mg/dL).",
        fontsize=FONT_BODY,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 3 — Section 4 with duplicate numbering + tables
    # ═══════════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "4  Troubleshooting", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Refer to the following sections for common issues.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 4.1
    y = _write_text(
        page, 72, y, "4.1  Error Messages", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Error codes are displayed as E followed by a three-digit number.",
        fontsize=FONT_BODY,
    )
    y += 15

    # ── IRREGULARITY #3: First 4.2 — Error Code Table ──
    y = _write_text(
        page,
        72,
        y,
        "4.2  Error Code Reference",
        fontsize=FONT_H2,
        bold=True,
    )
    y += 5

    # Table: Error codes
    y = _draw_table(
        page,
        x=72,
        y=y,
        headers=["Code", "Description", "Action"],
        rows=[
            ["E001", "Strip not detected", "Reinsert test strip"],
            ["E002", "Insufficient sample", "Apply more blood"],
            ["E003", "Temperature out of range", "Move to 15-40C environment"],
            ["E004", "Battery critically low", "Replace batteries"],
            ["E005", "Sensor malfunction", "Contact service"],
        ],
        col_widths=[80, 180, 200],
    )
    y += 10

    # ── IRREGULARITY #3 continued: Second 4.2 — DUPLICATE ──
    y = _write_text(
        page,
        72,
        y,
        "4.2  Warning Indicators",
        fontsize=FONT_H2,
        bold=True,
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Warning indicators are shown as yellow triangles on the display.",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "These do not prevent measurement but may affect accuracy.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 4.3
    y = _write_text(
        page, 72, y, "4.3  Factory Reset", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Hold Power + Mode buttons for 10 seconds to reset all settings.",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "WARNING: This erases all stored results and calibration data.",
        fontsize=FONT_BODY,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # PAGE 4 — Section 5 with maintenance table
    # ═══════════════════════════════════════════════════════════════════════
    page = doc.new_page(width=612, height=792)
    y = 72

    y = _write_text(page, 72, y, "5  Maintenance", fontsize=FONT_H1, bold=True)
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Regular maintenance ensures measurement accuracy and device longevity.",
        fontsize=FONT_BODY,
    )
    y += 15

    # 5.1
    y = _write_text(
        page,
        72,
        y,
        "5.1  Maintenance Schedule",
        fontsize=FONT_H2,
        bold=True,
    )
    y += 5

    # Table: Maintenance schedule
    y = _draw_table(
        page,
        x=72,
        y=y,
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

    # 5.2
    y = _write_text(
        page, 72, y, "5.2  Cleaning Procedure", fontsize=FONT_H2, bold=True
    )
    y += 3
    y = _write_text(
        page,
        72,
        y,
        "Power off the device before cleaning. Use only approved cleaning",
        fontsize=FONT_BODY,
    )
    y += 2
    y = _write_text(
        page,
        72,
        y,
        "agents listed in Appendix B. Do not immerse the device.",
        fontsize=FONT_BODY,
    )

    # ── Save ────────────────────────────────────────────────────────────
    doc.save(output_path)
    doc.close()

    return output_path


if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "..", "..", "data", "test_manual.pdf")
    out = os.path.abspath(out)
    generate_test_pdf(out)
    print(f"Generated: {out}")
