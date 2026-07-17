# Version Matching Strategy & Diff Engine

> This document details the architectural decisions and strategy used to match document versions and compute hierarchical differences.

---

## Strategy Selection

The matching engine matches nodes between an older version (V1) and a newer version (V2) of a document.
We evaluated several strategies:

| Strategy | Pros | Cons |
|----------|------|------|
| **Exact Path + Title Match (Selected)** | Extremely stable under renumbering, handles moved nodes, low computation overhead. | Fails if parent sections are renamed. |
| **Section Number Match** | Trivial to implement. | Breaks completely if a section is inserted/deleted (renumbering cascades). |
| **Content Hash Match** | Identifies identical sections instantly. | Cannot match sections if a single word or character changes. |
| **Fuzzy Title / Semantic Match** | Matches sections if typos or minor wording changes occur. | Risk of false matches for generic titles. |

### The Hybrid Hierarchical Strategy

We implement a **hierarchical fallback matcher** that operates recursively down the tree:

1. **Normalized Title Match**:
   - Compare the child list of matched parent nodes. If a child in V2 has the exact same title as a child in V1, they are matched. This is highly robust against section renumbering (e.g. `3.4 Auto Shutoff` in V1 matches `3.4 Auto Shutoff` in V2 even if it moves or gets renumbered).
2. **Section Number Fallback**:
   - If titles don't match, we check if they share the same section number. This helps match a section if its title was refined (e.g., `"General Specifications"` -> `"General System Specifications"`).
3. **Fuzzy Title Match Fallback**:
   - Compute title similarity using the Gestalt pattern matching algorithm via Python's built-in `difflib.SequenceMatcher`. If similarity is $\ge 70\%$, they are matched.
4. **Structural Adjacency Fallback**:
   - Unmatched V2 nodes under the parent are marked as `added`.
   - Unmatched V1 nodes under the parent are marked as `removed`.

---

## Diff Classification Rules

Once nodes are matched, their status is classified:

- **`added`**: Present in V2, but was not matched to any V1 node.
- **`removed`**: Present in V1, but was not matched to any V2 node.
- **`modified`**: Present in both, but `content_hash` differs.
- **`unchanged`**: Present in both, and `content_hash` is identical.

### Propagating Change Flags

If a leaf node is modified, added, or removed, we propagate the status up to its ancestors:
- If a parent node is otherwise `unchanged`, but one or more of its descendants have changes, the parent's status is changed to `modified`.
- This ensures that if a user views a high-level section, they are immediately alerted that a subsection beneath it was modified.

---

## Where It Breaks (Known Failure Modes)

While highly robust, this strategy has specific structural limits:

### 1. Significant Parent Renaming / Restructuring
- **Scenario**: A top-level section is renamed (e.g. `"Device Operation"` $\rightarrow$ `"Operating the System"`).
- **Behavior**: Because matching is anchored on matching parents first, renaming a parent node breaks path/title matching for that node. The entire subtree (including unmodified children) might be marked as `removed` from their old location and `added` under the new parent.
- **Mitigation**: We mitigate this by matching the parent using fuzzy title matching ($70\%$). If the parent matches fuzzily, the children matching anchors correctly. However, if the name changes completely (e.g., `"Alarms"` $\rightarrow$ `"System Safety Functions"`), it will break.

### 2. Splitting a Section
- **Scenario**: Section `"Device Specs"` containing both dimensions and battery info is split into `"Dimensions"` and `"Battery Info"`.
- **Behavior**: The matcher will fuzzy-match one of the new sections to the old one (whichever has the most similar title/content) and mark the other as `added`. It cannot track the "1-to-many" split relationship cleanly.

### 3. Duplicate Section Titles under Different Parents
- **Scenario**: Two different parent sections both have a child named `"General Specifications"`.
- **Behavior**: The hierarchical match handles this correctly because it only compares sibling nodes under the *same matched parent*. However, if both parents are renamed, cross-parent matching would fail.
