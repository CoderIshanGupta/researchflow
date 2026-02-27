from typing import List, Dict
from functools import lru_cache
from groq import Groq
from app.core.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)


@lru_cache()
def get_groq_model() -> str:
    """
    Determine which Groq model to use:
    1. If GROQ_MODEL is set in .env, use that.
    2. Otherwise, call client.models.list() and pick a reasonable default
       from the models actually available to this API key.
    """
    env_model = getattr(settings, "GROQ_MODEL", None)
    if env_model:
        print(f"[llm] Using GROQ_MODEL from env: {env_model}")
        return env_model

    models = client.models.list()
    model_ids = [m.id for m in models.data]
    print("[llm] Available Groq models for this API key:", model_ids)

    preferred_patterns = [
        "llama-3.3-70b",
        "llama-3.2-90b",
        "llama-3.2-70b",
        "llama-3.2-11b",
        "llama-3.2-8b",
        "llama-3.2-3b",
        "llama-3.1-8b",
        "llama3-8b",
    ]

    for pattern in preferred_patterns:
        for mid in model_ids:
            if pattern in mid:
                print(f"[llm] Selected Groq model: {mid}")
                return mid

    if model_ids:
        print(f"[llm] No preferred model found, using first model: {model_ids[0]}")
        return model_ids[0]

    raise RuntimeError("No Groq models available for this API key.")


def _build_context_text(papers: List[Dict]) -> str:
    """
    Turn a list of papers into a context string:
    [Tag] Title (Year)
    Authors: ...
    Abstract: ...
    """
    chunks = []
    for i, p in enumerate(papers):
        title = p.get("title") or "Untitled"
        year = p.get("year") or "n.d."
        authors = ", ".join(p.get("authors") or [])
        abstract = p.get("abstract") or ""
        tag = p.get("tag") or f"Source-{i+1}"
        chunk = (
            f"[{tag}] {title} ({year})\n"
            f"Authors: {authors}\n"
            f"Abstract: {abstract[:700]}"
        )
        chunks.append(chunk)
    return "\n\n".join(chunks)


def generate_session_answer(question: str, papers: List[Dict]) -> str:
    """
    Used for the Chat tab: Q&A style answer grounded in the provided papers.
    Each paper dict may include: title, abstract, year, authors, tag.
    """
    if not papers:
        return "I don't have any sources in this session yet. Please add some papers first."

    context_text = _build_context_text(papers)

    system_prompt = (
        "You are an AI research assistant. Answer the user's question ONLY using the provided sources.\n"
        "Each source begins with a tag in square brackets, e.g. [Eeg-Alzheimer-2019].\n"
        "When you make a claim, cite the relevant source(s) by reusing EXACTLY those tags, "
        "e.g. '... [Eeg-Alzheimer-2019]'. Do NOT invent new tags.\n"
        "If the answer is not supported by these sources, say you don't know or that the sources don't cover it.\n"
    )

    user_prompt = (
        f"User question:\n{question}\n\n"
        f"Here are the available sources:\n{context_text}\n\n"
        "Now provide a concise, well-structured answer with inline citations using the tags."
    )

    model_name = get_groq_model()

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content


def generate_session_draft(topic: str, style: str, papers: List[Dict]) -> str:
    """
    Used for the Draft tab: generate a structured draft (summary or literature review)
    grounded in the provided papers.
    - topic: session title+topic
    - style: 'summary' or 'literature_review'
    """
    if not papers:
        return "I don't have any sources in this session yet. Please add some papers first."

    context_text = _build_context_text(papers)
    model_name = get_groq_model()

    # ----- Style-specific instructions -----

    if style == "summary":
        # SHORT, high-level, 2–4 paragraphs, minimal headings
        system_prompt = (
            "You are an AI research assistant. Write a SHORT textual summary based ONLY on the provided sources.\n"
            "Each source begins with a tag in square brackets, e.g. [Eeg-Alzheimer-2019].\n"
            "When you refer to a source, cite it inline using those tags, e.g. '[Eeg-Alzheimer-2019]'.\n"
            "Do NOT invent new tags. Do NOT include a long multi-section structure.\n"
            "The summary should be:\n"
            "- 2 to 4 paragraphs\n"
            "- High-level, focusing on overall goals, methods, and key findings\n"
            "- NO section headings except 'Summary' as a top-level heading\n"
            "- Avoid deep methodological detail; just highlight the main ideas.\n"
        )

        user_prompt = (
            f"Research topic:\n{topic}\n\n"
            f"Write a SHORT Summary of what these sources say about this topic.\n\n"
            f"Sources:\n{context_text}\n\n"
            "Output format:\n"
            "# Summary\n\n"
            "Then 2–4 paragraphs of text with inline citation tags like [Eeg-Alzheimer-2019]."
        )

        max_tokens = 900  # shorter summaries

    else:
        # LONGER, analytic literature review with multiple sections
        system_prompt = (
            "You are an AI research assistant. Write a DETAILED literature review based ONLY on the provided sources.\n"
            "Each source begins with a tag in square brackets, e.g. [Eeg-Alzheimer-2019].\n"
            "When you refer to a source, cite it inline using those tags, e.g. '[Eeg-Alzheimer-2019]'.\n"
            "Do NOT invent new tags. The literature review should:\n"
            "- Be roughly 1200–2000 words in length (not extremely short)\n"
            "- Have clear section headings:\n"
            "  Introduction; Background / Related Work; Methods / Approaches; Findings / Discussion;\n"
            "  Limitations and Future Work; Conclusion\n"
            "- Compare and contrast different sources, not just list them one by one\n"
            "- Highlight agreements, contradictions, gaps, and trends across papers.\n"
            "If some sections cannot be fully supported, keep those parts brief but still include them.\n"
        )

        user_prompt = (
            f"Research topic:\n{topic}\n\n"
            "Write a detailed literature review for this topic using ONLY the following sources:\n\n"
            f"{context_text}\n\n"
            "Remember to use the tags in square brackets from each source when citing it, like [Eeg-Alzheimer-2019].\n"
            "Do NOT add any sections other than the headings listed.\n"
        )

        max_tokens = 2048  # allow a longer output

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
    )

    return completion.choices[0].message.content