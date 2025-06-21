import asyncio
from urllib.parse import urldefrag, urljoin
from crawl4ai import (
    AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode,
    MemoryAdaptiveDispatcher, LLMConfig
)
import re
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel
from bs4 import BeautifulSoup
import os
from datetime import datetime, timezone
import json

# Set Gemini API key
os.environ["GEMINI_API_KEY"] = "Your-Gemini-API-Key-Here"

# Schema for structured LLM output
class ArticleData(BaseModel):
    headline: str
    summary: str
    published_date: str
    product: str
    target: str

# Main crawler function
async def crawl_html(start_urls, targets, nm, desc, max_depth=2, max_concurrent=10):
    if targets is None:
        targets = []
    elif isinstance(targets, str):
        targets = [targets]

    browser_config = BrowserConfig(headless=True, verbose=False)

    # LLM-based extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="gemini/gemini-2.0-flash",
            api_token=os.environ["GEMINI_API_KEY"]
        ),
        schema=ArticleData.model_json_schema(),
        extraction_type="schema",
        instruction="""Extract article fields from the content. Return one complete JSON."""
    )

    # First-layer crawl config (extract links)
    depth1_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        stream=False,
        wait_for=", ".join(targets),
        excluded_tags=["header", "footer", "form", "nav", ".cookie-banner", ".privacy-preference"]
    )

    # Second-layer crawl config (extract article content)
    depth2_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        stream=False,
        extraction_strategy=llm_strategy,
        excluded_tags=["header", "footer", "form", "nav", ".cookie-banner", ".privacy-preference"],
        remove_overlay_elements=True,
        scan_full_page=True,
        delay_before_return_html=5.0,
    )

    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=90.0,
        check_interval=1.0,
        max_session_permit=2
    )

    def normalize_url(url):
        return urldefrag(url)[0]

    # Crawl depth 2: article pages
    async def crawl2(article_links, depth2_config, crawler, nm, desc):
        article_results = await crawler.arun_many(
            urls=list(article_links),
            config=depth2_config,
            dispatcher=None
        )

        extracted_count = 0

        def score_content(entry: dict) -> int:
            # Score based on how complete the entry is
            score = 0
            if entry.get("published_date"): score += 3
            if entry.get("product"): score += 2
            if entry.get("target"): score += 2
            if entry.get("summary") and len(entry.get("summary")) > 30: score += 1
            if entry.get("headline") and len(entry.get("headline")) > 10: score += 1
            return score

        for result in article_results:
            norm_url = normalize_url(result.url)
            visited.add(norm_url)

            if result.success:
                if result.extracted_content:
                    extracted_count += 1
                    content = result.extracted_content
                    if isinstance(content, str):
                        content = json.loads(content)

                    if isinstance(content, list) and content:
                        content = max(content, key=score_content)

                    if not isinstance(content, dict):
                        raise ValueError("Extracted content is not a dictionary")

                    article_data = {
                        "datetime": datetime.now(timezone.utc).isoformat(),
                        "url": result.url,
                        "published_date": content.get("published_date", ""),
                        "headline": content.get("headline", ""),
                        "product": content.get("product", ""),
                        "target": content.get("target", ""),
                        "description": result.markdown,
                        "web_name": nm,
                        "web_desc": desc
                    }

                    # Save to JSONL
                    with open("extracted_articles.json", "a", encoding="utf-8") as f:
                        f.write(json.dumps(article_data, ensure_ascii=False) + "\n")
            else:
                print(f"[ERROR] Depth 2 - {result.url}: {result.error_message}")

        print(f"\n=== Summary ===")
        print(f"Successfully extracted content from {extracted_count} articles")

    visited = set()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        print(f"\n=== Depth 1: Extracting links from selectors ===")
        start_urls_normalized = [normalize_url(url) for url in start_urls]

        # Crawl home/section pages
        results = await crawler.arun_many(
            urls=start_urls_normalized,
            config=depth1_config,
            dispatcher=dispatcher
        )

        article_links = set()

        for result in results:
            norm_url = normalize_url(result.url)
            visited.add(norm_url)

            if result.success and result.html:
                soup = BeautifulSoup(result.html, 'html.parser')
                found = False

                # Search for article links using CSS selectors
                for target in targets:
                    target_element = soup.select(target)
                    if not target_element:
                        continue
                    for element in target_element:
                        links = element.select('a[href]')

                        for link in links:
                            href = link['href']
                            link_text = link.get_text(strip=True)

                            if not href or href.startswith('#') or href.startswith('javascript:'):
                                continue
                            if not href.startswith('http'):
                                href = urljoin(result.url, href)

                            normalized_href = normalize_url(href)

                            # Skip pagination and downloads
                            if re.search(r"(page=\d+|/page/\d+/?)", normalized_href, re.IGNORECASE):
                                continue
                            if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar)(\?|$)", normalized_href, re.IGNORECASE):
                                continue

                            if normalized_href not in visited:
                                article_links.add(normalized_href)

                        found = True

                if not found:
                    print(f"No selectors matched in {result.url}")
            else:
                print(f"[ERROR] Depth 1 - {result.url}")

        # Proceed to article crawling if applicable
        if article_links and max_depth >= 2:
            print(f"\n=== Depth 2: Extracting articles with LLM ===")
            print(f"Processing {len(article_links)} article links")
            await crawl2(article_links, depth2_config, crawler, nm, desc)
        else:
            print("No article links found or max_depth < 2")
