"""
HP (Högskoleprovet) Question Extractor
- Parses all provpass PDFs for questions (XYZ, KVA, NOG, DTK, ORD, LAS, MEK, ELF)
- Parses all facit PDFs for correct answers
- Saves LAS/ELF passage texts to texts/ folder, referenced in JSON
- Renders DTK diagram pages to images/ folder, referenced in JSON
- Deduplicates and validates
- Output: hp_questions.json next to this script
"""

import os
import re
import json
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

import fitz        # PyMuPDF
import pdfplumber  # fallback text extractor

BASE_DIR    = Path(__file__).resolve().parent
INPUT_DIR   = BASE_DIR / "Gamla_HP"
IMAGES_DIR  = BASE_DIR / "images"
_LOCAL      = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HPOvning"
_LOCAL.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = _LOCAL / "hp_questions.json"
TEXTS_DIR   = _LOCAL / "texts"
TEXTS_DIR.mkdir(parents=True, exist_ok=True)

# ── section header patterns ──────────────────────────────────────────────────
SECTION_PATTERNS = [
    (re.compile(r"^XYZ\b"),                        "XYZ"),
    (re.compile(r"^Matematisk probleml", re.I),    "XYZ"),
    (re.compile(r"^KVA\b"),                        "KVA"),
    (re.compile(r"^Kvantitativa j",      re.I),    "KVA"),
    (re.compile(r"^NOG\b"),                        "NOG"),
    (re.compile(r"^Kvantitativa res",    re.I),    "NOG"),
    (re.compile(r"^DTK\b"),                        "DTK"),
    (re.compile(r"^Diagram,?\s+tabeller",re.I),    "DTK"),
    (re.compile(r"^ORD\b"),                        "ORD"),
    (re.compile(r"^Ordf",               re.I),    "ORD"),
    (re.compile(r"^LÄS\b"),                        "LAS"),
    (re.compile(r"^LAS\b"),                        "LAS"),
    (re.compile(r"^Svensk läs",          re.I),    "LAS"),
    (re.compile(r"^MEK\b"),                        "MEK"),
    (re.compile(r"^Meningskomplettering",re.I),   "MEK"),
    (re.compile(r"^ELF\b"),                        "ELF"),
    (re.compile(r"^Engelsk läs",         re.I),    "ELF"),
    # DELPROV prefix variants (e.g. "DELPROV ORD – ORDFÖRSTÅELSE")
    (re.compile(r"^DELPROV\s+ORD\b",    re.I),    "ORD"),
    (re.compile(r"^DELPROV\s+LÄS\b",    re.I),    "LAS"),
    (re.compile(r"^DELPROV\s+LAS\b",    re.I),    "LAS"),
    (re.compile(r"^DELPROV\s+MEK\b",    re.I),    "MEK"),
    (re.compile(r"^DELPROV\s+ELF\b",    re.I),    "ELF"),
    (re.compile(r"^DELPROV\s+XYZ\b",    re.I),    "XYZ"),
    (re.compile(r"^DELPROV\s+KVA\b",    re.I),    "KVA"),
    (re.compile(r"^DELPROV\s+NOG\b",    re.I),    "NOG"),
    (re.compile(r"^DELPROV\s+DTK\b",    re.I),    "DTK"),
]

SKIP_RE = re.compile(
    r"^([–\-]\s*\d+\s*[–\-]"
    r"|Uppgifter$"
    r"|Tillr.cklig information"
    r"|B.rja inte"
    r"|Tillst.nd"
    r"|Svarsh.fte"
    r"|Provtiden"
    r"|Du m.ste"
    r"|F.lj instruktionerna"
    r"|Du f.r"
    r"|Fyll"
    r"|P. n.sta"
    r"|Prov\s+Antal"
    r"|Antal uppgifter"
    r"|Uppgiftsnummer"
    r"|H.gskoleprovet"
    r"|Provpass \d"
    r"|Kvantitativ del"
    r"|Verbal del"
    r"|Rekommenderad"
    r"|Detta provh.fte"
    r"|Universit"
    r"|\d{4}-\d{2}-\d{2}$"
    r"|^(?:ORD|LÄS|LAS|MEK|ELF|XYZ|KVA|NOG|DTK)\s+\d"
    r")",
    re.I,
)

Q_RE   = re.compile(r"^(\d{1,2})\.\s+(.*)")
OPT_RE = re.compile(r"^([A-E])\s{1,5}(\S.*)")
NOG_RE = re.compile(r"^\((\d)\)\s+(.*)")

# Inline option detection: quantitative sections pack options with 1 space; verbal use 3+
_INLINE_QUANT_RE = re.compile(r"\s{1,}([A-E])\s{1,5}(\S.*)")
_INLINE_VERB_RE  = re.compile(r"\s{3,}([A-E])\s{1,5}(\S.*)")

# Fraction-option: fitz places the option letter at the END of a numerator line.
# Pattern: "<expr> LETTER" where expr starts with a digit/lowercase/minus/paren.
# e.g. "7 C" → C) 7    "m D" → D) m    "1 A" → A) 1
_FRAC_OPT_RE = re.compile(r"^([0-9a-z\-\(].{0,14})\s+([A-E])$")

PASSAGE_SECTIONS = {"LAS", "ELF"}

EXCLUDE_STEMS = {"facit", "kallforteckning", "norm-", "fordelningstabell",
                 "documents_claude"}


# ── PDF text extraction ──────────────────────────────────────────────────────

def _fitz_page_lines(page):
    """Reconstruct lines from PyMuPDF word positions (handles multi-column)."""
    words = page.get_text("words")
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(w[1] / 4) * 4, w[0]))
    lines, cur_y, cur_ws = [], None, []
    for w in words:
        y = round(w[1] / 4) * 4
        if cur_y is None or abs(y - cur_y) > 4:
            if cur_ws:
                lines.append(" ".join(cur_ws))
            cur_ws = [w[4]]
            cur_y  = y
        else:
            cur_ws.append(w[4])
    if cur_ws:
        lines.append(" ".join(cur_ws))
    return lines


def _fitz_page_lines_smart(page):
    """Column-aware line reconstruction.

    Detects two-column pages by presence of question markers ("N.") in both
    the left and right halves.  On two-column pages, full-width content above
    the first question line (e.g. passage text, headers) is kept in natural
    reading order, then the left column is appended, then the right column.
    Single-column pages fall back to normal word-sorted reconstruction.
    """
    words = page.get_text("words")
    if not words:
        return []

    cx = page.rect.width / 2

    q_words_left  = [w for w in words if re.match(r"^\d+\.$", w[4]) and w[0] < cx]
    q_words_right = [w for w in words if re.match(r"^\d+\.$", w[4]) and w[0] >= cx]

    def _to_lines(ws):
        ws = sorted(ws, key=lambda w: (round(w[1] / 4) * 4, w[0]))
        lines, cy, cw = [], None, []
        for w in ws:
            y = round(w[1] / 4) * 4
            if cy is None or abs(y - cy) > 4:
                if cw:
                    lines.append(" ".join(cw))
                cw = [w[4]]
                cy = y
            else:
                cw.append(w[4])
        if cw:
            lines.append(" ".join(cw))
        return lines

    if not q_words_left or not q_words_right:
        return _to_lines(words)

    # Two-column: split at the y of the topmost question number
    q_top_y = min(w[1] for w in q_words_left + q_words_right)

    above = [w for w in words if w[1] < q_top_y - 5]   # passage / headers
    below = [w for w in words if w[1] >= q_top_y - 5]  # question area

    return _to_lines(above) + _to_lines([w for w in below if w[0] < cx]) + \
           _to_lines([w for w in below if w[0] >= cx])


def _pdfplumber_lines(path):
    result = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                for line in (page.extract_text() or "").splitlines():
                    result.append((line, i))
    except Exception:
        pass
    return result


def pdf_lines_with_pages(path):
    """Returns list of (line, page_idx). Prefers fitz; falls back to pdfplumber."""
    fitz_result = []
    try:
        doc = fitz.open(str(path))
        for i, page in enumerate(doc):
            for line in _fitz_page_lines_smart(page):
                fitz_result.append((line, i))
        doc.close()
    except Exception as e:
        print(f"  fitz ERROR {path.name}: {e}")

    plumber_result = _pdfplumber_lines(path)

    if len(plumber_result) > len(fitz_result) * 1.5:
        return plumber_result
    return fitz_result


def pdf_lines(path):
    return [l for l, _ in pdf_lines_with_pages(path)]


def render_page_png(pdf_path, page_idx, out_path, zoom=2):
    doc = fitz.open(str(pdf_path))
    pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(str(out_path))
    doc.close()


# ── filename parsing ─────────────────────────────────────────────────────────

def parse_exam_filename(name):
    stem = Path(name).stem
    m = re.match(
        r"(\d{4}-\d{2}-\d{2})_provpass-(\d+)-(kvant|verb)(?:-utan-elf)?(?:-(v\d+))?$",
        stem, re.I,
    )
    if not m:
        m2 = re.match(r"provpass-(\d+)-(kvant|verb)", stem, re.I)
        if m2:
            stype = "kvant" if "kvant" in m2.group(2).lower() else "verbal"
            return {"source_exam": "unknown", "provpass": int(m2.group(1)),
                    "section_type": stype, "variant": None}
        return None
    stype = "kvant" if "kvant" in m.group(3).lower() else "verbal"
    return {
        "source_exam":  m.group(1),
        "provpass":     int(m.group(2)),
        "section_type": stype,
        "variant":      m.group(4),
    }


def parse_facit_filename(name):
    stem = Path(name).stem
    m = re.match(r"(\d{4}-\d{2}-\d{2})_facit(?:-(v\d+))?", stem, re.I)
    if m:
        return m.group(1), m.group(2)
    return None, None


# ── question extraction ──────────────────────────────────────────────────────

def detect_section(line):
    s = line.strip()
    for pat, code in SECTION_PATTERNS:
        if pat.match(s):
            return code
    return None


def is_skip(line):
    return not line.strip() or bool(SKIP_RE.match(line.strip()))


def extract_questions(path, meta):
    lines_pages  = pdf_lines_with_pages(path)
    questions    = []
    section      = None
    q_num        = None
    q_text       = []
    options      = []
    nog_stmts    = []
    in_opts      = False
    q_page       = None
    passage_buf  = []
    cur_passage  = None
    # ORD two-column: tracks the right-column question built in parallel
    right_q      = None   # {"num": int, "text": str, "opts": list}

    # Detects fitz-merged ORD paired lines: "word1 N. word2"
    _ORD_QPAIR = re.compile(r"^(\S+)\s+(\d{1,2})\.\s+(\S.*)$")
    # Detects fitz-merged ORD paired option lines: "A def1 A def2"
    _ORD_OPAIR = re.compile(r"^([A-E])\s+(.+?)\s+([A-E])\s+(.+)$")

    def _emit_entry(num, text_parts, opts, nogs, page, sec, passage=None):
        full_text = " ".join(" ".join(text_parts).split())
        if not full_text and not opts:
            return
        entry = {
            "source_exam":     meta["source_exam"],
            "provpass":        meta["provpass"],
            "variant":         meta.get("variant"),
            "section_type":    meta["section_type"],
            "question_type":   sec,
            "question_number": num,
            "question_text":   full_text,
            "options":         list(opts),
            "correct_answer":  None,
        }
        if nogs:
            entry["nog_statements"] = list(nogs)
        if sec in PASSAGE_SECTIONS and passage:
            entry["_passage_text"] = passage
        if sec in {"DTK", "XYZ"} and page is not None:
            entry["_source_pdf"] = str(path)
            entry["_page_idx"]   = page
        questions.append(entry)

    def flush():
        nonlocal q_num, q_text, options, nog_stmts, in_opts, q_page, right_q
        if q_num is not None and section is not None:
            _emit_entry(q_num, q_text, options, nog_stmts, q_page, section,
                        passage=(cur_passage if section in PASSAGE_SECTIONS else None))
            if right_q is not None:
                _emit_entry(right_q["num"], [right_q["text"]], right_q["opts"],
                            [], None, "ORD")
        q_num = None; q_text = []; options = []; nog_stmts = []
        in_opts = False; q_page = None; right_q = None

    def maybe_commit_passage():
        nonlocal cur_passage, passage_buf
        candidate = " ".join(passage_buf).strip()
        if len(candidate) > 200:
            cur_passage = candidate
        elif cur_passage is None and len(candidate) > 40:
            cur_passage = candidate
        passage_buf = []

    for raw, page_idx in lines_pages:
        line = raw.strip()
        if is_skip(line):
            continue
        if ".indd" in line:          # InDesign production metadata artifact
            continue

        sec = detect_section(line)
        if sec:
            if section in PASSAGE_SECTIONS:
                maybe_commit_passage()
            flush()
            section     = sec
            passage_buf = []
            cur_passage = None
            continue

        if section is None:
            continue

        m = Q_RE.match(line)
        if m:
            if section in PASSAGE_SECTIONS:
                maybe_commit_passage()
            flush()
            q_num = int(m.group(1))
            q_page = page_idx
            rest  = m.group(2).strip()

            if section == "ORD":
                # Detect fitz-merged two-column line: "word1 N. word2"
                mp = _ORD_QPAIR.match(rest)
                if mp:
                    q_text  = [mp.group(1)]
                    right_q = {"num": int(mp.group(2)), "text": mp.group(3), "opts": []}
                else:
                    q_text  = [rest] if rest else []
            else:
                q_text = [rest] if rest else []
            in_opts = False
            continue

        if q_num is None:
            if section in PASSAGE_SECTIONS:
                passage_buf.append(line)
            continue

        m_opt = OPT_RE.match(line)
        if m_opt:
            in_opts  = True
            opt_letter = m_opt.group(1)
            opt_text   = m_opt.group(2).strip()

            # ORD two-column: try to split "A def1 A def2" into left and right
            if section == "ORD" and right_q is not None:
                mo = _ORD_OPAIR.match(line)
                if mo and mo.group(1) == mo.group(3):
                    options.append(f"{mo.group(1)}) {mo.group(2).strip()}")
                    right_q["opts"].append(f"{mo.group(3)}) {mo.group(4).strip()}")
                    continue

            options.append(f"{opt_letter}) {opt_text}")
            # Recursively peel off trailing inline options.
            # Quantitative sections pack options with 1 space; verbal needs 3+.
            inl_re = (_INLINE_QUANT_RE if section in {"XYZ", "KVA", "NOG", "DTK"}
                      else _INLINE_VERB_RE)
            while True:
                m_last = re.match(r"^([A-E])\) (.+)", options[-1])
                if not m_last:
                    break
                inl = inl_re.search(m_last.group(2))
                if not inl:
                    break
                inner = m_last.group(2)
                options[-1] = f"{m_last.group(1)}) {inner[:inl.start()].strip()}"
                options.append(f"{inl.group(1)}) {inl.group(2).strip()}")
            continue

        if section == "NOG":
            m_nog = NOG_RE.match(line)
            if m_nog:
                nog_stmts.append(f"({m_nog.group(1)}) {m_nog.group(2).strip()}")
                continue

        # Fraction-option: "numerator LETTER" — letter trails the numerator on the
        # same fitz line (e.g. "7 C", "m D", "1 A").  Only in math sections.
        if section in {"XYZ", "KVA", "NOG"} and q_num is not None:
            mf = _FRAC_OPT_RE.match(line)
            if mf:
                in_opts = True
                options.append(f"{mf.group(2)}) {mf.group(1)}")
                continue

        if not in_opts:
            # In math sections, a line like "2 A -" or "19 L A =" has the option
            # letter in the middle.  Detect it and switch to option mode.
            if section in {"XYZ", "KVA", "NOG"}:
                # XYZ fraction rendering: fitz puts numerator, letter, denominator
            # on separate lines.  A lone "A"/"B"/… = option start.
                if section == "XYZ" and re.fullmatch(r"[A-E]", line):
                    in_opts = True
                    options.append(f"{line})")
                    continue
                inl = _INLINE_QUANT_RE.search(line)
                if inl:
                    pre = line[:inl.start()].strip()
                    if pre:
                        q_text.append(pre)
                    in_opts = True
                    options.append(f"{inl.group(1)}) {inl.group(2).strip()}")
                    while True:
                        ml = re.match(r"^([A-E])\) (.+)", options[-1])
                        if not ml:
                            break
                        ii = _INLINE_QUANT_RE.search(ml.group(2))
                        if not ii:
                            break
                        inn = ml.group(2)
                        options[-1] = f"{ml.group(1)}) {inn[:ii.start()].strip()}"
                        options.append(f"{ii.group(1)}) {ii.group(2).strip()}")
                    continue
            q_text.append(line)
        else:
            if section in PASSAGE_SECTIONS:
                passage_buf.append(line)
            else:
                # XYZ fraction: lone letter = new option (numerator on prev line)
                if section == "XYZ" and re.fullmatch(r"[A-E]", line):
                    options.append(f"{line})")
                elif options:
                    options[-1] += " " + line
                    # Re-scan for embedded option letters now that the
                    # continuation text (e.g. a fraction denominator) may have
                    # completed the surrounding space pattern.
                    if section in {"XYZ", "KVA", "NOG", "DTK"}:
                        while True:
                            ml = re.match(r"^([A-E])\) (.+)", options[-1])
                            if not ml:
                                break
                            inl = _INLINE_QUANT_RE.search(ml.group(2))
                            if not inl:
                                break
                            inn = ml.group(2)
                            options[-1] = f"{ml.group(1)}) {inn[:inl.start()].strip()}"
                            options.append(f"{inl.group(1)}) {inl.group(2).strip()}")

    flush()
    return [q for q in questions if 1 <= q["question_number"] <= 60]


# ── facit parsing ────────────────────────────────────────────────────────────

def parse_facit(path):
    # Always use fitz word-based lines — correctly groups multi-column answers
    lines_raw = []
    try:
        doc = fitz.open(str(path))
        for page in doc:
            for line in _fitz_page_lines(page):
                lines_raw.append(line)
        doc.close()
    except Exception:
        pass
    if not lines_raw:
        lines_raw = [l for l, _ in _pdfplumber_lines(path)]

    answers        = {}
    provpass_order = []
    current_pp     = None
    pending_qnum   = None

    def _add(pp, qnum, letter):
        if pp and qnum is not None and letter in "ABCDE":
            answers.setdefault(pp, {})[qnum] = letter

    def _fix_num(raw_num, pp):
        """
        Some PDFs split two-digit question numbers: '10' → '1 0'.
        Detect by matching the last digit of the next expected question number.
        """
        if raw_num >= 10 or pp not in answers or not answers[pp]:
            return raw_num
        max_seen = max(answers[pp].keys())
        next_exp = max_seen + 1
        if next_exp >= 10 and raw_num == next_exp % 10:
            return next_exp
        return raw_num

    for line in lines_raw:
        s = line.strip()
        pp_matches = re.findall(r"Provpass\s+(\d+)", s)
        if pp_matches:
            pending_qnum = None
            if len(pp_matches) > 1:
                provpass_order = [int(x) for x in pp_matches]
                current_pp     = None
                for pp in provpass_order:
                    answers.setdefault(pp, {})
            else:
                current_pp     = int(pp_matches[0])
                provpass_order = []
                answers.setdefault(current_pp, {})
            continue

        parts = s.split()

        # Handle "N\nL" split (number alone then letter on next line)
        if pending_qnum is not None and len(parts) == 1 and parts[0] in "ABCDE":
            if current_pp:
                _add(current_pp, _fix_num(pending_qnum, current_pp), parts[0])
            pending_qnum = None
            continue
        pending_qnum = None

        # Standard "N L [N L …]" scan
        pairs = []
        i = 0
        while i < len(parts):
            if re.match(r"^\d+$", parts[i]):
                raw = int(parts[i])
                if i + 1 < len(parts) and parts[i + 1] in "ABCDE":
                    pairs.append((raw, parts[i + 1]))
                    i += 2
                    continue
                elif i + 1 == len(parts):
                    pending_qnum = raw
            i += 1

        # Fallback: "N N N N L L L L" layout (e.g. 2023-10-22)
        if not pairs or (provpass_order and len(pairs) != len(provpass_order)):
            nums = [int(p) for p in parts if re.match(r"^\d+$", p)]
            lets = [p for p in parts if p in "ABCDE"]
            if len(nums) == len(lets) > 0 and len(nums) > len(pairs):
                pairs = list(zip(nums, lets))

        if not pairs:
            continue

        if provpass_order and len(pairs) == len(provpass_order):
            for pp, (raw_num, letter) in zip(provpass_order, pairs):
                _add(pp, _fix_num(raw_num, pp), letter)
        elif current_pp:
            for raw_num, letter in pairs:
                _add(current_pp, _fix_num(raw_num, current_pp), letter)

    return answers


# ── ID & deduplication ───────────────────────────────────────────────────────

def make_id(qtype, text, variant=None, options=None, source_exam=None):
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    v = f"|{variant}" if variant else ""
    # DTK questions have nearly identical text ("30.", "36." …) across exams.
    # Pin each to its source exam to prevent cross-exam merging.
    if qtype == "DTK":
        key = f"DTK{v}|{source_exam or 'unknown'}|{normalized}"
    elif len(normalized) < 40 and options:
        opts_str = "|".join(sorted(o.lower() for o in options))
        key = f"{qtype}{v}|{normalized}|{opts_str}"
    else:
        key = f"{qtype}{v}|{normalized}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def deduplicate(all_q):
    seen = {}
    for q in all_q:
        if not q["question_text"] and not q.get("options"):
            continue
        variant = q.get("variant")
        qid = make_id(
            q["question_type"], q["question_text"], variant,
            q.get("options"), source_exam=q.get("source_exam"),
        )
        if qid in seen:
            ex   = seen[qid]
            srcs = ex["all_sources"]
            src  = {"exam": q["source_exam"], "provpass": q["provpass"],
                    "variant": variant}
            if src not in srcs:
                srcs.append(src)
            if q["correct_answer"] and not ex["correct_answer"]:
                ex["correct_answer"] = q["correct_answer"]
            elif (q["correct_answer"]
                  and ex["correct_answer"]
                  and ex["correct_answer"] != q["correct_answer"]
                  and q["source_exam"] != ex["source_exam"]):
                ex.setdefault("answer_conflict", []).append(
                    {"exam": q["source_exam"], "provpass": q["provpass"],
                     "answer": q["correct_answer"]}
                )
            if "_passage_text" not in ex and q.get("_passage_text"):
                ex["_passage_text"] = q["_passage_text"]
        else:
            q["id"] = qid
            q["all_sources"] = [{"exam": q["source_exam"],
                                  "provpass": q["provpass"],
                                  "variant": variant}]
            seen[qid] = q
    return list(seen.values())


# ── validation ───────────────────────────────────────────────────────────────

_GRAPH_RE = re.compile(
    r"\bgraf(?:en|erna|er)?\b"
    r"|\bkurva(?:n|r)?\b"
    r"|\bdiagram(?:met)?\b"
    r"|\bsvarsalternativ\s+visar\b"          # "vilket svarsalternativ visar..."
    r"|\bA\s+B\s+C\s+D\b",                  # panel labels "A B C D" adjacent in text
    re.I
)


def validate(questions):
    issues = defaultdict(list)
    for q in questions:
        qid = q["id"]
        qt  = q["question_type"]
        ans = q.get("correct_answer")
        if ans:
            prefix = f"{ans})"
            # DTK is diagram-based; extracted option text is secondary
            if (q["options"] and qt != "DTK"
                    and not any(o.startswith(prefix) for o in q["options"])):
                issues[qid].append(f"answer {ans} not found in options")
        else:
            issues[qid].append("no correct_answer")
        # XYZ graph questions: options are visual diagrams on the page.
        # The single-letter detection may have created bare "A)"…"D)" labels;
        # those are not useful — clear them so diagram_image is the only source.
        is_graph = qt == "XYZ" and _GRAPH_RE.search(q.get("question_text", ""))
        if is_graph:
            q["graph_question"] = True
            q["options"] = []
        if not q["options"] and qt not in ("DTK",) and not is_graph:
            issues[qid].append("no options extracted")
    return issues


# ── passage text files ───────────────────────────────────────────────────────

def save_passage(text):
    """Write passage to texts/ folder; return filename."""
    os.makedirs(str(TEXTS_DIR), exist_ok=True)
    name = hashlib.md5(text.encode()).hexdigest()[:16] + ".txt"
    path = TEXTS_DIR / name
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return name


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    all_pdfs = sorted(INPUT_DIR.glob("*.pdf"))

    exam_pdfs = [
        p for p in all_pdfs
        if "provpass" in p.name.lower()
        and not any(e in p.name.lower() for e in EXCLUDE_STEMS)
    ]
    facit_pdfs = [p for p in all_pdfs if "facit" in p.name.lower()]

    print(f"Exam PDFs : {len(exam_pdfs)}")
    print(f"Facit PDFs: {len(facit_pdfs)}")

    # 1. Parse facit files
    facit_lookup = {}
    for path in facit_pdfs:
        date, variant = parse_facit_filename(path.name)
        if not date:
            print(f"  SKIP facit (bad name): {path.name}")
            continue
        per_pp = parse_facit(path)
        total  = sum(len(v) for v in per_pp.values())
        for pp, answers in per_pp.items():
            for qnum, letter in answers.items():
                facit_lookup[(date, variant, pp, qnum)] = letter
        print(f"  facit {path.name}: {len(per_pp)} provpass, {total} answers")

    # 2. Extract questions and attach answers
    all_q = []
    zero  = []
    for path in exam_pdfs:
        meta = parse_exam_filename(path.name)
        if not meta:
            print(f"  SKIP exam (bad name): {path.name}")
            continue
        qs      = extract_questions(path, meta)
        date    = meta["source_exam"]
        pp      = meta["provpass"]
        variant = meta.get("variant")
        for q in qs:
            qnum = q["question_number"]
            ans  = (facit_lookup.get((date, variant, pp, qnum))
                    or facit_lookup.get((date, None,  pp, qnum))
                    or facit_lookup.get((date, "v1",  pp, qnum))
                    or facit_lookup.get((date, "v2",  pp, qnum)))
            q["correct_answer"] = ans
        answered = sum(1 for q in qs if q["correct_answer"])
        print(f"  {path.name}: {len(qs)} questions, {answered} with answers")
        if not qs:
            zero.append(path.name)
        all_q.extend(qs)

    # 3. Deduplicate
    deduped = deduplicate(all_q)
    print(f"\nRaw: {len(all_q)}  Unique: {len(deduped)}")

    # 3b. Remove questions that can't be used: false-positive Q_RE matches in
    # passages (LAS/ELF with no options), corrupted PDF artifacts, and stubs
    # with neither answer nor options.
    def _is_droppable(q):
        qt = q["question_type"]
        has_ans  = bool(q.get("correct_answer"))
        has_opts = bool(q.get("options"))
        # LAS/ELF: a question with no options is always a passage-text false positive
        if qt in PASSAGE_SECTIONS and not has_opts:
            return True
        # Completely unusable: no answer and no options
        if not has_ans and not has_opts:
            return True
        # PDF artifact: option text contains InDesign production metadata
        if any(".indd" in o for o in q.get("options", [])):
            return True
        # XYZ/NOG with no options and not a detected graph question — extraction
        # failed completely (garbled math, truncated text) and the question can't
        # be used.  Graph questions are excluded since their options are visual.
        if not has_opts and qt in {"XYZ", "NOG"}:
            is_graph = _GRAPH_RE.search(q.get("question_text", ""))
            if not is_graph:
                return True
        return False

    before = len(deduped)
    deduped = [q for q in deduped if not _is_droppable(q)]
    dropped = before - len(deduped)
    if dropped:
        print(f"Dropped {dropped} unusable questions")

    # 4. Validate
    issues     = validate(deduped)
    no_answer  = sum(1 for v in issues.values() if any("no correct_answer" in i for i in v))
    bad_answer = sum(1 for v in issues.values() if any("not found in options" in i for i in v))
    no_options = sum(1 for v in issues.values() if any("no options" in i for i in v))
    conflicts  = sum(1 for q in deduped if "answer_conflict" in q)
    print(f"\nValidation:")
    print(f"  Missing answer       : {no_answer}")
    print(f"  Answer not in options: {bad_answer}")
    print(f"  Missing options      : {no_options}")
    print(f"  Answer conflicts     : {conflicts}")

    for q in deduped:
        if q["id"] in issues:
            q["validation_issues"] = issues[q["id"]]

    # 5. Stats by type
    counts = Counter(q["question_type"] for q in deduped)
    print("\nBy type:")
    for k, v in sorted(counts.items()):
        answered  = sum(1 for q in deduped if q["question_type"] == k and q["correct_answer"])
        w_passage = sum(1 for q in deduped if q["question_type"] == k and q.get("_passage_text"))
        extra = f", {w_passage} with passage" if k in PASSAGE_SECTIONS else ""
        print(f"  {k}: {v} total, {answered} with answers{extra}")

    if zero:
        print(f"\nZero-question files ({len(zero)}):")
        for f in zero:
            print(f"  {f}")

    # 6. Save passage texts to texts/ folder
    os.makedirs(str(TEXTS_DIR), exist_ok=True)
    passage_count = 0
    for q in deduped:
        raw = q.pop("_passage_text", None)
        if raw:
            fname = save_passage(raw)
            q["passage_file"] = fname
            passage_count += 1
    print(f"\nPassage files written: {passage_count} questions linked, "
          f"{len(list(TEXTS_DIR.glob('*.txt')))} unique files in texts/")

    # 7. Render DTK and XYZ-graph images to images/ folder
    os.makedirs(str(IMAGES_DIR), exist_ok=True)
    rendered        = {}
    dtk_count       = 0
    xyz_graph_count = 0
    for q in deduped:
        qt           = q["question_type"]
        is_xyz_graph = qt == "XYZ" and q.get("graph_question")
        if qt != "DTK" and not is_xyz_graph:
            continue
        pdf_path = q.pop("_source_pdf", None)
        page_idx = q.pop("_page_idx",   None)
        if pdf_path is None or page_idx is None:
            continue
        key = (pdf_path, page_idx)
        if key not in rendered:
            stem     = Path(pdf_path).stem
            img_name = f"{stem}_p{page_idx}.png"
            img_path = IMAGES_DIR / img_name
            if not img_path.exists():
                try:
                    render_page_png(pdf_path, page_idx, img_path)
                except Exception as e:
                    print(f"  ERROR rendering {img_name}: {e}")
                    rendered[key] = None
                    continue
            rendered[key] = img_name
        fname = rendered[key]
        if fname:
            q["diagram_image"] = fname
            if qt == "DTK":
                dtk_count += 1
            else:
                xyz_graph_count += 1

    unique_imgs = len({v for v in rendered.values() if v})
    print(f"Diagram images: {dtk_count} DTK + {xyz_graph_count} XYZ-graph linked, "
          f"{unique_imgs} unique PNGs in images/")

    # Clean up any leftover internal keys
    for q in deduped:
        q.pop("_source_pdf", None)
        q.pop("_page_idx",   None)

    # 8. Write JSON
    out = {
        "total_questions": len(deduped),
        "generated":       "2026-06-20",
        "notes": {
            "passage_file": "LAS/ELF reading passage saved in texts/ folder",
            "diagram_image": "DTK diagram page (or XYZ graph question page) saved in images/ folder",
        },
        "questions": deduped,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(deduped)} questions -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
