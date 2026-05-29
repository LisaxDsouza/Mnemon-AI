import unittest
import json
from unittest.mock import MagicMock, patch
from backend.agents import (
    _local_planner_fallback,
    llm_planner,
    llm_reranker,
    llm_summarizer,
    AgenticRetrievalSystem,
)


# ---------------------------------------------------------------------------
# Tests for Local NLTK Fallback Planner
# ---------------------------------------------------------------------------

class TestLocalPlannerFallback(unittest.TestCase):

    def test_youtube_source_filter(self):
        """Queries mentioning video/youtube should map to the youtube filter."""
        keywords, sources = _local_planner_fallback("find me a youtube video on react hooks")
        self.assertIn("youtube", sources)
        self.assertIn("react", keywords)

    def test_github_source_filter(self):
        """Queries mentioning github/repo should map to the github filter."""
        keywords, sources = _local_planner_fallback("search github readme for docker config")
        self.assertIn("github", sources)
        self.assertIn("docker", keywords)

    def test_pdf_source_filter(self):
        """Queries mentioning pdf/paper should filter to pdf."""
        keywords, sources = _local_planner_fallback("look up the pdf document for research paper")
        self.assertIn("pdf", sources)
        self.assertIn("research", keywords)

    def test_fallback_includes_all_sources_for_general_query(self):
        """Generic queries should default to all source types."""
        keywords, sources = _local_planner_fallback("how to setup nextjs routing")
        self.assertNotIn("how", keywords)
        self.assertNotIn("to", keywords)
        self.assertIn("nextjs", keywords)
        self.assertIn("routing", keywords)
        self.assertGreater(len(sources), 3)


# ---------------------------------------------------------------------------
# Tests for LLM Planner Agent (with Groq mocked)
# ---------------------------------------------------------------------------

class TestLLMPlanner(unittest.TestCase):

    @patch("backend.agents.groq_client")
    def test_llm_planner_parses_keywords_and_sources(self, mock_client):
        """Verifies that the LLM planner correctly parses the Groq response JSON."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "search_keywords": ["react", "hooks", "state", "tutorial"],
            "source_type_filter": ["youtube", "articles"]
        })
        mock_client.chat.completions.create.return_value = mock_response

        keywords, sources = llm_planner("teach me about react hooks")

        self.assertIn("react", keywords)
        self.assertIn("hooks", keywords)
        self.assertIn("youtube", sources)

    @patch("backend.agents.groq_client")
    def test_llm_planner_falls_back_on_bad_json(self, mock_client):
        """If the LLM returns garbage JSON, the planner should fall back gracefully."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "I am not a JSON response."
        mock_client.chat.completions.create.return_value = mock_response

        keywords, sources = llm_planner("some random query")

        # Should not crash; returns at least one keyword
        self.assertIsInstance(keywords, list)
        self.assertIsInstance(sources, list)
        self.assertGreater(len(keywords), 0)


# ---------------------------------------------------------------------------
# Tests for LLM Re-Ranker Agent (with Groq mocked)
# ---------------------------------------------------------------------------

class TestLLMReRanker(unittest.TestCase):

    @patch("backend.agents.groq_client")
    def test_reranker_selects_top_chunks_by_score(self, mock_client):
        """Verifies that the re-ranker correctly selects the highest-scored chunks."""
        mock_response = MagicMock()
        # Scores: index 2 is best (9), then 0 (7), then 1 (2)
        mock_response.choices[0].message.content = json.dumps([
            {"index": 0, "score": 7},
            {"index": 1, "score": 2},
            {"index": 2, "score": 9},
        ])
        mock_client.chat.completions.create.return_value = mock_response

        chunks = ["chunk A", "chunk B", "chunk C"]
        metas = [{"title": "A"}, {"title": "B"}, {"title": "C"}]

        top_chunks, top_metas = llm_reranker("my query", chunks, metas)

        # First result should be the highest-scoring chunk (index 2)
        self.assertEqual(top_chunks[0], "chunk C")
        self.assertEqual(top_metas[0]["title"], "C")

    @patch("backend.agents.groq_client")
    def test_reranker_falls_back_on_bad_json(self, mock_client):
        """If Groq returns invalid JSON, the re-ranker should return raw top-5."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "not json"
        mock_client.chat.completions.create.return_value = mock_response

        chunks = [f"chunk {i}" for i in range(10)]
        metas = [{"title": f"t{i}"} for i in range(10)]

        top_chunks, top_metas = llm_reranker("query", chunks, metas)
        self.assertEqual(len(top_chunks), 5)


# ---------------------------------------------------------------------------
# Tests for LLM Summarizer Agent (with Groq mocked)
# ---------------------------------------------------------------------------

class TestLLMSummarizer(unittest.TestCase):

    @patch("backend.agents.groq_client")
    def test_summarizer_extracts_answer_and_citation(self, mock_client):
        """Verifies that the summarizer correctly splits answer text and citation block."""
        citation_json = json.dumps({
            "quote": "React hooks allow functional components to use state.",
            "source": "React Docs",
            "url": "https://react.dev",
            "location": "Introduction"
        })
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "React hooks are functions that let you use state in functional components.\n"
            f"---CITATION---\n{citation_json}\n---END---"
        )
        mock_client.chat.completions.create.return_value = mock_response

        result = llm_summarizer(
            "What are React hooks?",
            ["React hooks allow functional components to use state."],
            [{"title": "React Docs", "url": "https://react.dev", "location": "Introduction"}]
        )

        self.assertIn("hooks", result["answer"].lower())
        self.assertEqual(result["citation"]["source"], "React Docs")
        self.assertEqual(result["citation"]["url"], "https://react.dev")

    @patch("backend.agents.groq_client")
    def test_summarizer_falls_back_on_no_citation_block(self, mock_client):
        """If the LLM response has no citation block, falls back to metadata."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "A plain answer without citation markers."
        mock_client.chat.completions.create.return_value = mock_response

        result = llm_summarizer(
            "query",
            ["some chunk"],
            [{"title": "Some Page", "url": "http://example.com", "location": "Main"}]
        )

        self.assertIn("answer", result)
        self.assertIn("citation", result)
        self.assertEqual(result["citation"]["source"], "Some Page")


if __name__ == "__main__":
    unittest.main()
