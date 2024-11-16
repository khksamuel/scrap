from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
from .routes import router
from .storage_utils import read_storage_data
from .smart_extractor import SmartExtractor
from typing import List
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.tag import pos_tag
from googlesearch import search
import re

def search_with_nlp_query(query: str, 
                          num_results: int = 10, 
                          blacklisted_domains: List[str] = [
                            'youtube.com', 
                            'facebook.com',
                            'twitter.com'
                        ]
) -> List[str]:
    """
    Extract keywords from natural language query and perform internet search.
    
    Args:
        query: Natural language query string
        num_results: Number of search results to return, faster if less
    
    Returns:
        List of URLs
    """
    # Tokenize and remove stopwords
    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(query.lower())
    filtered_tokens = [w for w in word_tokens if w not in stop_words and w.isalnum()]

    # Extract nouns and important words using POS tagging
    tagged = pos_tag(filtered_tokens)
    keywords = [
        word for word, tag in tagged 
        if tag.startswith(('NN', 'JJ', 'VB'))  # Nouns, adjectives, verbs
    ]

    # Construct search query
    search_query = ' '.join(keywords)
    
    try:
        # Perform Google search
        urls = list(search(
            search_query,
            num_results=num_results
        ))
        
        # Filter out unwanted domains (optional)
        filtered_urls = [
            url for url in urls
            if not any(domain in url for domain in blacklisted_domains)
        ]
        
        return filtered_urls

    except Exception as e:
        print(f"Search error: {e}")
        return []


async def main() -> None:
    """The crawler entry point."""
    crawler = PlaywrightCrawler(
        request_handler=router,
        max_requests_per_crawl=50,
    )

    urls = search_with_nlp_query("jobs for Computer Science graduates in Adelaide", 50)
    # print(urls)

    await crawler.run(
        urls
    )

    # storage_data = read_storage_data()

    # for item in storage_data:
    #     print(f"{item['url']} - {item['title']}")
