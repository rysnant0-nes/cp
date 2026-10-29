import json
import re
import sys
from pathlib import Path

import fitz

PDF = Path(r"D:\laragon\www\cp.pdf")
OUT = Path(__file__).resolve().parent.parent / "data" / "cp.json"
ZW = "\u200b"

SUBJECTS = [
    ("pai", "Pendidikan Agama Islam dan Budi Pekerti", "CAPAIAN PEMBELAJARAN PENDIDIKAN AGAMA ISLAM DAN BUDI"),
    ("kristen", "Pendidikan Agama Kristen dan Budi Pekerti", "CAPAIAN PEMBELAJARAN PENDIDIKAN AGAMA KRISTEN"),
    ("katolik", "Pendidikan Agama Katolik dan Budi Pekerti", "CAPAIAN PEMBELAJARAN PENDIDIKAN AGAMA KATOLIK"),
    ("hindu", "Pendidikan Agama Hindu dan Budi Pekerti", "CAPAIAN PEMBELAJARAN PENDIDIKAN AGAMA HINDU"),
    ("buddha", "Pendidikan Agama Buddha dan Budi Pekerti", "CAPAIAN PEMBELAJARAN PENDIDIKAN AGAMA BUDDHA"),
    ("khonghucu", "Pendidikan Agama Khonghucu dan Budi Pekerti", "CAPAIAN PEMBELAJARAN PENDIDIKAN AGAMA KHONGHUCU"),
    ("pancasila", "Pendidikan Pancasila", "CAPAIAN PEMBELAJARAN PENDIDIKAN PANCASILA"),
    ("bindo", "Bahasa Indonesia", "CAPAIAN PEMBELAJARAN BAHASA INDONESIA"),
    ("matematika", "Matematika", "CAPAIAN PEMBELAJARAN MATEMATIKA"),
    ("bing", "Bahasa Inggris", "CAPAIAN PEMBELAJARAN BAHASA INGGRIS"),
    ("ipas", "Ilmu Pengetahuan Alam dan Sosial", "CAPAIAN PEMBELAJARAN ILMU PENGETAHUAN ALAM DAN SOSIAL"),
    ("seni-musik", "Seni Musik", "CAPAIAN PEMBELAJARAN SENI MUSIK"),
    ("seni-rupa", "Seni Rupa", "CAPAIAN PEMBELAJARAN SENI RUPA"),
    ("seni-tari", "Seni Tari", "CAPAIAN PEMBELAJARAN SENI TARI"),
    ("seni-teater", "Seni Teater", "CAPAIAN PEMBELAJARAN SENI TEATER"),
    ("pjok", "Pendidikan Jasmani, Olahraga, dan Kesehatan", "CAPAIAN PEMBELAJARAN PENDIDIKAN JASMANI"),
    ("koding", "Koding dan Kecerdasan Artifisial", "CAPAIAN PEMBELAJARAN KODING DAN KECERDASAN ARTIFISIAL"),
]


def is_top_heading(text):
    return bool(
        re.match(r"^(?:[IVX]+(?:\.\d+)?\.?\s*)?CAPAIAN PEMBELAJARAN ", text)
        and text == text.upper()
        and "CAPAIAN PEMBELAJARAN PADA " not in text
    )


def page_lines(page):
    raw = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip() and ZW not in text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            raw.append({"y": y0, "x0": x0, "x1": x1, "text": text, "has_zw": ZW in text})

    raw.sort(key=lambda item: item["y"])
    groups = []
    for item in raw:
        if groups and abs(item["y"] - groups[-1][0]["y"]) <= 5:
            groups[-1].append(item)
        else:
            groups.append([item])

    merged = []
    for items in groups:
        items.sort(key=lambda item: item["x0"])
        cur = dict(items[0])
        for item in items[1:]:
            gap = item["x0"] - cur["x1"]
            if gap > 1.5 and not cur["text"].endswith(" ") and not item["text"].startswith(" "):
                cur["text"] += " "
            cur["text"] += item["text"]
            cur["x1"] = max(cur["x1"], item["x1"])
            cur["has_zw"] = cur["has_zw"] or item["has_zw"]
        merged.append(cur)
    for item in merged:
        item["text"] = re.sub(r"[ \t]+", " ", item["text"]).strip()
        item["ends_zw"] = item["text"].endswith(ZW)
        item["text"] = item["text"].replace(ZW, "").strip()
    return [item for item in merged if item["text"]]


def clean(text):
    text = text.replace(ZW, "").replace("\u00ad", "")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    text = re.sub(r"(?<=\w) - (?=\w)", "-", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def join_lines(parts):
    out = ""
    for raw in parts:
        part = clean(raw)
        if not part:
            continue
        if not out:
            out = part
        elif out.endswith("-") and part[:1].islower():
            out += part
        else:
            out += " " + part
    return re.sub(r"\s+", " ", out).strip()


def subject_ranges(doc):
    pages = [page_lines(doc[p]) for p in range(doc.page_count)]
    flat = []
    for pno, lines in enumerate(pages):
        for line in lines:
            flat.append((pno, line["text"]))

    def find_heading(needle, start=0):
        for idx in range(start, len(flat)):
            if needle in flat[idx][1]:
                return idx
        return None

    lampiran2 = None
    lampiran3 = None
    for idx, (_, text) in enumerate(flat):
        if text.strip() == "LAMPIRAN II" and lampiran2 is None:
            lampiran2 = idx
        if text.strip() == "LAMPIRAN III" and lampiran2 is not None:
            lampiran3 = idx
            break
    if lampiran2 is None or lampiran3 is None:
        raise RuntimeError("Lampiran II/III not found")

    located = []
    for key, name, needle in SUBJECTS:
        idx = find_heading(needle, lampiran2)
        if idx is None or idx > lampiran3:
            raise RuntimeError(f"Heading not found: {key}")
        located.append((idx, key, name))
    located.sort()

    ranges = {}
    for idx, key, name in located:
        end = lampiran3
        for j in range(idx + 1, lampiran3):
            if is_top_heading(flat[j][1]):
                end = j
                break
        ranges[key] = (flat[idx][0], flat[end][0], name)
    return ranges, pages


def parse_subject(pages, start_page, end_page, name, needle):
    seq = []
    for pno in range(start_page, end_page + 1):
        seq.extend(pages[pno])

    head_idx = None
    for i, line in enumerate(seq):
        if needle in line["text"]:
            head_idx = i
            break
    if head_idx is None:
        raise RuntimeError(f"Subject heading not found for {name}")
    seq = seq[head_idx + 1 :]

    cp_start = None
    for i, line in enumerate(seq):
        if re.match(r"^[A-Z]\.\s*Capaian Pembelajaran$", line["text"]):
            cp_start = i
            break
    if cp_start is None:
        raise RuntimeError(f"No CP heading for {name}")

    seq = seq[cp_start + 1 :]
    for i, line in enumerate(seq):
        if is_top_heading(line["text"]):
            seq = seq[:i]
            break

    fase_idx = []
    for i, line in enumerate(seq):
        if re.match(r"^\d+\.\s*Fase\s+[A-F]\b", line["text"]):
            fase_idx.append(i)

    fases = {}
    for fi, idx in enumerate(fase_idx):
        stop = fase_idx[fi + 1] if fi + 1 < len(fase_idx) else len(seq)
        j = idx
        head_parts = [seq[j]["text"]]
        while not seq[j]["ends_zw"] and j + 1 < stop:
            j += 1
            head_parts.append(seq[j]["text"])
        j += 1
        heading = re.sub(r"^\d+\.\s*", "", join_lines(head_parts))
        m = re.match(r"Fase\s+([A-F])", heading)
        if not m:
            continue
        fase = m.group(1)
        if fase not in ("A", "B", "C"):
            continue

        body = seq[j:stop]
        elements = []
        intro_parts = []
        cursor = 0
        current = None
        while cursor < len(body):
            line = body[cursor]
            label = re.match(r"^(\d+(?:\.\d+)+\.)\s*(.*)$", line["text"])
            group_heading = bool(
                label and (label.group(2).startswith("Elemen ") or label.group(2).startswith("Subelemen "))
            )
            is_heading = bool(label and line["x0"] < 300 and line["has_zw"])

            if is_heading:
                if current is not None:
                    elements.append(current)
                parts = [line["text"]]
                cursor += 1
                no_continuation = bool(re.match(r"^\d+(?:\.\d+)+\.\s*Elemen\b", line["text"]))
                while not line["ends_zw"] and not no_continuation and cursor < len(body):
                    nxt = body[cursor]
                    if re.match(r"^\d+(?:\.\d+)+\.", nxt["text"]) and nxt["x0"] < 300:
                        break
                    parts.append(nxt["text"])
                    line = nxt
                    cursor += 1
                head = join_lines(parts)
                mm = re.match(r"^(\d+(?:\.\d+)+\.)\s*(.*)$", head)
                number, title = (mm.group(1), mm.group(2)) if mm else ("", head)
                current = {"number": number, "title": title, "text": []}
                continue
            else:
                if current is None:
                    intro_parts.append(line["text"])
                else:
                    current["text"].append(line["text"])
            cursor += 1
        if current is not None:
            elements.append(current)

        fases[fase] = {
            "label": fase,
            "heading": clean(heading),
            "intro": join_lines(intro_parts),
            "elements": [
                {
                    "number": clean(e["number"]),
                    "title": clean(e["title"]),
                    "text": join_lines(e["text"]),
                }
                for e in elements
            ],
        }
    return {"name": name, "fases": fases}


def main():
    doc = fitz.open(str(PDF))
    ranges, pages = subject_ranges(doc)
    result = []
    for key, name, needle in SUBJECTS:
        start, end, nm = ranges[key]
        subject = parse_subject(pages, start, end, nm, needle)
        subject["id"] = key
        result.append(subject)
        counts = {f: len(subject["fases"][f]["elements"]) for f in subject["fases"]}
        print(key, counts, file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written", OUT, file=sys.stderr)


if __name__ == "__main__":
    main()
