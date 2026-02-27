from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import re

from app.core.supabase import get_supabase
from app.core.llm import generate_session_answer

router = APIRouter(prefix="/rag", tags=["RAG"])

# ---------- SIMPLE KEYWORD-BASED RETRIEVAL ----------

CHAT_STOPWORDS = {
    "the", "and", "of", "in", "on", "for", "to", "a", "an", "with",
    "using", "based", "approach", "method", "methods", "study", "paper",
    "results", "from", "into", "via", "towards", "toward", "new",
    "analysis", "system", "framework", "application", "applications",
    "model", "models", "deep", "learning", "machine", "neural", "network",
    "networks", "data", "dataset", "datasets"
}


def _tokenize(text: str) -> set[str]:
    """
    Very simple tokenizer: lowercase, remove punctuation, split, remove stopwords.
    """
    if not text:
        return set()
    cleaned = re.sub(r"[^a-zA-Z0-9\s\-]", " ", text.lower())
    tokens = cleaned.split()
    return {t for t in tokens if len(t) >= 3 and t not in CHAT_STOPWORDS}


def select_relevant_papers(question: str, papers: List[Dict], top_k: int = 5) -> List[Dict]:
    """
    Score papers by keyword overlap with the question and return top_k.
    """
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

    # If everything scores zero, just take first top_k as fallback
    if scored and scored[0][0] == 0:
        return papers[:top_k]

    return [p for (s, p) in scored[:top_k]]


def make_citation_tag(p: Dict) -> str:
    """
    Build a human-readable tag for a paper, e.g. 'EEG-Alzheimer-2019'.
    Uses title keywords + year or first author surname.
    """
    year = p.get("year") or "n.d."
    title = p.get("title") or ""
    authors = p.get("authors") or []

    tokens = _tokenize(title)
    keywords = sorted(tokens)

    if keywords:
        # take first 2 keywords, capitalize
        core = "-".join(kw.capitalize() for kw in keywords[:2])
        tag = f"{core}-{year}"
    elif authors:
        surname = authors[0].split()[-1]
        tag = f"{surname}{year}"
    else:
        tag = f"Source-{year}"

    # Keep it manageable length
    return tag[:40]


# ---------- MODELS ----------

class ChatSource(BaseModel):
    paper_id: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    authors: List[str]
    tag: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]


class ChatMessageOut(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    created_at: Optional[datetime] = None


# ---------- CHAT ENDPOINT ----------

@router.post("/chat", response_model=ChatResponse)
async def chat_with_session(req: ChatRequest):
    """
    Chat over the papers in a research session:
      - Fetch session_papers joined with papers
      - Select most relevant papers for this question
      - Ask Groq LLM for an answer with citations
      - Save Q&A into chat_messages
    """
    supabase = get_supabase()

    # 1. Fetch session_papers joined with papers
    try:
        rows = supabase.table_select(
            "session_papers",
            "paper_id,relevance_score,papers(*)",
            {"session_id": req.session_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="No sources in this session yet")

    # 2. Build list of paper dicts for retrieval & LLM
    all_papers: List[Dict] = []
    for item in rows:
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
        tag = make_citation_tag(base_paper)
        base_paper["tag"] = tag
        all_papers.append(base_paper)

    # 3. Select top-k relevant papers for this question
    context_papers = select_relevant_papers(req.question, all_papers, top_k=5)

    # 4. Ask LLM
    try:
        answer = generate_session_answer(req.question, context_papers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    # 5. Save chat messages (user + assistant) into chat_messages
    try:
        # user message
        supabase.table_insert(
            "chat_messages",
            {
                "session_id": req.session_id,
                "role": "user",
                "content": req.question,
                "cited_papers": None,
            },
        )
        # assistant message with cited paper tags
        supabase.table_insert(
            "chat_messages",
            {
                "session_id": req.session_id,
                "role": "assistant",
                "content": answer,
                "cited_papers": [p.get("paper_id") for p in context_papers],
            },
        )
    except Exception as e:
        # Don't fail the chat if saving history fails
        print(f"[rag.chat] Warning: failed to save chat messages: {e}")

    # 6. Build sources array for response
    sources_for_response = [
        ChatSource(
            paper_id=p.get("paper_id"),
            title=p.get("title"),
            abstract=p.get("abstract"),
            year=p.get("year"),
            authors=p.get("authors") or [],
            tag=p.get("tag"),
        )
        for p in context_papers
    ]

    return ChatResponse(answer=answer, sources=sources_for_response)


# ---------- CHAT HISTORY ENDPOINT ----------

@router.get("/history", response_model=List[ChatMessageOut])
async def get_chat_history(session_id: str = Query(..., description="Session ID")):
    """
    Return all chat messages (user + assistant) for a session, sorted by created_at.
    """
    supabase = get_supabase()
    try:
        rows = supabase.table_select(
            "chat_messages",
            "role,content,created_at",
            {"session_id": session_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # Sort by created_at ascending
    rows_sorted = sorted(
        rows,
        key=lambda r: r.get("created_at") or "",
    )

    messages: List[ChatMessageOut] = [
        ChatMessageOut(
            role=row.get("role", "assistant"),
            content=row.get("content", ""),
            created_at=row.get("created_at"),
        )
        for row in rows_sorted
    ]

    return messages