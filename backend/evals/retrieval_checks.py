from answering.insur_llm import retrieve_chunks


def retrieve_only(question: str) -> list[dict]:
    # Only the search step (embed the question, search the index), no chat model. Cheap, so it can run on its own.
    return [
        {"source": c.metadata.get("source"), "page": c.metadata.get("page_label"), "text": c.page_content}
        for c in retrieve_chunks(question)
    ]


def check_retrieval(expected_sources: list[dict], chunks: list[dict]) -> tuple[int, int, list[str]]:
    # Did the search find the pages that hold the answer? Returns (found, total, missing "file page N").
    got = {(str(c.get("source")), str(c.get("page"))) for c in chunks}
    missing = [f"{s['file']} page {s['page']}" for s in expected_sources if (s["file"], s["page"]) not in got]
    return len(expected_sources) - len(missing), len(expected_sources), missing
