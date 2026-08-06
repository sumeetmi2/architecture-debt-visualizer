#!/usr/bin/env python3
"""Extract slide text from a .pptx file, in slide order, with no third-party dependencies.

A .pptx is a zip of XML parts (OOXML) — ppt/slides/slideN.xml holds each slide's text
runs as <a:t> elements. This reads that directly via zipfile + xml.etree, so it works
without python-pptx being installed. Speaker notes (ppt/notesSlides/notesSlideN.xml) are
extracted separately and kept out of the main slide text, since notes are usually
private commentary, not the proposal content itself — but --include-notes exists because
sometimes the actual reasoning lives there.

Usage:
  python3 extract_pptx_text.py --pptx proposal.pptx --out proposal.txt [--include-notes]

Not for .key (Keynote) — no equivalent stdlib-only path exists; ask the user to export
to .pptx or .pdf first (the Read tool already handles PDF natively).
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
SLIDE_NUM_RE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
NOTES_NUM_RE = re.compile(r"ppt/notesSlides/notesSlide(\d+)\.xml$")


def extract_text_runs(xml_bytes):
    root = ET.fromstring(xml_bytes)
    texts = [node.text for node in root.iter(f"{A_NS}t") if node.text]
    return " ".join(t.strip() for t in texts if t.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pptx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--include-notes", action="store_true")
    args = ap.parse_args()

    slides = {}
    notes = {}
    try:
        with zipfile.ZipFile(args.pptx) as zf:
            for name in zf.namelist():
                m = SLIDE_NUM_RE.search(name)
                if m:
                    slides[int(m.group(1))] = extract_text_runs(zf.read(name))
                    continue
                if args.include_notes:
                    m = NOTES_NUM_RE.search(name)
                    if m:
                        notes[int(m.group(1))] = extract_text_runs(zf.read(name))
    except zipfile.BadZipFile:
        print(f"extract_pptx_text.py: '{args.pptx}' is not a valid .pptx (not a zip file) — "
              f"if this is a .key (Keynote) file, export to .pptx or .pdf first", file=sys.stderr)
        sys.exit(1)

    if not slides:
        print("extract_pptx_text.py: no ppt/slides/slideN.xml parts found — is this really a .pptx?", file=sys.stderr)
        sys.exit(1)

    lines = []
    for n in sorted(slides):
        lines.append(f"--- Slide {n} ---")
        lines.append(slides[n] or "(no text content)")
        if args.include_notes and n in notes and notes[n]:
            lines.append(f"[Speaker notes, slide {n}]: {notes[n]}")
        lines.append("")

    with open(args.out, "w") as fh:
        fh.write("\n".join(lines))

    print(f"extract_pptx_text.py: wrote {len(slides)} slide(s) to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
