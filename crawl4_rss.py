
from urllib.parse import urldefrag, urljoin
from crawl4ai import (
    AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode,
    MemoryAdaptiveDispatcher, LLMConfig
)
import re
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel
from bs4 import BeautifulSoup
import feedparser
import os
import json
from crawl4ai import RateLimiter



os.environ["GEMINI_API_KEY"] = "Your-Gemini-API-Key-Here"


class ArticleData(BaseModel):
    headline: str
    summary: str
    published_date: str
    product: str
    target: str



async def crawl_rss(rss_urls,max_concurrent=10):
    browser_config = BrowserConfig(headless=True, verbose=False)


    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=90.0,  
        check_interval=1.0,            
        max_session_permit=10,          
        rate_limiter=RateLimiter(       
            base_delay=(8.0, 10.0), 
            max_delay=30.0,
            max_retries=2
        )
    )
    # LLM strategy for depth 2 (article extraction)
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="gemini/gemini-2.0-flash",
            api_token="Your-Gemini-API-Key-Here",
        ),
        schema=ArticleData.model_json_schema(),
        extraction_type="schema",
        instruction=""" Extract 'headline' and a short 'summary' from the content.
        Get the 'published_date' from the content such that it had date,month and year. Check throughly near the headline.

        **IMPORTANT**: Answer only from the provided content, DO NOT make up any information or try to come up with an example.

        List of products and targets that should be recognized:
            'BCG Tice': 'Bacterial immunopotentiator',
            'Adstiladrin': 'Non-replicating AAV with IFN alpha2b gene',
            'Vicineum': 'Anti-ECAM exotoxin A fusion protein',
            'Keytruda': 'Anti-PD-1 mAb',
            'Pembrolizumab': 'Anti-PD-1 mAb',
            'UGN-102': 'D- synthesis inhibitor',
            'CG0070 + Keytruda': 'Oncolytic adenovirus immunotherapy + Anti-PD-1 mAb',
            'VesAnktiva + BCG': 'IL-15 superagonist fusion protein',
            'EG-70': 'IL-12 non-viral gene therapy',
            'Erdafitinib': 'FGFR inhibitor',
            'TAR-200': 'Gemcitabine-releasing intravesical system',
            'TLD-1433': 'Ruthenium-based photosensitizer',
            'Enfortumab Vedotin': 'Nectin-4-directed',
            'TARA-002': 'TLR-4 agonists'
        if any of these products or targets are mentioned in the article, extract them.
        If the article does not mention any of these products or targets, return an empty string for those fields.
        
        Return only ONE complete JSON object with all fields filled.
        """
    )


    
    # Config for depth 2 (LLM extraction from articles)
    
    depth2_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        stream=False,
        extraction_strategy=llm_strategy,
        excluded_tags=['form', 'footer', 'nav'],
    )


    def normalize_url(url):
        return urldefrag(url)[0]
    
    async def crawl2(article_links, depth2_config, crawler):
        article_results = await crawler.arun_many(
            urls=list(article_links)[5],
            config=depth2_config,
            dispatcher=dispatcher
        )

        print(f"\n\n=== Here is the result of all the links ===")
        # print(article_results)


        extracted_count = 0
        for result in article_results:
            norm_url = normalize_url(result.url)
            visited.add(norm_url)

            print(f"\n[DEBUG] Raw result: {result.url}")
            print(f"[DEBUG] Success: {result.success}")
            print(f"[DEBUG] Extracted Content: {result.extracted_content}")
            # print(f"[DEBUG] Error Message: {result.error_message}")

            if result.success:
                print(f"[OK] Depth 2 - {result.url}")
                if result.extracted_content:
                    # Filter out empty or error extractions
                    valid_extractions = []
                    c=0
                    for item in json.loads(result.extracted_content):

                        if isinstance(item, dict):
                            # Skip error items
                            if item.get('headline', '').strip() or item.get('summary', '').strip():
                                valid_extractions.append(item)
                            if item.get('error', 'false'):
                                print(f"[WARNING] Skipping error extraction: {item.get('content', 'Unknown error')}")
                                fl=1
                            # Check if extraction has meaningful content
                            
                        fl=0
                    
                    if valid_extractions:
                        # Use the first valid extraction
                        extracted_content = valid_extractions[0]
                        extracted_count += 1
                        
                        # Save results to file
                        with open("extracted_articles.txt", "w", encoding="utf-8") as f:
                            f.write(f"URL: {result.url}\n")
                            f.write("Extracted:\n")
                            f.write(f"{extracted_content}\n")
                            f.write("-" * 80 + "\n\n")
                            
                    else:
                        print(f"No valid content extracted from {result.url}")
                else:
                    print(f"No content extracted from {result.url}")
            else:
                print(f"[ERROR] Depth 2 - {result.url}: {result.error_message}")

        print(f"\n=== Summary ===")
        print(f"Successfully extracted content from {extracted_count} articles")


    visited = set()
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
    
        feed = feedparser.parse(rss_urls[0]) 
        l=[]
        for entry in feed.entries:
            link = entry.get("link", "No Link")   
            l.append(link)

        await crawl2(l, depth2_config, crawler)         
     
        
