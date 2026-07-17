# Approach & Design Decisions Document

> **Medical Document Versioning API**  
> Design documentation, technical approach, failure modes analysis, and decision log.

---

## 1. Technical Stack Decisions

### Backend Framework: FastAPI
- **Decision**: FastAPI (Python)
- **Rationale**: Async-first, high performance, native integration with Pydantic v2 for request/response validation, and auto-generated interactive OpenAPI/Swagger documentation.
- **Alternatives Considered**: Flask (rejected due to lack of native async/validation) and NestJS (rejected to prioritize python-native data science/parser libraries).

### Persistence & ORM: SQLite + SQLAlchemy 2.0 (Async)
- **Decision**: SQLAlchemy (using `asyncio` and `aiosqlite`) to manage SQLite storage.
- **Rationale**: SQLite is zero-configuration and perfectly suited for development. SQLAlchemy 2.0 provides clean Mapped types and relational integrity for parent-child tree mapping.
- **JSON Store**: The database uses SQLite JSON-extensions in the `generations` table to store LLM prompts, outputs, and content hashes, satisfying the NoSQL requirements in a single, self-contained file.

---

## 2. PDF Parsing & Hierarchy Extraction

### Extraction Strategy: PyMuPDF (`fitz`)
We chose **PyMuPDF** over alternatives (like `pdfplumber` or OCR models) because it provides detailed per-span metadata (font name, size, bold flag, bounding boxes) and is 10-50x faster. Heading detection is based on:
1. **Bold Flag**: Headings are always bold (`NimbusSans-Bold`).
2. **Font Size**: Font size thresholds (H1 = 15.0, H2 = 13.0, H3 = 11.5, H4 = 10.5). Body text is regular at 10.0pt.
3. **Numbering Pattern**: Regex verification (e.g., `^(\d+(\.\d+)*)\.?$`).

### Custom Table Parser
Tables are extracted by:
- Filtering spans with font size $\le 9.5$ (TABLE_MAX_SIZE).
- Clustering text spans on the same horizontal axis (y-coordinate) within a `2.0pt` tolerance to group columns.
- Header rows are identified by the bold flag, while data rows use the regular font variant.

### Irregularity Resolution Strategy
Real-world manuals (such as the CT-200 manual) contain significant structural inconsistencies. Our parser resolves them as follows:

| Irregularity | Description in CT-200 Manual | Parser Handling |
| --- | --- | --- |
| **Out-of-Order Sections** | `3.4 Auto Shutoff` appears *before* `3.3 Result Display` on Page 2 in reading order. | Preserves **reading order** in the tree representation rather than sorting numerically. Logs `OUT_OF_ORDER` warning. |
| **Skipped Heading Levels** | Jumping from H2 (`2.1 Analyzer Unit`) directly to H4 (`2.1.1.1 Electrode Specifications`) skipping H3. | Nestles the node under the nearest ancestor (`2.1`), keeping its level as 4. Logs `SKIPPED_LEVEL` warning. |
| **Duplicate Numbering** | Multiple sections labeled `4.2` (`Error Codes` and `Warning Indicators`). | Disambiguates by renaming the second section number to `4.2_dup1`. Both retain unique DB records and content hashes. Logs `DUPLICATE_NUMBER` warning. |

---

## 3. Version Matching Strategy

When a modified manual is re-ingested (e.g., `v1` $\rightarrow$ `v2`), we use a **Hierarchical Path-based Matching Strategy**:

1. **Path Signatures**: We construct an absolute path string for every node (e.g., `/Document Root/General Specifications/Battery Life`).
2. **First-Pass Match**: If a node in V2 has the exact same path signature as a node in V1, they are matched.
3. **Second-Pass Fuzzy Match**: If a path match fails (due to parent renaming or minor heading changes), we run **Gestalt pattern matching** on titles under the same level with a $70\%$ threshold.
4. **Change Classification**:
   - `added`: Node exists in V2 but not in V1.
   - `removed`: Node exists in V1 but not in V2.
   - `modified`: Node exists in both but their `content_hash` differs.
   - `unchanged`: Node exists in both and content hash is identical.

### Known Failure Modes
- **Renaming + Shifting Parent**: If a level-1 chapter name is renamed and section numbers are re-ordered simultaneously, path signatures break. Fallbacks are triggered, but if they both mutate heavily, V1 nodes are flagged as `removed` and V2 nodes are treated as new `added` items, breaking historical continuity.

---

## 4. LLM Generation & Staleness Detection

### Prompt Design
The prompt models a **medical device software QA Engineer** to demand high safety compliance. It injects a reconstructed context of the selected nodes and strictly enforces Pydantic-based structured JSON output (`QAGenerationResponse`).

### Failure Handling & Self-Repair Retry Loop
If the LLM output is malformed, incomplete, or fails the Pydantic schema verification:
- The system catches the parser exception.
- It triggers a **self-repair loop** (up to 3 retries): resends the prompt, appending the malformed text and the validation error message, instructing the model to repair its JSON structure.
- If it still fails, raises an HTTP 502 Bad Gateway error.

### Caching and Duplicate Policy
- **Cache Hit (Default)**: Repeated calls to generate test cases for the same selection ID return the cached output immediately. This avoids redundant billing and latency.
- **Forced Regeneration**: The user can pass `force_regenerate=true` to override the cache, invoke the LLM, and register a new generation record.

### Staleness Limits
Staleness checks identify if generated test cases are out-of-sync with the latest document version:
- **What it detects**: Text updates, deletions, and paragraph expansions.
- **Limits**:
  - **Formatting Noise**: Pure styling layout modifications (e.g., margins/line-breaks changing text spans) mutate the content hash and flag the node as stale (false positive).
  - **Semantic Equivalence**: Sentence rephrasings that maintain identical requirements trigger a stale flag because binary hashes differ.
  - **Out-of-Scope Impacts**: If a related requirement changes outside the selected scope, the selected node reports `up_to_date` (false negative).

---

## 5. Decision Log (Required Answers)

### Question 1
> *What's the one part of this system most likely to silently give wrong results without erroring? How would you catch it?*

- **Answer**: The heading level classifier during PDF parsing. If a heading uses non-standard bold flags or slightly modified font sizes (e.g., 10.2pt instead of 10.5pt), the parser will treat the heading line as body text and merge it into the preceding section's text. The tree is built successfully without throwing any errors, but the hierarchy is broken.
- **How to catch it**: Post-parsing validation checks. We can scan all extracted body paragraphs using regex to check if they start with section numbering strings (e.g., `^\d+(\.\d+)+\s+[A-Z]`). If a paragraph begins with a subsection number prefix, it is flagged as a parsing anomaly warning.

### Question 2
> *Where did you choose simplicity over correctness because of time, and what would break first if this went to production as-is?*

- **Answer**: The custom layout-based table extractor. It relies on grouping spans strictly by identical y-coordinates (with a small vertical tolerance).
- **What would break first**: If a table has cell blocks containing multi-line wrapped text or merged vertical headers, the extractor will treat each line of text as a separate row or merge columns incorrectly. In production, tables containing wrapped cells will be stored as garbled data rows, losing cell alignment and destroying traceability.

### Question 3
> *Name one input (to your parser, your versioning matcher, or your LLM call) that you did not handle, and what your system does when it sees it.*

- **Answer**: A scanned/image-only PDF document containing no embedded text spans.
- **What the system does**: PyMuPDF's `page.get_text("dict")` returns an empty span list. The parser processes this as a zero-text document, creating a tree with only a root node, and returns a success status of 201 (with no children nodes and empty content). In production, this must be caught by checking if the page contains image blocks but no text, triggering an OCR pipeline fallback (e.g., Tesseract).
