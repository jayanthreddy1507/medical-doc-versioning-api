"""Generates a professional, print-ready PDF containing the entire project's approach,

setup guides, decision log, and submission details using PyMuPDF.
"""

import os
import fitz

OUTPUT_PATH = "data/project_submission_document.pdf"


def draw_header_footer(page, title: str, page_num: int):
    # Header
    page.draw_line(fitz.Point(54, 40), fitz.Point(558, 40), color=(0.7, 0.7, 0.7), width=0.5)
    page.insert_text(
        fitz.Point(54, 34),
        "Medical Document Versioning API — Submission Document",
        fontsize=8,
        fontname="helvetica",
        color=(0.4, 0.4, 0.4),
    )

    # Footer
    page.draw_line(fitz.Point(54, 750), fitz.Point(558, 750), color=(0.7, 0.7, 0.7), width=0.5)
    page.insert_text(
        fitz.Point(54, 762),
        "Tri9T AI — Engineering Internship Assignment",
        fontsize=8,
        fontname="helvetica",
        color=(0.4, 0.4, 0.4),
    )
    page.insert_text(
        fitz.Point(520, 762),
        f"Page {page_num}",
        fontsize=8,
        fontname="helvetica",
        color=(0.4, 0.4, 0.4),
    )


def build_pdf():
    doc = fitz.open()

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 1: COVER PAGE
    # ──────────────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)  # Letter size

    # Decorative colored sidebar banner
    page.draw_rect(fitz.Rect(0, 0, 45, 792), color=None, fill=(0.1, 0.25, 0.47), overlay=True)

    # Main Cover Text
    page.insert_textbox(
        fitz.Rect(70, 100, 540, 250),
        "MEDICAL DOCUMENT VERSIONING\n& QA TRACEABILITY API",
        fontsize=24,
        fontname="helvetica-bold",
        color=(0.1, 0.25, 0.47),
        align=0,
    )

    page.insert_textbox(
        fitz.Rect(70, 220, 540, 300),
        "Engineering Internship Assessment Project Submission Document",
        fontsize=12,
        fontname="helvetica",
        color=(0.3, 0.3, 0.3),
        align=0,
    )

    metadata_text = (
        "Candidate Details & Submission Info\n\n"
        "Applicant: JAYANTH REDDY\n"
        "Role: AI Engineering Intern Candidate\n"
        "Organization: Tri9T AI\n"
        "Date: July 2026\n"
        "Repository URL: https://github.com/jayanthreddy1507/medical-doc-versioning-api.git\n"
        "Documentation Base: docs/approach.md"
    )
    page.insert_textbox(
        fitz.Rect(70, 480, 540, 680),
        metadata_text,
        fontsize=10.5,
        fontname="helvetica",
        color=(0.2, 0.2, 0.2),
        align=0,
    )

    page.insert_text(
        fitz.Point(70, 720),
        "affine-api // compiled-submission-v1.0",
        fontsize=8,
        fontname="helvetica",
        color=(0.5, 0.5, 0.5),
    )

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2: TABLE OF CONTENTS & QUICK START
    # ──────────────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    draw_header_footer(page, "Contents", 2)

    page.insert_text(fitz.Point(54, 80), "1. Executive Summary & Setup", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))

    summary_text = (
        "The project is a complete production-grade FastAPI application engineered to tackle requirements versioning, "
        "traceability, and impact analysis in medical device development. Using an layout-aware parsing pipeline, "
        "the system extracts hierarchy trees from blood pressure monitor user manuals, persists them in a versioned relational database, "
        "enables named selections, generates QA test-case ideas via LLM integration, and implements active staleness detection.\n\n"
        "How to Setup & Run Server:\n"
        "1. Create and activate Python virtual environment:\n"
        "   python -m venv venv\n"
        "   venv\\Scripts\\activate (Windows) or source venv/bin/activate (Mac/Linux)\n"
        "2. Install all required dependencies:\n"
        "   pip install -r requirements.txt\n"
        "3. Run the development server:\n"
        "   uvicorn app.main:app --reload\n"
        "4. Interactive OpenAPI docs will be live at: http://localhost:8000/docs"
    )
    page.insert_textbox(fitz.Rect(54, 105, 558, 380), summary_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    page.insert_text(fitz.Point(54, 410), "2. Triggering the Ingestion & Revision Flow", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    flow_text = (
        "We provide a native Python script 'demo_flow.py' that walks through the entire lifecycle.\n\n"
        "To execute the E2E verification script:\n"
        "1. Ensure the FastAPI server is running in a background terminal on port 8000.\n"
        "2. Run the command in a second terminal:\n"
        "   .\\venv\\Scripts\\python.exe demo_flow.py\n\n"
        "Steps executed by the verification script:\n"
        "- Uploads ct200_manual_v1.pdf as 'ct200_manual.pdf' (registers as Document 1, Version 1).\n"
        "- Locates Node ID for Section 2.1.1.1 (Battery Life) which defines 300 cycles in V1.\n"
        "- Creates a Selection containing this node.\n"
        "- Invokes the LLM generator to create QA test cases (marked as is_stale = False).\n"
        "- Re-ingests ct200_manual_v2.pdf under the same filename 'ct200_manual.pdf' (registers as Version 2).\n"
        "- Resolves structural difference, returning unified diffs showing battery cycles reduced to 250.\n"
        "- Re-retrieves selection test cases which are now flagged as is_stale = True due to the modification.\n"
        "- Fetches generations by V2 Node ID, proving successful cross-version requirement tracing."
    )
    page.insert_textbox(fitz.Rect(54, 435, 558, 720), flow_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 3: REPO STRUCTURE & PARSER DECISIONS
    # ──────────────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    draw_header_footer(page, "Parser Decisions", 3)

    page.insert_text(fitz.Point(54, 80), "3. Repository Architecture & Layout", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    struct_text = (
        "The project is structured logically to separate layers of concern:\n"
        "- app/models/: db_models.py (relational persistence) and document.py (in-memory parsing tree).\n"
        "- app/schemas/: Pydantic validation models for input request and structured output serialization.\n"
        "- app/services/parser.py: Custom layout-aware PDF parser utilizing font size/bold metadata.\n"
        "- app/services/ingestion.py: Ingestion database coordinator and browse logic helper.\n"
        "- app/services/versioning.py: Path-based matching algorithm and history tracing engine.\n"
        "- app/services/generation.py: LLM client wrapper orchestrating structured output retries.\n"
        "- tests/: Complete automated test suite containing 47 unit and integration tests (pytest)."
    )
    page.insert_textbox(fitz.Rect(54, 105, 558, 250), struct_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    page.insert_text(fitz.Point(54, 280), "4. PDF Ingestion & Irregularity Handling", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    parser_text = (
        "Our PyMuPDF parser extracts heading level hierarchies by inspecting per-span fonts. "
        "Standard headings are distinguished by bold names ('Helvetica-Bold') and sizes from 10.5pt to 15pt, "
        "while body paragraphs use regular weights at 10.0pt. Real-world manual inconsistencies are solved as follows:\n\n"
        "- Out-of-Order Sections (e.g. section 3.4 appearing before 3.3 on page 2):\n"
        "  The parser preserves visual reading order in the database stack, preventing structural re-ordering "
        "  and registering an OUT_OF_ORDER irregularity log.\n\n"
        "- Skipped Heading Levels (e.g. jumping from 2.1 to 2.1.1.1, skipping level 3):\n"
        "  The parser links the level-4 node under its nearest existing ancestor (2.1), preserving its true level (4) "
        "  and logging a SKIPPED_LEVEL warning.\n\n"
        "- Duplicate Section Numbers (e.g. two sections labeled '4.2'):\n"
        "  To prevent overwriting, the second occurrence is appended with a suffix '4.2_dup1'. "
        "  Each node maintains distinct hashes and primary keys, allowing independent versioning and diff tracing."
    )
    page.insert_textbox(fitz.Rect(54, 305, 558, 720), parser_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 4: VERSIONING MATCHING & LLM GENERATION
    # ──────────────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    draw_header_footer(page, "Versioning & LLM", 4)

    page.insert_text(fitz.Point(54, 80), "5. Document Versioning & Matching", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    matching_text = (
        "When a new manual revision is uploaded, nodes are compared using a Hierarchical Path Matcher:\n"
        "1. Nodes are matched primarily by absolute path signatures (e.g., '/Document Root/Specifications/General').\n"
        "2. If path signatures differ (due to parent renaming), Gestalt pattern matching (SequenceMatcher) "
        "   is triggered on the heading titles under the same hierarchy level with a 70% threshold.\n"
        "3. Nodes with modified text are flagged as 'modified' and unified line-by-line diffs are created "
        "   by comparing SHA-256 content hashes.\n\n"
        "Matching Failure Modes:\n"
        "If a high-level chapter is renamed and section numbers are re-ordered simultaneously, path comparison fails. "
        "In this edge case, V1 nodes are marked as 'removed' and V2 nodes are treated as 'added', breaking history tracing."
    )
    page.insert_textbox(fitz.Rect(54, 105, 558, 290), matching_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    page.insert_text(fitz.Point(54, 320), "6. LLM Generation & Self-Repair Retry Loop", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    llm_text = (
        "The system generates 3-5 QA test cases using Pydantic structured output constraints (responseMimeType: application/json).\n\n"
        "Self-Repair Correction Loop:\n"
        "If the LLM generates malformed JSON, or fails Pydantic schema validation, the system catches the parser error, "
        "and prompts the LLM again (up to 3 times) appending the validation error message and its previous malformed text. "
        "This self-repair loop guarantees stable, structured JSON output in production.\n\n"
        "Duplicate Submission Policy:\n"
        "Repeated requests to generate test cases for the same selection ID return the cached generation immediately. "
        "This drastically reduces billing costs and api latency, while ensuring output consistency. Bypassed only when "
        "explicitly requested using force_regenerate=true."
    )
    page.insert_textbox(fitz.Rect(54, 345, 558, 550), llm_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    page.insert_text(fitz.Point(54, 570), "7. Active Staleness Detection Limits", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    stale_text = (
        "Selected nodes are linked to their exact content hashes at generation time. On retrieval, the system resolves "
        "the latest version, compares the path match content hash, and flags staleness status ('up_to_date', 'stale', 'removed').\n\n"
        "Limitations:\n"
        "- Formatting changes (e.g. layout or line breaks) change the content hash, causing false stale flags.\n"
        "- Semantic rephrasings that preserve functional equivalence trigger a stale flag (binary hash mismatch).\n"
        "- Out-of-scope shifts: a changed constraint outside the selection area goes undetected (false negative)."
    )
    page.insert_textbox(fitz.Rect(54, 595, 558, 730), stale_text, fontsize=10, fontname="helvetica", color=(0.15, 0.15, 0.15))

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 5: DECISION LOG ANSWERS
    # ──────────────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    draw_header_footer(page, "Decision Log", 5)

    page.insert_text(fitz.Point(54, 80), "8. Required Decision Log Answers", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))

    q1_title = "Q1: What's the one part of this system most likely to silently give wrong results without erroring? How would you catch it?"
    q1_body = (
        "Answer: The heading level classifier during PDF extraction. If a heading in a document uses non-standard bold flags, "
        "or slightly modified font sizes (e.g., 10.2pt instead of 10.5pt), the parser will treat the heading as body text "
        "and merge it into the preceding section's text. The tree builds successfully without throwing any errors, "
        "but the hierarchy is broken.\n"
        "How to catch it: Post-parsing validation checks. We scan extracted body paragraphs using regex. If a paragraph starts "
        "with a subsection number prefix (e.g. '^\\d+(\\.\\d+)+\\s+[A-Z]'), we flag it as a parsing anomaly warning."
    )
    page.insert_text(fitz.Point(54, 115), q1_title, fontsize=10.5, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    page.insert_textbox(fitz.Rect(54, 125, 558, 250), q1_body, fontsize=9.5, fontname="helvetica", color=(0.15, 0.15, 0.15))

    q2_title = "Q2: Where did you choose simplicity over correctness because of time, and what would break first if this went to production as-is?"
    q2_body = (
        "Answer: The custom layout-based table extractor. It relies on grouping spans strictly by identical y-coordinates "
        "with a small vertical tolerance.\n"
        "What would break first: If a table has cell blocks containing multi-line wrapped text or merged vertical headers, "
        "the extractor will treat each line of text as a separate row or merge columns incorrectly. In production, tables containing "
        "wrapped cells will be stored as garbled data rows, losing cell alignment and destroying traceability."
    )
    page.insert_text(fitz.Point(54, 275), q2_title, fontsize=10.5, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    page.insert_textbox(fitz.Rect(54, 285, 558, 410), q2_body, fontsize=9.5, fontname="helvetica", color=(0.15, 0.15, 0.15))

    q3_title = "Q3: Name one input (to your parser, your versioning matcher, or your LLM call) that you did not handle, and what your system does when it sees it."
    q3_body = (
        "Answer: A scanned/image-only PDF document containing no embedded text spans.\n"
        "What the system does: PyMuPDF's page.get_text('dict') returns an empty span list. The parser processes this as a "
        "zero-text document, creating a tree with only a root node, and returns a success status of 201 (with no children nodes "
        "and empty content). In production, this must be caught by checking if the page contains image blocks but no text, "
        "triggering an OCR pipeline fallback (e.g., Tesseract)."
    )
    page.insert_text(fitz.Point(54, 435), q3_title, fontsize=10.5, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))
    page.insert_textbox(fitz.Rect(54, 445, 558, 570), q3_body, fontsize=9.5, fontname="helvetica", color=(0.15, 0.15, 0.15))

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 6: SUBMISSION EMAIL TEMPLATE
    # ──────────────────────────────────────────────────────────────────────────
    page = doc.new_page(width=612, height=792)
    draw_header_footer(page, "Email Template", 6)

    page.insert_text(fitz.Point(54, 80), "9. Project Submission Email Template", fontsize=14, fontname="helvetica-bold", color=(0.1, 0.25, 0.47))

    email_body = (
        "To: careers@tri9t.ai\n"
        "Subject: AI Engineering Intern Submission - JAYANTH REDDY\n\n"
        "Dear Tri9T AI Hiring Team,\n\n"
        "I am pleased to submit my entry for the AI Engineering Internship Assessment project. "
        "I have built a robust document parsing, versioning, and test-case generation backend "
        "satisfying all core requirements, including the edge cases present in the CT-200 manual.\n\n"
        "Key Project Links:\n"
        "- GitHub Repository URL:\n"
        "  https://github.com/jayanthreddy1507/medical-doc-versioning-api.git\n"
        "- Technical Approach Document:\n"
        "  https://github.com/jayanthreddy1507/medical-doc-versioning-api/blob/main/docs/approach.md\n\n"
        "Features Implemented:\n"
        "1. PyMuPDF layout-aware tree parser handling out-of-order, duplicates, and skipped levels.\n"
        "2. Hierarchical path-based & fuzzy SequenceMatcher version matching engine with unified diffs.\n"
        "3. Named, version-pinned Selections API.\n"
        "4. LLM QA generator with Pydantic JSON validation and self-repair loops (retries with error logs).\n"
        "5. SQLite database using native JSON extensions as our light NoSQL test-cases store.\n"
        "6. Active staleness/impact detection on selection retrievals and cross-version node tracing.\n"
        "7. Complete E2E verification script (demo_flow.py) validating the versioning lifecycle.\n"
        "8. Fully documented Decision Log answers addressing parser edge-cases and limitations.\n\n"
        "Thank you for this opportunity, and I look forward to walking you through my implementation and design choices!\n\n"
        "Best regards,\n"
        "JAYANTH REDDY\n"
        "jayanthreddy1507@gmail.com"
    )
    page.insert_textbox(fitz.Rect(54, 110, 558, 730), email_body, fontsize=9.5, fontname="helvetica", color=(0.15, 0.15, 0.15))

    # Save to disk
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc.save(OUTPUT_PATH)
    doc.close()
    print(f"[OK] PDF successfully generated at: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
