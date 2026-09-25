"""Merge written text into the plans, run quality checks, write the datasets.

Text lives in batches/*.tsv, one row per line: <id><TAB><text>.
Can run at any point: rows without text yet are simply not written.

Outputs (committed):
  complaints.csv         plan A rows + the relabelled 100-row pilot
  paraphrase_groups.csv  plan B rows (3 variants per group)
  qc_report.txt          the check results

Run: python -m training.synthetic.assemble
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

from training.synthetic.plan import LATIN_ONLY

HERE = Path(__file__).parent
BATCH_DIR = HERE / "batches"
PILOT_CSV = Path.home() / "civicfix-data/raw/synthetic_pune_pilot_100.csv"
ICMYC_CSV = HERE.parent / "icmyc_mapped.csv"
NEAR_DUP = 0.6

# Pilot used a coarser taxonomy; relabelled once, by reading each row.
# Loanwords (road, light, footpath, signal, drainage...) don't make text code-mixed;
# whole English phrases do. Hindi/Marathi mixes take the dominant language.
PILOT_LANGUAGE = {
    "0013": "romanized_marathi", "0031": "romanized_marathi", "0070": "romanized_marathi",
    "0010": "hinglish", "0011": "hinglish", "0012": "hinglish", "0030": "hinglish",
    "0042": "hinglish", "0054": "hinglish", "0036": "hinglish", "0060": "hinglish", "0078": "hinglish",
    "0022": "marathi_english", "0088": "marathi_english",
}
PILOT_SEVERITY = {"low": "cosmetic", "medium": "moderate", "high": "critical", "critical": "critical"}
PILOT_OUTSIDE_PMC = ("wakad", "hinjewadi", "pimple", "sus road")

FIELDS = ["id", "text", "category", "secondary_category", "severity", "language", "script",
          "locality", "scenario", "difficulty", "source", "is_synthetic", "review_status", "generated_by"]
GROUP_FIELDS = ["id", "group_id", "text", "category", "severity", "language", "script", "locality",
                "scenario", "source", "is_synthetic", "review_status", "generated_by"]

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_PII = re.compile(r"\d{6,}|\S+@\S+\.\w+|\b(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+[A-Z]")


def detect_script(text: str) -> str:
    dev, lat = bool(_DEVANAGARI.search(text)), bool(_LATIN.search(text))
    return "mixed" if dev and lat else "devanagari" if dev else "latin"


def script_problem(language: str, script_hint: str, text: str) -> str | None:
    actual = detect_script(text)
    if language in LATIN_ONLY and actual != "latin":
        return f"{language} must be Latin script, got {actual}"
    if language in ("hindi", "marathi") and actual != "devanagari":
        return f"{language} must be Devanagari only, got {actual}"
    if script_hint and actual != script_hint:
        return f"planned {script_hint} script, got {actual}"
    return None


def has_pii(text: str) -> bool:
    return bool(_PII.search(text))


def _shingles(text: str) -> set[str]:
    t = " ".join(text.lower().split())
    return {t[i:i + 3] for i in range(len(t) - 2)}


def shingle_similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _read_texts() -> tuple[dict[str, str], list[str]]:
    texts, problems = {}, []
    for path in sorted(BATCH_DIR.glob("*.tsv")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            row_id, sep, text = line.partition("\t")
            if not sep or not text.strip():
                problems.append(f"{path.name}:{n} malformed line")
            elif row_id in texts:
                problems.append(f"{path.name}:{n} {row_id} written twice")
            else:
                texts[row_id] = text.strip()
    return texts, problems


def _pilot_rows() -> list[dict]:
    rows = []
    for r in _read_csv(PILOT_CSV):
        suffix = r["complaint_id"][-4:]
        rows.append({
            "id": r["complaint_id"], "text": r["text"], "category": r["category"],
            "secondary_category": r["secondary_category"], "severity": PILOT_SEVERITY[r["severity"]],
            "language": PILOT_LANGUAGE.get(suffix, "romanized_hindi" if r["language"] == "hinglish" else r["language"]),
            "script": detect_script(r["text"]),
            # Outside PMC: fine for learning categories, blanked so it never feeds ward lookup.
            "locality": "" if any(p in r["text"].lower() for p in PILOT_OUTSIDE_PMC) else r["locality"],
            "scenario": r["generation_scenario"],
            "difficulty": "multi_issue" if r["multi_issue"] == "true" else
                          ("hard_" + r["generation_scenario"][5:].split("_")[0]
                           if r["generation_scenario"].startswith("hard_") else "normal"),
            "source": "synthetic_claude_pilot", "is_synthetic": "true",
            "review_status": "unreviewed", "generated_by": "claude",
        })
    return rows


def assemble() -> list[str]:
    plan_a, plan_b = _read_csv(HERE / "plan_complaints.csv"), _read_csv(HERE / "plan_groups.csv")
    texts, problems = _read_texts()
    known = {r["id"] for r in plan_a} | {r["id"] for r in plan_b}
    problems += [f"{i}: text for an id not in any plan" for i in texts if i not in known]

    complaints = _pilot_rows()
    for p in plan_a:
        if p["id"] not in texts:
            continue
        text = texts[p["id"]]
        issue = script_problem(p["language"], p["script_hint"], text)
        if issue:
            problems.append(f"{p['id']}: {issue}")
        complaints.append({**{k: p[k] for k in ("id", "category", "secondary_category", "severity",
                                                "language", "locality", "scenario", "difficulty")},
                           "text": text, "script": detect_script(text), "source": "synthetic_claude",
                           "is_synthetic": "true", "review_status": "unreviewed", "generated_by": "claude"})
    groups = []
    for p in plan_b:
        if p["id"] not in texts:
            continue
        text = texts[p["id"]]
        issue = script_problem(p["language"], p["script_hint"], text)
        if issue:
            problems.append(f"{p['id']}: {issue}")
        groups.append({**{k: p[k] for k in ("id", "group_id", "category", "severity", "language",
                                            "locality", "scenario")},
                       "text": text, "script": detect_script(text), "source": "synthetic_claude",
                       "is_synthetic": "true", "review_status": "unreviewed", "generated_by": "claude"})

    everything = [(r["id"], r["text"]) for r in complaints] + [(r["id"], r["text"]) for r in groups]
    problems += [f"{i}: possible personal information" for i, t in everything if has_pii(t)]

    # ponytail: O(n^2) shingle comparison, ~3k texts is seconds; MinHash if this grows past ~20k.
    group_of = {r["id"]: r["group_id"] for r in groups}
    shingled = [(i, _shingles(t)) for i, t in everything]
    for x in range(len(shingled)):
        id_a, sa = shingled[x]
        for y in range(x + 1, len(shingled)):
            id_b, sb = shingled[y]
            if group_of.get(id_a) and group_of.get(id_a) == group_of.get(id_b):
                continue  # variants of one group are meant to describe the same problem
            if sa and sb and len(sa & sb) / len(sa | sb) >= NEAR_DUP:
                problems.append(f"{id_a} ~ {id_b}: near-duplicate")

    if ICMYC_CSV.exists():
        icmyc = {r["text"].lower() for r in _read_csv(ICMYC_CSV)}
        problems += [f"{i}: copied from iCMyC" for i, t in everything if t.lower() in icmyc]

    _write(HERE / "complaints.csv", FIELDS, complaints)
    _write(HERE / "paraphrase_groups.csv", GROUP_FIELDS, groups)
    report = _report(complaints, groups, plan_a, plan_b, problems)
    (HERE / "qc_report.txt").write_text(report)
    print(report)
    return problems


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _report(complaints, groups, plan_a, plan_b, problems) -> str:
    written = [r for r in complaints if r["source"] == "synthetic_claude"]
    words = [len(r["text"].split()) for r in complaints + groups]
    openers = Counter(" ".join(r["text"].lower().split()[:2]) for r in complaints + groups)
    lines = [
        f"complaints written: {len(written)}/{len(plan_a)} (+{len(complaints) - len(written)} pilot)",
        f"group variants written: {len(groups)}/{len(plan_b)}",
        f"category: {dict(Counter(r['category'] for r in complaints))}",
        f"language: {dict(Counter(r['language'] for r in complaints))}",
        f"script: {dict(Counter(r['script'] for r in complaints + groups))}",
        f"words per text: min {min(words, default=0)}, max {max(words, default=0)}, "
        f"mean {sum(words) / max(len(words), 1):.1f}",
        f"most repeated openers: {openers.most_common(5)}",
        f"'urgent' used in {sum('urgent' in r['text'].lower() for r in complaints + groups)} texts",
        f"problems: {len(problems)}",
        *problems,
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(1 if assemble() else 0)
