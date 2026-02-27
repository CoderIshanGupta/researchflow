from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Set
from enum import Enum
import re

from app.core.supabase import get_supabase
from app.core.llm import generate_session_draft

router = APIRouter(prefix="/draft", tags=["Drafts"])

# --- basic tokenization and relevance scoring (free, no embeddings) ---

CHAT_STOPWORDS = {
    "the", "and", "of", "in", "on", "for", "to", "a", "an", "with",
    "using", "used", "based", "approach", "method", "methods", "study",
    "paper", "results", "from", "into", "via", "towards", "toward",
    "new", "analysis", "system", "framework", "application", "applications",
    "model", "models", "deep", "learning", "machine", "neural", "network",
    "networks", "data", "dataset", "datasets",
}


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    cleaned = re.sub(r"[^a-zA-Z0-9\s\-]", " ", text.lower())
    tokens = cleaned.split()
    return {t for t in tokens if len(t) >= 3 and t not in CHAT_STOPWORDS}


def select_relevant_papers(question: str, papers: List[Dict], top_k: int = 8) -> List[Dict]:
    q_tokens = _tokenize(question)
    if not q_tokens:
        return papers[:top_k]

    scored: List[tuple[int, Dict]] = []
    for p in papers:
        text = (p.get("title") or "") + " " + (p.get("abstract") or "")
        p_tokens = _tokenize(text)
        score = len(q_tokens & p_tokens)
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    if scored and scored[0][0] == 0:
        return papers[:top_k]

    return [p for (s, p) in scored[:top_k]]


def make_citation_tag(p: Dict, idx: int) -> str:
    """
    Build a human-readable tag for a paper, e.g. 'EEG-Alzheimer-2019'.
    """
    year = p.get("year") or "n.d."
    title = p.get("title") or ""
    authors = p.get("authors") or []

    tokens = _tokenize(title)
    keywords = sorted(tokens)

    if keywords:
        core = "-".join(kw.capitalize() for kw in keywords[:2])
        tag = f"{core}-{year}"
    elif authors:
        surname = authors[0].split()[-1]
        tag = f"{surname}{year}"
    else:
        tag = f"Source-{idx+1}"

    return tag[:40]


# --- request/response models for draft generation ---

class DraftRequest(BaseModel):
    session_id: str
    style: Optional[str] = "literature_review"  # or 'summary', etc.


class DraftResponse(BaseModel):
    content: str


# --- main draft generation endpoint ---

@router.post("/generate", response_model=DraftResponse)
async def generate_draft(req: DraftRequest):
    """
    Generate a structured draft (e.g. literature review) for a session
    using the session's sources and Groq LLM.
    """
    supabase = get_supabase()

    # 1. Fetch the session (title + topic)
    try:
        sess_rows = supabase.table_select(
            "research_sessions",
            "id,title,topic",
            {"id": req.session_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error (session): {e}")

    if not sess_rows:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = sess_rows[0]
    topic_text = f"{sess.get('title') or ''} {sess.get('topic') or ''}".strip()
    if not topic_text:
        topic_text = "this research topic"

    # 2. Fetch session_papers joined with papers
    try:
        rows = supabase.table_select(
            "session_papers",
            "paper_id,relevance_score,papers(*)",
            {"session_id": req.session_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error (papers): {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="No sources in this session yet")

    # 3. Build list of papers
    all_papers: List[Dict] = []
    for idx, item in enumerate(rows):
        p = item.get("papers") or {}
        authors_list: List[str] = []
        for a in p.get("authors") or []:
            name = a.get("name")
            if name:
                authors_list.append(name)

        base_paper = {
            "paper_id": p.get("id"),
            "title": p.get("title"),
            "abstract": p.get("abstract"),
            "year": p.get("year"),
            "authors": authors_list,
        }
        tag = make_citation_tag(base_paper, idx)
        base_paper["tag"] = tag
        all_papers.append(base_paper)

    # 4. Select relevant subset
    context_papers = select_relevant_papers(topic_text, all_papers, top_k=8)

    # 5. Ask LLM for draft
    try:
        draft_text = generate_session_draft(
            topic_text, req.style or "literature_review", context_papers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    return DraftResponse(content=draft_text)


# -------------------------------------------------------------------
# BIBLIOGRAPHY EXPORT (BibTeX / APA / MLA / IEEE) FOR A SESSION
# -------------------------------------------------------------------

class BibliographyStyle(str, Enum):
    bibtex = "bibtex"
    apa = "apa"
    mla = "mla"
    ieee = "ieee"


class BibliographyResponse(BaseModel):
    style: BibliographyStyle
    entries: List[str]
    text: str


def _split_name(full: str) -> tuple[Optional[str], Optional[str]]:
    """Very simple 'First Last' splitter."""
    if not full:
        return None, None
    parts = full.strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return None, parts[0]
    first = " ".join(parts[:-1])
    last = parts[-1]
    return first, last


def _authors_apa(authors: List[str]) -> str:
    """
    Simplified APA:
      'Last, F. M., & Last, F. M.'
    """
    formatted: List[str] = []
    for name in authors:
        first, last = _split_name(name)
        if not last:
            continue
        initials = ""
        if first:
            for part in first.split():
                if not part:
                    continue
                initials += f"{part[0].upper()}."
                initials += " "
            initials = initials.strip()
        if initials:
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(last)

    if not formatted:
        return ""

    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + ", & " + formatted[-1]


def _authors_mla(authors: List[str]) -> str:
    """
    Simplified MLA:
      1 author: 'Last, First'
      2: 'Last, First, and First Last'
      3+: 'Last, First, et al.'
    """
    if not authors:
        return ""

    first, last = _split_name(authors[0])
    main = f"{last}, {first}" if first and last else authors[0]

    if len(authors) == 1:
        return main
    if len(authors) == 2:
        return f"{main}, and {authors[1]}"
    return f"{main}, et al."


def _authors_ieee(authors: List[str]) -> str:
    """
    Simplified IEEE authors:
      One:   F. M. Last
      Many:  F. M. Last, F. M. Last, and F. M. Last
    """
    if not authors:
        return ""

    parts: List[str] = []

    def fmt(name: str) -> str:
        first, last = _split_name(name)
        if not last:
            return name
        initials = ""
        if first:
            for part in first.split():
                if not part:
                    continue
                initials += f"{part[0].upper()}."
                initials += " "
            initials = initials.strip()
        if initials:
            return f"{initials} {last}"
        return last

    if len(authors) == 1:
        return fmt(authors[0])

    # all except last
    for name in authors[:-1]:
        parts.append(fmt(name))
    # last with 'and'
    parts.append(f"and {fmt(authors[-1])}")
    return ", ".join(parts)


def _make_bibtex_key(p: Dict, used_keys: Set[str]) -> str:
    """
    Very simple key: lastnameYearFirstWord, made unique in 'used_keys'.
    """
    authors = p.get("authors") or []
    if authors:
        _, last = _split_name(authors[0])
        last = (last or "anon").lower()
    else:
        last = "anon"

    year = str(p.get("year")) if p.get("year") else "nd"
    title = p.get("title") or ""
    first_word = title.split()[0].lower() if title else "title"

    base = f"{last}{year}{first_word}"
    key = base
    i = 2
    while key in used_keys:
        key = f"{base}{i}"
        i += 1
    used_keys.add(key)
    return key


def _format_bibtex(papers: List[Dict]) -> List[str]:
    entries: List[str] = []
    used_keys: Set[str] = set()

    for p in papers:
        key = _make_bibtex_key(p, used_keys)
        entry_lines = [
            f"@article{{{key},",
            f"  title   = {{{p.get('title', '')}}},",
        ]
        authors = p.get("authors") or []
        if authors:
            entry_lines.append(f"  author  = {{{' and '.join(authors)}}},")

        container = p.get("container_title")
        if container:
            entry_lines.append(f"  journal = {{{container}}},")

        year = p.get("year")
        if year:
            entry_lines.append(f"  year    = {{{year}}},")

        volume = p.get("volume")
        if volume:
            entry_lines.append(f"  volume  = {{{volume}}},")

        issue = p.get("issue")
        if issue:
            entry_lines.append(f"  number  = {{{issue}}},")

        pages = p.get("pages")
        if pages:
            entry_lines.append(f"  pages   = {{{pages}}},")

        doi = p.get("doi")
        if doi:
            entry_lines.append(f"  doi     = {{{doi}}},")

        url = p.get("url")
        if url:
            entry_lines.append(f"  url     = {{{url}}},")

        entry_lines.append("}")
        entries.append("\n".join(entry_lines))

    return entries


def _format_apa(papers: List[Dict]) -> List[str]:
    """
    Very simplified APA 7 style (journal-article-like).
    """
    results: List[str] = []
    for p in papers:
        authors = _authors_apa(p.get("authors") or [])
        year = f"({p.get('year')})." if p.get("year") else "(n.d.)."
        title = (p.get("title") or "").rstrip(".")
        container = p.get("container_title") or ""
        volume_issue = ""
        if p.get("volume"):
            volume_issue = str(p["volume"])
            if p.get("issue"):
                volume_issue += f"({p['issue']})"
        pages = f", {p['pages']}" if p.get("pages") else ""
        doi_url = ""
        if p.get("doi"):
            doi_url = f" https://doi.org/{p['doi']}"
        elif p.get("url"):
            doi_url = f" {p['url']}"

        ref = f"{authors} {year} {title}."
        if container:
            ref += f" {container}"
        if volume_issue:
            ref += f", {volume_issue}"
        if pages:
            ref += pages
        ref += f".{doi_url}"

        results.append(ref.strip())

    return results


def _format_mla(papers: List[Dict]) -> List[str]:
    """
    Simplified MLA 9 style (journal-article-like).
    """
    results: List[str] = []
    for p in papers:
        authors = _authors_mla(p.get("authors") or [])
        title = (p.get("title") or "").rstrip(".")
        container = p.get("container_title") or ""
        year = str(p.get("year")) if p.get("year") else "n.d."
        volume = p.get("volume") or ""
        issue = p.get("issue") or ""
        pages = p.get("pages") or ""
        url = p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")

        pieces: List[str] = []
        if authors:
            pieces.append(f"{authors}.")
        pieces.append(f"\"{title}.\"")
        if container:
            pieces.append(container + ",")
        vol_issue: List[str] = []
        if volume:
            vol_issue.append(f"vol. {volume}")
        if issue:
            vol_issue.append(f"no. {issue}")
        if vol_issue:
            pieces.append(", ".join(vol_issue) + ",")
        if pages:
            pieces.append(f"pp. {pages},")
        pieces.append(year + ".")
        if url:
            pieces.append(url)

        results.append(" ".join(piece for piece in pieces if piece))

    return results


def _format_ieee(papers: List[Dict]) -> List[str]:
    """
    Simplified IEEE style:
      [1] A. B. Author and C. D. Author, "Title," Journal, vol. X, no. Y, pp. Z–W, Year. URL/DOI
    """
    results: List[str] = []
    for idx, p in enumerate(papers):
        authors = _authors_ieee(p.get("authors") or [])
        title = (p.get("title") or "").rstrip(".")
        container = p.get("container_title") or ""
        year = str(p.get("year")) if p.get("year") else "n.d."
        volume = p.get("volume") or ""
        issue = p.get("issue") or ""
        pages = p.get("pages") or ""
        url = p.get("url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")

        parts: List[str] = [f"[{idx+1}]"]
        if authors:
            parts.append(authors + ",")
        if title:
            parts.append(f"\"{title},\"")
        if container:
            parts.append(container + ",")
        vol_issue: List[str] = []
        if volume:
            vol_issue.append(f"vol. {volume}")
        if issue:
            vol_issue.append(f"no. {issue}")
        if vol_issue:
            parts.append(", ".join(vol_issue) + ",")
        if pages:
            parts.append(f"pp. {pages},")
        parts.append(year + ".")
        if url:
            parts.append(url)

        results.append(" ".join(part for part in parts if part))

    return results


def _generate_bibliography(papers: List[Dict], style: BibliographyStyle) -> Dict[str, object]:
    # Deduplicate by paper id
    seen_ids: Set[str] = set()
    unique_papers: List[Dict] = []
    for p in papers:
        pid = p.get("id")
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        unique_papers.append(p)

    if style == BibliographyStyle.bibtex:
        entries = _format_bibtex(unique_papers)
    elif style == BibliographyStyle.apa:
        entries = _format_apa(unique_papers)
    elif style == BibliographyStyle.mla:
        entries = _format_mla(unique_papers)
    elif style == BibliographyStyle.ieee:
        entries = _format_ieee(unique_papers)
    else:
        entries = []

    text = "\n\n".join(entries)
    return {"style": style, "entries": entries, "text": text}


@router.get("/bibliography", response_model=BibliographyResponse)
async def get_bibliography(
    session_id: str = Query(..., description="Research session ID"),
    style: BibliographyStyle = Query(BibliographyStyle.bibtex, description="bibtex | apa | mla | ieee"),
):
    """
    Generate a bibliography for ALL papers in a session, in the chosen style.
    Uses:
      - session_papers (to find paper_ids for this session)
      - papers (to get title/authors/year/url/metadata)
    """
    supabase = get_supabase()

    # 1) Fetch session_papers joined with papers
    try:
        rows = supabase.table_select(
            "session_papers",
            "paper_id,papers(*)",
            {"session_id": session_id},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DB error (session_papers): {e}",
        )

    if not rows:
        # No sources in this session -> empty bibliography
        return BibliographyResponse(style=style, entries=[], text="")

    # 2) Build metadata list
    papers_meta: List[Dict] = []

    for item in rows:
        p = item.get("papers") or {}
        meta = p.get("metadata") or {}

        authors_raw = p.get("authors") or []
        authors: List[str] = []
        for a in authors_raw:
            if isinstance(a, dict):
                name = a.get("name")
                if name:
                    authors.append(name)

        paper_meta = {
            "id": p.get("id") or "",
            "title": p.get("title") or "",
            "authors": authors,
            "year": p.get("year"),
            "container_title": meta.get("journal") or meta.get("venue"),
            "publisher": meta.get("publisher"),
            "volume": meta.get("volume"),
            "issue": meta.get("issue"),
            "pages": meta.get("pages"),
            "doi": meta.get("doi"),
            "url": p.get("url"),
        }
        papers_meta.append(paper_meta)

    # 3) Format bibliography
    result = _generate_bibliography(papers_meta, style)

    return BibliographyResponse(
        style=result["style"],
        entries=result["entries"],
        text=result["text"],
    )