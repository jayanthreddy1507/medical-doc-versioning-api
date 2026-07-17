# Staleness & Impact Detection Limits

> This document details how staleness is detected, what it successfully tracks, and the inherent engineering limitations of hashing-based impact analysis.

---

## 1. How Staleness Detection Works

When test cases are generated for a selection, the system snapshots the `content_hash` of each selected node in the database. 
Upon retrieval (via Selection ID or Node ID), the system:
1. Resolves the latest version of the parent document.
2. Identifies the matching nodes in the latest version by reconstructed absolute paths (e.g. `/Document Root/Specifications/Battery Life`) with a fallback to section number + title signatures.
3. Compares the current content hash of the matching node with the hash recorded at generation time.
4. Marks the node status as:
   - `up_to_date`: Node exists in the latest version and content hash is identical.
   - `stale`: Node exists but content hash differs (text changed).
   - `removed`: Node no longer exists in the latest version.
5. Flags the entire generation as `is_stale = True` if any single selected node is `stale` or `removed`.

---

## 2. Inherent Limitations: Where the System Breaks

While content-hash tracking is robust and deterministic, it has several critical engineering limitations:

### A. Formatting and Whitespace Noise (False Positives)
- **Problem**: Our PDF parser extracts raw character sequences. If a newer manual layout changes line breaks, adds extra whitespace, or converts hyphens to non-breaking hyphens, the `content_hash` changes.
- **Impact**: The generation is flagged as `stale` even though the functional requirement and text meaning are 100% identical.

### B. Parent Node Renaming
- **Problem**: Our primary lookup uses absolute paths. If a high-level chapter is renamed (e.g. `"2. Physical Specs"` $\rightarrow$ `"2. Hardware Specs"`), the path signatures of all its descendant sub-headings change.
- **Impact**: Although section-number fallbacks are implemented, if a parent heading is renamed and section numbering is shifted simultaneously, the system will fail to match the nodes, marking them as `removed` and rendering the entire generation stale.

### C. Semantic Equivalence vs. String Mutation
- **Problem**: Hash comparison is binary. It cannot detect when words change but functional meaning is preserved.
  - *Example*: `"AA alkaline batteries provide approximately 300 cycles"` vs `"Four AA batteries support roughly 300 measurement cycles"`.
- **Impact**: The content hash changes, causing a `stale` flag, even though the generated QA test cases remain completely accurate.

### D. Indirect/Out-of-Scope Impact (False Negatives)
- **Problem**: The system only verifies the hashes of the selected nodes.
- **Impact**: If a related requirement changes in a section *outside* the selection, the selection's own nodes report `up_to_date`, but the generated test cases are now functionally incorrect or obsolete due to global document contradictions.
