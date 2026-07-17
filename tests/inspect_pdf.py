"""Inspect the raw PDF structure: font sizes, text positions, block types."""

import fitz
import sys


def inspect_pdf(path: str) -> None:
    doc = fitz.open(path)
    print(f"Pages: {doc.page_count}")
    print("=" * 80)

    for page_num in range(doc.page_count):
        page = doc[page_num]
        print(f"\n{'─' * 40} PAGE {page_num + 1} {'─' * 40}")

        # Extract text with detailed info (dict mode)
        blocks = page.get_text("dict")["blocks"]
        for block_idx, block in enumerate(blocks):
            if block["type"] == 0:  # text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text:
                            continue
                        size = span["size"]
                        font = span["font"]
                        flags = span["flags"]
                        bold = bool(flags & 2**4)  # bit 4 = bold
                        italic = bool(flags & 2**1)  # bit 1 = italic
                        origin = span["origin"]
                        bbox = span["bbox"]
                        print(
                            f"  size={size:5.1f}  bold={bold!s:5s}  "
                            f"y={origin[1]:6.1f}  "
                            f"font={font:20s}  "
                            f"text={text[:60]}"
                        )
            elif block["type"] == 1:  # image block
                print(f"  [IMAGE BLOCK] bbox={block['bbox']}")

    doc.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/test_manual.pdf"
    inspect_pdf(path)
