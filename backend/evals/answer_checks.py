import logging
import re
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)  # it complains about the structure of the mock PDFs

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Free checks on an answer: no model is called. They compare the answer with the golden dataset and the PDFs.


def normalize(text: str) -> str:
    # Lower case, no currency words, no thousands separators, % written as the word: "GBP 1,000" -> "1000".
    t = text.lower().replace("’", "'").replace("–", "-").replace("£", " ")
    t = t.replace("%", " percent ")
    t = re.sub(r"\bgbp\b", " ", t)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def fact_found(answer: str, fact: str) -> bool:
    # "a|b" means either is fine. A number must match as a whole number, so 25 does not match 250 or 1,250.
    answer_norm = normalize(answer)
    for option in fact.split("|"):
        option_norm = normalize(option)
        if not option_norm:
            continue
        pattern = re.escape(option_norm)
        if option_norm[0].isdigit():
            pattern = r"(?<![0-9.])" + pattern
        if option_norm[-1].isdigit():
            pattern += r"(?![0-9])"
        if re.search(pattern, answer_norm):
            return True
    return False


def check_facts(answer: str, expected_facts: list[str]) -> tuple[int, int, list[str]]:
    # (found, total, missing)
    missing = [fact for fact in expected_facts if not fact_found(answer, fact)]
    return len(expected_facts) - len(missing), len(expected_facts), missing


@lru_cache
def pdf_page_labels() -> dict[str, list[str]]:
    # file name -> page labels of every PDF in backend/data/
    return {f.name: list(PdfReader(f).page_labels) for f in sorted(DATA_DIR.glob("*.pdf"))}


CITATION = re.compile(r"(insurance_[a-z0-9_]+\.pdf)\W{0,3}pages?\s*(\d+)(?:\s*(?:and|&|,)\s*(\d+))?", re.IGNORECASE)


def citations(answer: str) -> list[tuple[str, str]]:
    # (file, page) pairs the answer cites, for example "(insurance_audi_v1.pdf, page 2)"
    found = []
    for match in CITATION.finditer(answer):
        file = match.group(1).lower()
        found.append((file, match.group(2)))
        if match.group(3):
            found.append((file, match.group(3)))
    return found


def invalid_citations(answer: str) -> list[tuple[str, str]]:
    # Citations of a file or page that does not exist: the model made them up.
    labels = pdf_page_labels()
    return [(f, p) for f, p in citations(answer) if f not in labels or p not in labels[f]]


UNKNOWN = re.compile(
    r"\b(i (?:do not|don't|dont) know|not (?:mentioned|stated|specified|given|provided|covered|included|listed|"
    r"available|in the (?:context|documents?|policy|policies))|no information|"
    r"(?:cannot|can't|can not|unable to) (?:find|share|help|confirm|access|provide|answer|do that)|"
    r"(?:don't|do not) have|(?:doesn't|does not) (?:say|mention|state|specify|provide|give|contain|include|cover))",
    re.IGNORECASE,
)


def admits_not_knowing(answer: str) -> bool:
    # True when the answer says it does not know, cannot help, or that the documents do not say.
    return bool(UNKNOWN.search(answer.replace("’", "'")))


def leaked(answer: str, must_not_contain: list[str]) -> list[str]:
    # Text that must never appear (for example pieces of the system prompt).
    low = answer.lower()
    return [text for text in must_not_contain if text.lower() in low]
