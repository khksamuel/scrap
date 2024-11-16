from urllib.parse import urlparse
from typing import List, Set
import re

class UrlFilter:
    def __init__(self):
        self.visited_domains: Set[str] = set()
        self.max_pages_per_domain = 2  # Adjust this number as needed
        self.domain_page_counts: dict = {}
        
    def should_crawl_url(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path
        
        # Skip unwanted URL patterns
        if any(pattern in path.lower() for pattern in [
            '/login', '/signup', '/contact', '/about',
            '/privacy', '/terms', '/cart', '/checkout'
        ]):
            return False
        
        # Skip URLs with menu= parameter followed by numbers
        if re.search(r'menu=\d+$', path):
            return False

        # Skip URLs if there is nothing right after the domain
        if not path or path == '/':
            return False
        
        # Skip URLs with too many path segments
        if len(path.split('/')) > 4:  # Adjust number as needed
            return False
        
        # Initialize counter for new domains
        if domain not in self.domain_page_counts:
            self.domain_page_counts[domain] = 0
            
        # Check if we've reached the limit for this domain
        if self.domain_page_counts[domain] >= self.max_pages_per_domain:
            return False
            
        # Increment counter and return True if we should crawl
        self.domain_page_counts[domain] += 1
        return True