from typing import Dict, Any
from bs4 import BeautifulSoup
import trafilatura
from newspaper import Article
from readability.readability import Document
import spacy
import yake
from price_parser import Price
import re
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

class ContentType(Enum):
    JOB = "job"
    RENTAL = "rental"
    GENERIC = "generic"

@dataclass
class ExtractionProfile:
    content_indicators: List[str]
    price_patterns: List[str]
    date_patterns: List[str]
    key_attributes: List[str]
    blacklist_phrases: List[str]

EXTRACTION_PROFILES: Dict[ContentType, ExtractionProfile] = {
    ContentType.JOB: ExtractionProfile(
        content_indicators=[
            "full time",
            "contract/temp",
            "per hour",
            "salary",
            "graduate program",
            "position"
        ],
        price_patterns=[
            r"\$\d+k?-\d+k?",
            r"\$\d+(\.\d{2})?\s*(per hour|ph|/h)",
            r"salary range",
            r"OTE"
        ],
        date_patterns=[
            r"listed\s+\d+\s+days?\s+ago",
            r"posted\s+\d+\s+days?\s+ago",
            r"expiring soon"
        ],
        key_attributes=[
            "job type",
            "location",
            "company",
            "requirements",
            "benefits"
        ],
        blacklist_phrases=[
            "No matching search results",
            "Try adjusting the filters",
            "Sign in",
            "Menu"
        ]
    ),
    
    ContentType.RENTAL: ExtractionProfile(
        content_indicators=[
            "bedroom",
            "bathroom",
            "parking",
            "rent",
            "lease",
            "furnished"
        ],
        price_patterns=[
            r"\$\d+(\.\d{2})?\s*(pw|per week)",
            r"\$\d+(\.\d{2})?\s*(pcm|per month)",
            r"bond"
        ],
        date_patterns=[
            r"available from",
            r"inspection",
            r"lease term"
        ],
        key_attributes=[
            "property type",
            "bedrooms",
            "bathrooms",
            "parking",
            "pets allowed"
        ],
        blacklist_phrases=[
            "No properties found",
            "Sign in",
            "Menu"
        ]
    ),
    ContentType.GENERIC: ExtractionProfile(
        content_indicators=[
            "article",
            "content",
            "text",
            "description"
        ],
        price_patterns=[
            r"\$\d+(?:\.\d{2})?",
            r"A\s*\d+(?:\.\d{2})?",
            r"AUD\s*\d+(?:\.\d{2})?"
        ],
        date_patterns=[
            r"\d{4}-\d{2}-\d{2}",
            r"\d{2}/\d{2}/\d{4}"
        ],
        key_attributes=[
            "title",
            "author",
            "category"
        ],
        blacklist_phrases=[
            "404",
            "Page not found",
            "Access denied"
        ]
    )
}

class ProfileMatcher:
    def __init__(self, profile: Optional[ExtractionProfile]):
        self.profile = profile

    def match(self, data: Dict[str, Any], strictness: int = 1) -> bool:
        """Match and validate content against the current profile."""
        if not data or not isinstance(data, dict):
            return False
            
        # If no profile is set, consider it a match
        if self.profile is None:
            return True

        main_content = data.get('main_content', '').lower()
        
        # Check for blacklisted phrases
        if any(phrase.lower() in main_content for phrase in self.profile.blacklist_phrases):
            return False
            
        # Check for required content indicators
        has_indicators = any(
            indicator.lower() in main_content 
            for indicator in self.profile.content_indicators
        )
        if not has_indicators:
            return False
            
        # Extract prices matching profile patterns
        prices = []
        for pattern in self.profile.price_patterns:
            matches = re.finditer(pattern, main_content)
            for match in matches:
                price_text = match.group()
                # Clean up price text (remove extra spaces, normalize format)
                price_text = re.sub(r'\s+', ' ', price_text).strip()
                prices.append(price_text)
        
        # Extract dates matching profile patterns
        dates = []
        for pattern in self.profile.date_patterns:
            matches = re.finditer(pattern, main_content)
            for match in matches:
                date_text = match.group()
                dates.append(date_text)
        
        # Extract key attributes
        attributes = {}
        for attr in self.profile.key_attributes:
            # Look for patterns like "job type: full time" or "location: Adelaide"
            pattern = rf"{attr}\s*:?\s*([^.\n]+)"
            match = re.search(pattern, main_content, re.IGNORECASE)
            if match:
                attributes[attr] = match.group(1).strip()
        
        # check if at least one of the key attributes is present
        if len(attributes) < strictness:
            return False

        return True

class SmartExtractor:
    def __init__(self, content_type: ContentType = ContentType.GENERIC):
        self.content_type = content_type
        self.profile = EXTRACTION_PROFILES.get(content_type)
        # Load spaCy model - use 'python -m spacy download en_core_web_sm' first
        self.nlp = spacy.load('en_core_web_sm')
        # Initialize keyword extractor
        self.kw_extractor = yake.KeywordExtractor(
            lan="en", 
            n=2,  # ngram size
            dedupLim=0.3,
            top=10,
            features=None
        )
        
    def set_content_type(self, content_type: ContentType):
        self.content_type = content_type
        self.profile = EXTRACTION_PROFILES.get(content_type)
    
    async def extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """Extract content from HTML with structured data priority"""
        try:
            # First try to get structured data
            structured_data = await self.extract_structured_data(html)
            if structured_data:
                # Map structured data to our expected format
                mapped_data = self.map_structured_data(structured_data)
                if mapped_data:  # If we successfully mapped the data
                    return mapped_data

            # Fall back to regular extraction if no structured data
            return await self.extract_unstructured_content(html, url)
            
        except Exception as e:
            logger.error(f"Error in extraction: {str(e)}")
            return {}

    async def extract_structured_data(self, html: str) -> Optional[dict]:
        """Extract structured data (JSON-LD, microdata) from the page"""
        try:
            # Look for JSON-LD
            soup = BeautifulSoup(html, 'html.parser')
            json_ld = soup.find('script', {'type': 'application/ld+json'})
            
            if json_ld:
                return json.loads(json_ld.string)

            # Optionally look for other structured data formats
            # microdata, RDFa, etc.
            
            return None
        except Exception as e:
            logger.debug(f"Failed to extract structured data: {str(e)}")
            return None

    def map_structured_data(self, structured_data: dict) -> Optional[dict]:
        """Map structured data to our expected format based on content type"""
        if not structured_data:
            return None

        try:
            # Handle different schema types
            schema_type = structured_data.get('@type', '').lower()
            
            if self.content_type == ContentType.JOB:
                if schema_type in ['jobposting', 'job']:
                    return {
                        'title': structured_data.get('title'),
                        'description': structured_data.get('description'),
                        'salary': structured_data.get('baseSalary', {}).get('value'),
                        'company': structured_data.get('hiringOrganization', {}).get('name'),
                        'location': structured_data.get('jobLocation', {}).get('address', {}).get('addressLocality'),
                        'date_posted': structured_data.get('datePosted'),
                        'employment_type': structured_data.get('employmentType'),
                        'structured': True  # Flag to indicate this came from structured data
                    }
            
            elif self.content_type == ContentType.RENTAL:
                if schema_type in ['apartment', 'house', 'rental']:
                    return {
                        'title': structured_data.get('name'),
                        'description': structured_data.get('description'),
                        'price': structured_data.get('price'),
                        'location': structured_data.get('address', {}).get('addressLocality'),
                        'structured': True
                    }

            # Add more content types as needed
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to map structured data: {str(e)}")
            return None

    async def extract_unstructured_content(self, html: str, url: str) -> Dict[str, Any]:
        """Fall back to regular extraction methods"""
        try:
            # Use multiple extraction methods and combine results
            extracted_data = {}
            
            # 1. Basic HTML parsing with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            extracted_data['title'] = self._extract_title(soup, html)
            
            # 2. Use trafilatura for main content extraction
            main_text = trafilatura.extract(html, include_links=True, include_images=True)
            extracted_data['main_content'] = main_text
            
            # 3. Use newspaper3k for article parsing
            article_data = self._extract_article_data(url, html)
            extracted_data.update(article_data)
            
            # 4. profile specific extraction
            if not ProfileMatcher(self.profile).match(extracted_data):
                return {}
            
            # 5. Extract prices
            extracted_data['prices'] = self._extract_prices(html)
            
            # 6. Extract dates
            extracted_data['dates'] = self._extract_dates(html)
            
            # 7. Extract key phrases and entities
            if main_text:
                extracted_data.update(self._extract_nlp_data(main_text))
            
            # 8. Clean and validate the data
            cleaned_data = self._clean_extracted_data(extracted_data)
            
            return cleaned_data
            
        except Exception as e:
            logger.error(f"Error in extraction: {str(e)}")
            return {"error": str(e)}

    def _extract_title(self, soup: BeautifulSoup, html: str) -> str:
        """Extract title using multiple methods."""
        # Try multiple sources for title
        title_candidates = [
            soup.find('meta', property='og:title'),
            soup.find('meta', property='twitter:title'),
            soup.find('h1'),
            soup.find('title')
        ]
        
        for candidate in title_candidates:
            if candidate:
                if hasattr(candidate, 'content'):
                    return candidate['content']
                else:
                    return candidate.text.strip()
                    
        # Fallback to readability
        doc = Document(html)
        return doc.title()

    def _extract_article_data(self, url: str, html: str) -> Dict[str, Any]:
        """Extract article data using newspaper3k."""
        try:
            article = Article(url)
            article.download(input_html=html)
            article.parse()
            article.nlp()
            
            return {
                'authors': article.authors,
                'publish_date': article.publish_date,
                'summary': article.summary,
                'keywords': article.keywords
            }
        except:
            return {}

    def _extract_prices(self, html: str) -> list:
        """Extract prices from HTML content."""
        prices = []
        # Find price patterns
        price_patterns = [
            r'\$\d+(?:\.\d{2})?',
            r'USD\s*\d+(?:\.\d{2})?',
            r'€\d+(?:\.\d{2})?',
            r'£\d+(?:\.\d{2})?'
        ]
        
        for pattern in price_patterns:
            matches = re.finditer(pattern, html)
            for match in matches:
                price_str = match.group()
                parsed_price = Price.fromstring(price_str)
                if parsed_price.amount is not None:
                    prices.append({
                        'amount': float(parsed_price.amount),
                        'currency': parsed_price.currency
                    })
                    
        return prices

    def _extract_dates(self, html: str) -> list:
        """Extract dates from HTML content."""
        dates = []
        # Common date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
        ]
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, html)
            for match in matches:
                try:
                    # Convert to standard format
                    date_str = match.group()
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                    dates.append(parsed_date.isoformat())
                except:
                    continue
                    
        return dates

    def _extract_nlp_data(self, text: str) -> Dict[str, Any]:
        """Extract named entities and key phrases using spaCy and YAKE."""
        # Process text with spaCy
        doc = self.nlp(text)
        
        # Extract named entities
        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            entities[ent.label_].append(ent.text)
            
        # Extract keywords using YAKE
        keywords = self.kw_extractor.extract_keywords(text)
        
        return {
            'named_entities': entities,
            'key_phrases': [kw[0] for kw in keywords]
        }

    def _clean_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate extracted data."""
        cleaned = {}
        
        for key, value in data.items():
            # Remove None values
            if value is None:
                continue
                
            # Clean strings
            if isinstance(value, str):
                cleaned_value = value.strip()
                if cleaned_value:
                    cleaned[key] = cleaned_value
                    
            # Clean lists
            elif isinstance(value, list):
                cleaned_value = [v for v in value if v is not None and str(v).strip()]
                if cleaned_value:
                    cleaned[key] = cleaned_value
                    
            # Clean dictionaries
            elif isinstance(value, dict):
                cleaned_value = self._clean_extracted_data(value)
                if cleaned_value:
                    cleaned[key] = cleaned_value
                    
            else:
                cleaned[key] = value
                
        return cleaned