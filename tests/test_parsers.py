import unittest
from backend.parsers import get_parser_for_url
from backend.parsers.parser_factory import get_parser, StackOverflowParser, GitHubParser, GenericParser

class TestParsers(unittest.TestCase):
    def test_routing_stackoverflow(self):
        """Verifies that stackoverflow URLs route to the StackOverflow parser class."""
        parser = get_parser("https://stackoverflow.com/questions/12345/how-to-do-this")
        self.assertIsInstance(parser, StackOverflowParser)

    def test_routing_github(self):
        """Verifies that github URLs route to the GitHub parser class."""
        parser = get_parser("https://github.com/owner/repo")
        self.assertIsInstance(parser, GitHubParser)

    def test_routing_generic(self):
        """Verifies that generic URLs route to the Generic parser class."""
        parser = get_parser("https://medium.com/some-post")
        self.assertIsInstance(parser, GenericParser)

    def test_parse_real_stackoverflow_url(self):
        """Fetches and parses a real StackOverflow URL to verify live integration via compatible wrapper."""
        url = "https://stackoverflow.com/questions/5963269/how-to-make-a-great-r-reproducible-example"
        print(f"\n\n=== SCRAPING REAL STACKOVERFLOW PAGE ===\nURL: {url}")
        
        parse_func = get_parser_for_url(url)
        parsed = parse_func(url)
        
        print(f"Total items extracted: {len(parsed)}")
        for idx, item in enumerate(parsed[:10]):  # Print up to 10 items for readability
            location = item["metadata"].get("location", "Unknown")
            print(f"--------------------------------------------------")
            print(f"Item #{idx+1} | Location: {location}")
            print(f"Text:\n{item['text']}")
        print(f"=========================================\n")
        
        # Verify that we actually retrieved parsed content from the live website
        self.assertTrue(len(parsed) > 0, "No content was extracted from StackOverflow URL")

if __name__ == '__main__':
    unittest.main()
