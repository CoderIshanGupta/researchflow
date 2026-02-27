from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import httpx
import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import io
import pdfplumber
from uuid import uuid4

from app.core.supabase import get_supabase

router = APIRouter(prefix="/sources", tags=["Sources"])


# ---------- MODELS ----------

class Author(BaseModel):
    name: str
    affiliations: Optional[List[str]] = None


class Paper(BaseModel):
    id: str
    title: str
    authors: List[Author]
    abstract: Optional[str] = None
    year: Optional[int] = None
    citation_count: int = 0
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source_type: str  # 'semantic_scholar', 'arxiv', 'pubmed', 'uploaded'
    venue: Optional[str] = None


class SearchResponse(BaseModel):
    papers: List[Paper]
    total: int
    query: str
    sources_searched: List[str]


# ---------- KEYWORD REFINEMENT FOR SEARCH ----------

COMMON_STOPWORDS = {
    "the", "and", "of", "in", "on", "for", "to", "a", "an", "with",
    "using", "used", "based", "approach", "method", "methods", "study",
    "paper", "results", "from", "into", "via", "towards", "toward",
    "new", "analysis", "system", "framework", "application", "applications",
    "model", "models",
}

ML_STOPWORDS = {
    "deep", "learning", "deeplearning", "machine", "machinelearning",
    "neural", "networks", "network",
    "prediction", "predictive", "classifier", "classifiers",
    "review", "survey", "data", "dataset", "datasets",
    "computational", "artificial", "intelligence", "ai",
}


def extract_keywords(text: str, max_keywords: int = 6) -> List[str]:
    """
    Extract a small set of meaningful keywords from a title/topic string:
    - lowercase
    - remove punctuation
    - split on whitespace
    - remove common + generic ML stopwords
    - keep words length >= 4
    - return up to max_keywords
    """
    if not text:
        return []

    cleaned = re.sub(r"[^a-zA-Z0-9\s\-]", " ", text.lower())
    tokens = cleaned.split()

    keywords: List[str] = []
    seen: set[str] = set()

    for tok in tokens:
        if len(tok) < 4:
            continue
        if tok in COMMON_STOPWORDS or tok in ML_STOPWORDS:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        keywords.append(tok)

    return keywords[:max_keywords]


# ---------- MAIN SEARCH ENDPOINT ----------

@router.get("/search", response_model=SearchResponse)
async def search_papers(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    year_from: Optional[int] = Query(None, description="Filter papers from this year"),
    year_to: Optional[int] = Query(None, description="Filter papers until this year"),
    sort_by: str = Query("relevance", description="Sort by: relevance, citations, year"),
):
    """
    Search for papers across multiple sources (arXiv, Semantic Scholar, PubMed),
    with query refinement and simple filtering/sorting.
    """

    keywords = extract_keywords(query)
    refined_query = " ".join(keywords) if keywords else query
    print(f"[sources.search] Original query: '{query}' -> refined query: '{refined_query}'")

    papers: List[Paper] = []
    sources_searched: List[str] = []

    tasks = [
        search_arxiv(refined_query, limit),
        search_semantic_scholar(refined_query, limit, offset),
        search_pubmed(refined_query, limit),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # arXiv
    if isinstance(results[0], list):
        papers.extend(results[0])
        sources_searched.append("arXiv")
        print(f"[sources.search] arXiv: {len(results[0])} papers")
    else:
        print(f"[sources.search] arXiv error: {results[0]}")

    # Semantic Scholar
    if isinstance(results[1], list):
        papers.extend(results[1])
        sources_searched.append("Semantic Scholar")
        print(f"[sources.search] Semantic Scholar: {len(results[1])} papers")
    else:
        print(f"[sources.search] Semantic Scholar error: {results[1]}")

    # PubMed
    if isinstance(results[2], list):
        papers.extend(results[2])
        sources_searched.append("PubMed")
        print(f"[sources.search] PubMed: {len(results[2])} papers")
    else:
        print(f"[sources.search] PubMed error: {results[2]}")

    # Deduplicate by title (first 100 chars, case-insensitive)
    seen_titles = set()
    unique_papers: List[Paper] = []
    for p in papers:
        key = (p.title or "").lower().strip()[:100]
        if key not in seen_titles:
            seen_titles.add(key)
            unique_papers.append(p)

    # Year filters
    if year_from is not None:
        unique_papers = [p for p in unique_papers if p.year and p.year >= year_from]
    if year_to is not None:
        unique_papers = [p for p in unique_papers if p.year and p.year <= year_to]

    # Sort
    if sort_by == "citations":
        unique_papers.sort(key=lambda x: x.citation_count, reverse=True)
    elif sort_by == "year":
        unique_papers.sort(key=lambda x: x.year or 0, reverse=True)
    else:  # relevance heuristic
        current_year = datetime.now().year

        def relevance_score(p: Paper) -> float:
            citations = p.citation_count or 0
            year = p.year or 2000
            return citations * 0.7 + (year - 2000) * 10

        unique_papers.sort(key=relevance_score, reverse=True)

    return SearchResponse(
        papers=unique_papers[:limit],
        total=len(unique_papers),
        query=query,
        sources_searched=sources_searched,
    )


# ---------- ARXIV SEARCH ----------

async def search_arxiv(query: str, limit: int) -> List[Paper]:
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        content = resp.text

    root = ET.fromstring(content)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    papers: List[Paper] = []
    for entry in root.findall("atom:entry", ns):
        try:
            id_elem = entry.find("atom:id", ns)
            if id_elem is None or not id_elem.text:
                continue
            arxiv_id = id_elem.text.split("/abs/")[-1]

            title_elem = entry.find("atom:title", ns)
            title = "Untitled"
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip().replace("\n", " ")

            abstract_elem = entry.find("atom:summary", ns)
            abstract = None
            if abstract_elem is not None and abstract_elem.text:
                abstract = abstract_elem.text.strip().replace("\n", " ")[:2000]

            authors: List[Author] = []
            for a in entry.findall("atom:author", ns):
                name_elem = a.find("atom:name", ns)
                if name_elem is not None and name_elem.text:
                    authors.append(Author(name=name_elem.text))

            published_elem = entry.find("atom:published", ns)
            year = None
            if published_elem is not None and published_elem.text:
                try:
                    year = int(published_elem.text[:4])
                except ValueError:
                    year = None

            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            papers.append(
                Paper(
                    id=f"arxiv_{arxiv_id}",
                    title=title,
                    authors=authors or [Author(name="Unknown")],
                    abstract=abstract,
                    year=year,
                    citation_count=0,
                    url=f"https://arxiv.org/abs/{arxiv_id}",
                    pdf_url=pdf_url,
                    source_type="arxiv",
                    venue="arXiv",
                )
            )
        except Exception as e:
            print(f"[sources.arxiv] Error parsing entry: {e}")
            continue

    return papers


# ---------- SEMANTIC SCHOLAR SEARCH ----------

async def search_semantic_scholar(query: str, limit: int, offset: int) -> List[Paper]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": min(limit, 10),
        "offset": offset,
        "fields": "paperId,title,authors,abstract,year,citationCount,url,venue,openAccessPdf",
    }

    max_retries = 2
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 429 and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()

            papers: List[Paper] = []
            for item in data.get("data", []):
                try:
                    authors = [
                        Author(name=a.get("name", "Unknown"))
                        for a in item.get("authors", [])
                    ]
                    pdf_url = None
                    if item.get("openAccessPdf"):
                        pdf_url = item["openAccessPdf"].get("url")

                    abstract = item.get("abstract")
                    if abstract:
                        abstract = abstract[:2000]

                    papers.append(
                        Paper(
                            id=f"ss_{item.get('paperId', '')}",
                            title=item.get("title", "Untitled"),
                            authors=authors or [Author(name="Unknown")],
                            abstract=abstract,
                            year=item.get("year"),
                            citation_count=item.get("citationCount", 0) or 0,
                            url=item.get("url")
                            or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
                            pdf_url=pdf_url,
                            source_type="semantic_scholar",
                            venue=item.get("venue"),
                        )
                    )
                except Exception as e:
                    print(f"[sources.ss] Error parsing paper: {e}")
                    continue

            return papers

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                print(f"[sources.ss] HTTPStatusError: {e}")
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            print(f"[sources.ss] Error: {e}")
            raise

    return []


# ---------- PUBMED SEARCH ----------

async def search_pubmed(query: str, limit: int) -> List[Paper]:
    """
    Search PubMed (NCBI E-Utilities).
    """
    try:
        # Step 1: esearch
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance",
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            s_resp = await client.get(search_url, params=search_params)
            s_resp.raise_for_status()
            s_data = s_resp.json()

        idlist = s_data.get("esearchresult", {}).get("idlist", [])
        if not idlist:
            return []

        # Step 2: esummary
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(idlist),
            "retmode": "json",
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            f_resp = await client.get(fetch_url, params=fetch_params)
            f_resp.raise_for_status()
            f_data = f_resp.json()

        results = f_data.get("result", {})
        papers: List[Paper] = []

        for pmid in idlist:
            item = results.get(pmid)
            if not item:
                continue

            title = item.get("title", "Untitled")

            # Authors
            authors: List[Author] = []
            for a in item.get("authors", []):
                name = a.get("name")
                if name:
                    authors.append(Author(name=name))

            # Year from pubdate
            year = None
            pubdate = item.get("pubdate", "")
            if pubdate:
                try:
                    year = int(pubdate.split()[0])
                except Exception:
                    pass

            venue = item.get("source", "PubMed")

            papers.append(
                Paper(
                    id=f"pubmed_{pmid}",
                    title=title,
                    authors=authors or [Author(name="Unknown")],
                    abstract=None,
                    year=year,
                    citation_count=0,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    pdf_url=None,
                    source_type="pubmed",
                    venue=venue,
                )
            )

        return papers

    except Exception as e:
        print(f"[sources.pubmed] Error: {e}")
        raise


# ---------- ADD EXISTING PAPER TO SESSION ----------

class AddPaperRequest(BaseModel):
    session_id: str
    paper: Paper
    relevance_score: Optional[float] = None


@router.post("/add-to-session")
async def add_paper_to_session(request: AddPaperRequest):
    """
    Add a paper to a research session:
      - Upsert into 'papers'
      - Insert into 'session_papers'
    """
    supabase = get_supabase()

    try:
        paper_id = request.paper.id
        session_id = request.session_id

        paper_data = {
            "id": paper_id,
            "title": request.paper.title,
            "authors": [{"name": a.name} for a in request.paper.authors],
            "abstract": request.paper.abstract,
            "year": request.paper.year,
            "citation_count": request.paper.citation_count,
            "url": request.paper.url,
            "pdf_url": request.paper.pdf_url,
            "source_type": request.paper.source_type,
            "metadata": {"venue": request.paper.venue},
        }
        supabase.table_upsert("papers", paper_data, on_conflict="id")

        session_paper_data = {
            "session_id": session_id,
            "paper_id": paper_id,
            "relevance_score": request.relevance_score or 0.5,
        }
        supabase.table_insert("session_papers", session_paper_data)

        return {"message": "Paper added successfully", "paper_id": paper_id}

    except Exception as e:
        print(f"[sources.add_to_session] Error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to add paper: {str(e)}")


# ---------- ADD UPLOADED PDF TO SESSION ----------

class UploadedPaperRequest(BaseModel):
    session_id: str
    pdf_url: str
    filename: Optional[str] = None
    title: Optional[str] = None


@router.post("/add-uploaded")
async def add_uploaded_pdf(req: UploadedPaperRequest):
    """
    Add an uploaded PDF (stored in Supabase Storage) as a paper in this session.
    Steps:
      - Download PDF from pdf_url
      - Extract text from first page with pdfplumber
      - Derive a title (from req.title, filename, or first line)
      - Derive an abstract (short overview from first page text)
      - Guess a year if possible (from text or filename)
      - Insert into 'papers' with source_type='uploaded'
      - Link into 'session_papers'
    """
    supabase = get_supabase()

    # 1. Download PDF
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(req.pdf_url)
            resp.raise_for_status()
            pdf_bytes = resp.content
    except Exception as e:
        print(f"[sources.add_uploaded] Error downloading PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Could not download PDF: {e}")

    # 2. Extract text (first page) with pdfplumber
    first_page_text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if pdf.pages:
                first_page = pdf.pages[0]
                first_page_text = first_page.extract_text() or ""
    except Exception as e:
        print(f"[sources.add_uploaded] Error extracting text: {e}")
        # We'll still create a paper, just without abstract

    # 3. Derive title
    title = req.title
    if not title:
        # Try from filename
        if req.filename:
            base = req.filename.rsplit('.', 1)[0]
            title = base.replace('_', ' ').replace('-', ' ').strip()
        # Try from first non-empty line of first page
        if (not title) and first_page_text:
            first_line = first_page_text.splitlines()[0].strip()
            if len(first_line) > 5:
                title = first_line
        if not title:
            title = "Uploaded Paper"

    # 4. Derive abstract (short overview)
    abstract = None
    if first_page_text:
        abstract = first_page_text.strip()
        # Limit abstract length
        abstract = abstract[:2000]

    # 5. Guess year from text or filename
    year = None
    text_for_year = (first_page_text or "") + " " + (req.filename or "")
    m = re.search(r"(19|20)\d{2}", text_for_year)
    if m:
        try:
            year = int(m.group(0))
        except ValueError:
            year = None

    # 6. Create paper ID
    paper_id = f"upload_{uuid4().hex}"

    # 7. Insert into papers
    try:
        paper_data = {
            "id": paper_id,
            "title": title,
            "authors": [],  # unknown
            "abstract": abstract,
            "year": year,
            "citation_count": 0,
            "url": req.pdf_url,  # link to PDF page itself
            "pdf_url": req.pdf_url,
            "source_type": "uploaded",
            "metadata": {"filename": req.filename or "", "source": "uploaded"},
        }
        supabase.table_upsert("papers", paper_data, on_conflict="id")

        session_paper_data = {
            "session_id": req.session_id,
            "paper_id": paper_id,
            "relevance_score": 0.5,
        }
        supabase.table_insert("session_papers", session_paper_data)
    except Exception as e:
        print(f"[sources.add_uploaded] Error inserting into DB: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to save uploaded paper: {e}")

    return {"message": "Uploaded paper added successfully", "paper_id": paper_id}


# ---------- TEST ENDPOINT ----------

@router.get("/test")
async def test_apis():
    """
    Test all paper search APIs with a generic query.
    """
    results = {}
    try:
        arxiv = await search_arxiv("machine learning", 2)
        results["arxiv"] = {"status": "ok", "count": len(arxiv)}
    except Exception as e:
        results["arxiv"] = {"status": "error", "error": str(e)}

    try:
        ss = await search_semantic_scholar("machine learning", 2, 0)
        results["semantic_scholar"] = {"status": "ok", "count": len(ss)}
    except Exception as e:
        results["semantic_scholar"] = {"status": "error", "error": str(e)}

    try:
        pm = await search_pubmed("alzheimer", 2)
        results["pubmed"] = {"status": "ok", "count": len(pm)}
    except Exception as e:
        results["pubmed"] = {"status": "error", "error": str(e)}

    return results