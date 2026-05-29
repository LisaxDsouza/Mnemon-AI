import os
import sys
import re
import json
import datetime
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple, Optional

# Append parent directory to sys.path to allow standalone executions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import models
from vector_store import VectorStoreManager

load_dotenv()

# ---------------------------------------------------------------------------
# Groq Client Initialization
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = None

if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("AgentSystem: Groq client initialized successfully.")
    except Exception as e:
        print(f"AgentSystem: WARNING — Could not initialize Groq client: {e}")
        groq_client = None
else:
    print("AgentSystem: WARNING — GROQ_API_KEY not found. Falling back to local NLTK planner.")

# ---------------------------------------------------------------------------
# Local NLTK Fallback (used when Groq is unavailable)
# ---------------------------------------------------------------------------

def _local_planner_fallback(query: str) -> Tuple[List[str], List[str]]:
    """Fallback: determines search keywords and source filters locally using simple tokenization."""
    try:
        import nltk
        from nltk.corpus import stopwords
        from nltk.tokenize import word_tokenize
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
        nltk.download('stopwords', quiet=True)
        tokens = word_tokenize(query.lower())
        english_stopwords = set(stopwords.words('english'))
        custom_exclusions = {"show", "me", "find", "search", "for", "what", "is", "how", "to"}
        all_exclusions = english_stopwords.union(custom_exclusions)
        keywords = [t for t in tokens if t.isalnum() and t not in all_exclusions]
    except Exception:
        keywords = [w for w in query.lower().split() if len(w) > 3]

    query_lower = query.lower()
    sources = []
    if any(w in query_lower for w in ["youtube", "video", "clip", "watch"]):
        sources.append("youtube")
    if any(w in query_lower for w in ["github", "code", "repo", "readme"]):
        sources.append("github")
    if any(w in query_lower for w in ["pdf", "document", "paper", "book"]):
        sources.append("pdf")
    if any(w in query_lower for w in ["google", "bing", "search engine"]):
        sources.append("search")

    if not sources:
        sources = ["web", "articles", "youtube", "github", "pdf", "search"]

    return keywords or [query], sources

# ---------------------------------------------------------------------------
# Agent 1: Planner Agent (LLM-Powered Query Expansion)
# ---------------------------------------------------------------------------

def llm_planner(query: str) -> Tuple[List[str], List[str]]:
    """
    Uses Groq LLM to expand the user query into rich search keywords
    and identify the best source type filters.
    Falls back to local NLTK on any failure.
    """
    if not groq_client:
        return _local_planner_fallback(query)

    system_prompt = """You are a search query planner for a personal memory retrieval system.
The user's browsing history is indexed from: YouTube videos, GitHub repositories, PDF documents, web articles, and search results.

Given a user query, you MUST return a valid JSON object with exactly these two fields:
{
  "search_keywords": ["keyword1", "keyword2", "keyword3", ...],
  "source_type_filter": ["youtube", "github", "pdf", "articles", "search"]
}

Rules:
- "search_keywords": 3-8 specific, semantically rich terms that best describe what the user is looking for. Rephrase and expand the query to maximize recall.
- "source_type_filter": Only include source types that are clearly relevant. If unsure, include all of them.
- Return ONLY the JSON object. No explanation, no markdown fences."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User query: {query}"}
            ],
            temperature=0.2,
            max_tokens=256
        )
        content = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)

        parsed = json.loads(content)
        keywords = parsed.get("search_keywords", [])
        sources = parsed.get("source_type_filter", [])

        if not keywords:
            raise ValueError("Empty keywords returned by planner.")

        return keywords, sources

    except Exception as e:
        print(f"PlannnerAgent: LLM planning failed ({e}), falling back to local planner.")
        return _local_planner_fallback(query)


# ---------------------------------------------------------------------------
# Agent 2: Re-Ranker Agent (LLM-Powered Relevance Scoring)
# ---------------------------------------------------------------------------

def llm_reranker(query: str, candidate_chunks: List[str], candidate_metas: List[Dict]) -> Tuple[List[str], List[Dict]]:
    """
    Uses Groq LLM to score each retrieved chunk for relevance and return
    only the top-5 most relevant chunks. Falls back to returning the raw
    top-5 candidates on any failure.
    """
    if not groq_client or not candidate_chunks:
        return candidate_chunks[:5], candidate_metas[:5]

    # Build a compact prompt listing each candidate chunk
    chunks_text = ""
    for i, (chunk, meta) in enumerate(zip(candidate_chunks, candidate_metas)):
        source_label = f"{meta.get('title', 'Unknown')} ({meta.get('location', 'General')})"
        preview = chunk[:300].replace("\n", " ")
        chunks_text += f"\n[{i}] SOURCE: {source_label}\nTEXT: {preview}\n"

    system_prompt = """You are a relevance scoring agent for a personal memory retrieval system.
You will receive a user query and a numbered list of text chunks from their browsing history.
Score each chunk's relevance to the query from 0 (completely irrelevant) to 10 (perfectly relevant).

Return ONLY a valid JSON array of objects in this exact format:
[{"index": 0, "score": 8}, {"index": 1, "score": 3}, ...]

Include ALL chunks in your response. Return ONLY the JSON array, nothing else."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User query: {query}\n\nChunks:\n{chunks_text}"}
            ],
            temperature=0.0,
            max_tokens=512
        )
        content = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)

        scores_list = json.loads(content)

        # Sort by descending score and pick top 5
        scores_list.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_indices = [item["index"] for item in scores_list[:5] if item["index"] < len(candidate_chunks)]

        top_chunks = [candidate_chunks[i] for i in top_indices]
        top_metas = [candidate_metas[i] for i in top_indices]
        return top_chunks, top_metas

    except Exception as e:
        print(f"ReRankerAgent: LLM re-ranking failed ({e}), using top raw candidates.")
        return candidate_chunks[:5], candidate_metas[:5]


# ---------------------------------------------------------------------------
# Agent 3: Summarizer Agent (LLM-Powered Grounded Synthesis)
# ---------------------------------------------------------------------------

def llm_summarizer(query: str, top_chunks: List[str], top_metas: List[Dict]) -> Dict[str, Any]:
    """
    Uses Groq LLM to synthesize a grounded final answer from the top-ranked
    chunks. Returns a dict with 'answer' (str) and 'citation' (dict).
    Falls back to a simple local extraction on any failure.
    """
    if not groq_client or not top_chunks:
        # Local fallback: return best chunk directly
        best_chunk = top_chunks[0] if top_chunks else "No relevant content found."
        best_meta = top_metas[0] if top_metas else {}
        return {
            "answer": f"From '{best_meta.get('title', 'Unknown')}' ({best_meta.get('location', 'General')}):\n{best_chunk}",
            "citation": {
                "quote": best_chunk[:200],
                "source": best_meta.get("title", "Unknown Page"),
                "url": best_meta.get("url", ""),
                "location": best_meta.get("location", "General")
            }
        }

    # Build context block for the LLM
    context_text = ""
    for i, (chunk, meta) in enumerate(zip(top_chunks, top_metas)):
        source_label = f"{meta.get('title', 'Unknown')} — {meta.get('url', '')} ({meta.get('location', 'General')})"
        context_text += f"\n[Context {i+1}]\nSource: {source_label}\n{chunk}\n"

    system_prompt = """You are a precise memory retrieval assistant. Your job is to answer the user's query using ONLY the provided context from their personal browsing history.

Rules:
1. Answer the query using ONLY the context below. Do not use outside knowledge.
2. Be concise and direct.
3. At the end, return a JSON citation block in this exact format:
---CITATION---
{"quote": "<exact quote from the most relevant context>", "source": "<page title>", "url": "<page url>", "location": "<section name>"}
---END---

If the context does not contain a relevant answer, say: "I couldn't find a relevant answer in your browsing history for this query."
Do NOT make up an answer."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User query: {query}\n\nContext from browsing history:\n{context_text}"}
            ],
            temperature=0.3,
            max_tokens=512
        )
        raw_output = response.choices[0].message.content.strip()

        # Split answer text from citation block
        citation_dict = None
        answer_text = raw_output

        if "---CITATION---" in raw_output and "---END---" in raw_output:
            parts = raw_output.split("---CITATION---")
            answer_text = parts[0].strip()
            citation_raw = parts[1].split("---END---")[0].strip()
            try:
                citation_dict = json.loads(citation_raw)
            except Exception:
                pass

        if not citation_dict:
            # Fallback citation from best metadata
            best_meta = top_metas[0] if top_metas else {}
            best_chunk = top_chunks[0] if top_chunks else ""
            citation_dict = {
                "quote": best_chunk[:200],
                "source": best_meta.get("title", "Unknown Page"),
                "url": best_meta.get("url", ""),
                "location": best_meta.get("location", "General")
            }

        return {"answer": answer_text, "citation": citation_dict}

    except Exception as e:
        print(f"SummarizerAgent: LLM summarization failed ({e}), using local fallback.")
        best_chunk = top_chunks[0] if top_chunks else "No relevant content found."
        best_meta = top_metas[0] if top_metas else {}
        return {
            "answer": f"From '{best_meta.get('title', 'Unknown')}' ({best_meta.get('location', 'General')}):\n{best_chunk}",
            "citation": {
                "quote": best_chunk[:200],
                "source": best_meta.get("title", "Unknown Page"),
                "url": best_meta.get("url", ""),
                "location": best_meta.get("location", "General")
            }
        }


# ---------------------------------------------------------------------------
# Agentic Retrieval System Orchestrator
# ---------------------------------------------------------------------------

class AgenticRetrievalSystem:
    def __init__(self, vector_store_manager: VectorStoreManager):
        self.vector_store = vector_store_manager

    def search_memories(
        self, query: str, user_id: str, db: Session
    ) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
        """
        Orchestrates the full 5-agent pipeline:
          1. Planner Agent  — Expands query into keywords & source filters.
          2. Retriever      — Hybrid FAISS + BM25 search for top 15 candidates.
          3. Re-Ranker Agent — LLM scores candidates and keeps top 5.
          4. Timeline Agent — Sorts top-5 chunks chronologically.
          5. Summarizer Agent — LLM drafts grounded answer with citations.
        """
        execution_logs: List[Dict[str, str]] = []

        # ---------------------------------------------------------------
        # 1. Planner Agent
        # ---------------------------------------------------------------
        planner_mode = "LLM (Groq)" if groq_client else "Local NLTK"
        execution_logs.append({
            "agent": "Planner Agent",
            "action": f"Decomposing search intent using {planner_mode}..."
        })

        keywords, sources = llm_planner(query)

        execution_logs.append({
            "agent": "Planner Agent",
            "action": f"Keywords: [{', '.join(keywords)}] | Filters: [{', '.join(sources)}]"
        })

        # Map source filter labels → DB source_type values
        source_type_map = {
            "web": ["web", "articles"],
            "articles": ["articles", "web"],
            "youtube": ["youtube"],
            "github": ["github"],
            "pdf": ["pdf"],
            "search": ["search"],
        }
        mapped_sources: List[str] = []
        for s in sources:
            mapped_sources.extend(source_type_map.get(s.lower(), [s.lower()]))
        mapped_sources = list(set(mapped_sources))

        # ---------------------------------------------------------------
        # 2. Retriever Agent (Hybrid FAISS + BM25)
        # ---------------------------------------------------------------
        execution_logs.append({
            "agent": "Retriever Agent",
            "action": "Executing hybrid FAISS + BM25 search for top 15 candidates..."
        })

        query_filter = db.query(models.MemoryEvent).filter(
            models.MemoryEvent.user_id == user_id,
            models.MemoryEvent.status == "extracted"
        )
        if mapped_sources:
            query_filter = query_filter.filter(
                models.MemoryEvent.source_type.in_(mapped_sources)
            )

        allowed_events = query_filter.all()
        allowed_ids = [e.id for e in allowed_events]

        if not allowed_ids:
            execution_logs.append({
                "agent": "Retriever Agent",
                "action": f"No indexed memories match the filters: [{', '.join(mapped_sources)}]."
            })
            return {
                "answer": (
                    "I couldn't find any memories matching your query filters. "
                    "Try browsing more content or relaxing your category settings."
                ),
                "citation": None
            }, execution_logs

        search_query_text = " ".join(keywords)
        search_results = self.vector_store.query(
            query_text=search_query_text,
            user_id=user_id,
            allowed_event_ids=allowed_ids,
            n_results=15   # Fetch 15 candidates for the re-ranker
        )

        candidate_chunks: List[str] = search_results["documents"][0]
        candidate_metas: List[Dict] = search_results["metadatas"][0]

        execution_logs.append({
            "agent": "Retriever Agent",
            "action": f"Retrieved {len(candidate_chunks)} candidate chunks from the vector store."
        })

        if not candidate_chunks:
            return {
                "answer": "No relevant memories found in your browsing history for this query.",
                "citation": None
            }, execution_logs

        # ---------------------------------------------------------------
        # 3. Re-Ranker Agent
        # ---------------------------------------------------------------
        reranker_mode = "LLM (Groq)" if groq_client else "Top-N passthrough"
        execution_logs.append({
            "agent": "Re-Ranker Agent",
            "action": f"Scoring {len(candidate_chunks)} candidates for relevance using {reranker_mode}..."
        })

        top_chunks, top_metas = llm_reranker(query, candidate_chunks, candidate_metas)

        execution_logs.append({
            "agent": "Re-Ranker Agent",
            "action": f"Selected top {len(top_chunks)} most relevant chunks after re-ranking."
        })

        # ---------------------------------------------------------------
        # 4. Timeline Agent (Chronological ordering)
        # ---------------------------------------------------------------
        execution_logs.append({
            "agent": "Timeline Agent",
            "action": "Reconstructing chronological context from top-ranked chunks..."
        })

        event_time_map = {e.id: e.created_at for e in allowed_events}
        chunk_timeline = []
        for chunk, meta in zip(top_chunks, top_metas):
            event_id = meta.get("memory_event_id")
            timestamp = event_time_map.get(event_id, datetime.datetime.utcnow())
            chunk_timeline.append((timestamp, chunk, meta))

        chunk_timeline.sort(key=lambda x: x[0])

        sorted_chunks = [c for _, c, _ in chunk_timeline]
        sorted_metas = [m for _, _, m in chunk_timeline]

        if chunk_timeline:
            time_from = chunk_timeline[0][0].strftime("%Y-%m-%d %H:%M")
            time_to = chunk_timeline[-1][0].strftime("%Y-%m-%d %H:%M")
            execution_logs.append({
                "agent": "Timeline Agent",
                "action": f"Context ordered from {time_from} → {time_to}."
            })

        # ---------------------------------------------------------------
        # 5. Summarizer Agent
        # ---------------------------------------------------------------
        summarizer_mode = "LLM (Groq)" if groq_client else "Local extraction"
        execution_logs.append({
            "agent": "Summarizer Agent",
            "action": f"Synthesizing grounded answer using {summarizer_mode}..."
        })

        result = llm_summarizer(query, sorted_chunks, sorted_metas)
        answer_text = result["answer"]
        citation = result["citation"]

        # Persist query log to DB
        try:
            query_log = models.RecallQuery(
                user_id=user_id,
                query=query,
                response_summary=answer_text[:500]
            )
            db.add(query_log)
            db.commit()
        except Exception as e:
            print(f"AgentSystem: Could not persist query log: {e}")

        execution_logs.append({
            "agent": "Summarizer Agent",
            "action": "Response synthesized and citations generated successfully."
        })

        return {"answer": answer_text, "citation": citation}, execution_logs
