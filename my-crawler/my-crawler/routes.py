from crawlee.playwright_crawler import PlaywrightCrawlingContext
from crawlee.router import Router
from .smart_extractor import SmartExtractor
from .url_filter import UrlFilter
from .smart_extractor import ContentType
import logging
router = Router[PlaywrightCrawlingContext]()

@router.default_handler
async def request_handler(context: PlaywrightCrawlingContext) -> None:
    logger = logging.getLogger(__name__)
    url = context.request.url
    content_type = detect_content_type(url, await context.page.content())
    
    context.log.info(f'Processing {url} as {content_type}')
    title = await context.page.query_selector('title')
    data_dict = {
        'url': context.request.url,
        'title': await title.inner_text() if title else None
    }

    smart_extractor = SmartExtractor()
    smart_extractor.set_content_type(content_type)

    extracted_data: dict = await smart_extractor.extract_content(
        html=await context.page.content(),
        url=context.request.url
    )

    if (not UrlFilter().should_crawl_url(context.request.url) or extracted_data == {}):
        return

    if extracted_data.get('error'):
        logger.debug(f"Error extracting data from {context.request.url}: {extracted_data['error']}")
        return

    data_dict['extracted_data'] = extracted_data

    await context.push_data(data_dict)

    await context.enqueue_links()

def detect_content_type(url: str, html: str) -> ContentType:
    """Detect content type based on URL patterns and key phrases in HTML."""
    url = url.lower()
    html = html.lower()
    
    # URL-based patterns
    url_patterns = {
        ContentType.JOB: [
            '/job', '/career', '/position', '/vacancy', 
            'jobs.', 'careers.', 'seek.com', 'indeed.com'
        ],
        ContentType.RENTAL: [
            '/rent', '/property', '/apartment', 
            'realestate.', 'domain.com', 'zillow.com'
        ]
    }
    
    # HTML-based patterns (check meta tags, headings, etc.)
    html_patterns = {
        ContentType.JOB: [
            'job description', 'requirements:', 'qualifications:',
            'salary:', 'experience required', 'apply now'
        ],
        ContentType.RENTAL: [
            'bedroom', 'bathroom', 'square feet', 'sq ft',
            'lease', 'rent per', 'available from'
        ]
    }
    
    # Score each content type
    scores = {content_type: 0 for content_type in ContentType}
    
    # Check URL patterns (weighted more heavily)
    for content_type, patterns in url_patterns.items():
        for pattern in patterns:
            if pattern in url:
                scores[content_type] += 2  # URL matches are worth more
                
    # Check HTML patterns
    for content_type, patterns in html_patterns.items():
        for pattern in patterns:
            if pattern in html:
                scores[content_type] += 1
                
    # Get the content type with highest score
    max_score = max(scores.values())
    if max_score > 0:
        return max(scores.items(), key=lambda x: x[1])[0]
        
    return ContentType.GENERIC  # Default if no strong matches