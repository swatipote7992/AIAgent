import re
from collections import Counter

from langchain_core.documents import Document

MIN_PAGE_CHARS = 20  # pages with less text than this are treated as empty / extraction errors
EDGE_LINES = 2  # how many lines at the top and bottom of a page count as header / footer candidates
REPEAT_RATIO = 0.5  # an edge line repeated on at least this share of pages is a header / footer
MAX_EDGE_LINE_CHARS = 80  # longer lines are policy wording, not headers / footers

PAGE_NUMBER_RE = re.compile(r"^\s*(page\s+)?\d+(\s*(of|/)\s*\d+)?\s*$", re.IGNORECASE)


def _normalise(line: str) -> str:
    """Key used to compare lines across pages. Only 'Page N of M' numbers are masked so that
    numbered clauses and section headings are never mistaken for a repeated footer."""
    text = re.sub(r"\s+", " ", line.strip().lower())
    return re.sub(r"page \d+( (of|/) \d+)?", "page #", text)


def find_repeated_edge_lines(documents: list[Document]) -> set[str]:
    """Return normalised lines that repeat at the top/bottom of many pages (headers and footers)."""
    counts: Counter[str] = Counter()
    for doc in documents:
        lines = [ln for ln in doc.page_content.splitlines() if ln.strip()]
        if len(lines) <= 2 * EDGE_LINES:
            continue  # too short to tell edges from body text; never strip content from these pages
        edges = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
        counts.update({_normalise(ln) for ln in edges if len(ln.strip()) <= MAX_EDGE_LINE_CHARS})
    threshold = max(2, int(len(documents) * REPEAT_RATIO))
    return {line for line, n in counts.items() if n >= threshold}


def clean_page_text(text: str, repeated_edges: set[str]) -> str:
    """Remove headers/footers and extra whitespace. Wording, numbering and case are left untouched."""
    kept = []
    for line in text.splitlines():
        if PAGE_NUMBER_RE.match(line) or _normalise(line) in repeated_edges:
            continue
        kept.append(re.sub(r"[ \t ]+", " ", line).strip())
    cleaned = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()  # keep paragraph breaks, drop repeated blank lines


def clean_documents(documents: list[Document]) -> list[Document]:
    """Clean every page and drop empty pages. Prints what was removed so nothing disappears silently."""
    repeated_edges = find_repeated_edge_lines(documents)
    if repeated_edges:
        print(f"Removed repeated header/footer lines: {sorted(repeated_edges)}")

    cleaned_docs = []
    for doc in documents:
        text = clean_page_text(doc.page_content, repeated_edges)
        if len(text) < MIN_PAGE_CHARS:
            print(f"Skipped empty/short page {doc.metadata.get('page_label', doc.metadata.get('page'))}")
            continue
        cleaned_docs.append(Document(page_content=text, metadata=doc.metadata))
    return cleaned_docs
