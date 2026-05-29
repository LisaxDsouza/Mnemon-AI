from .parser_factory import get_parser
from .base_parser import BaseParser

def get_parser_for_url(url: str):
    """Compatible wrapper returning a callable function: parser_callable(url) -> List[Dict]"""
    parser_instance = get_parser(url)
    
    def parse_wrapper(target_url: str):
        html = parser_instance.fetch(target_url)
        return parser_instance.parse(target_url, html)
        
    return parse_wrapper
