# LLM-WebScraper-Graph-Pipeline

## Overview

**LLMScraper_Graph_pipeline** is an end-to-end information retrieval and question-answering pipeline that scrapes content from the web, processes it into a knowledge graph using Neo4j, and performs Retrieval-Augmented Generation (RAG) using LLMs such as OpenAI or Gemini. It is built with Python and uses a modular architecture that combines web crawling, semantic embedding, and knowledge graph querying for intelligent question answering.

## Core Components

### Main Scripts

| File                  | Description |
|-----------------------|-------------|
| `crawl4_direct.py`    | Directly scrapes website content (e.g., news pages) using browser automation or HTTP requests. Extracts and structures article content for downstream use. |
| `crawl4_rss.py`       | Scrapes news content via RSS feeds. Converts structured feed entries into article objects. Useful for automated, scheduled ingestion. |
| `extracted_articles.json` | Sample or output data containing extracted articles from the crawlers. Used as input for graph or RAG components. |
| `pipeline.py`         | Orchestrates the full pipeline: ingestion → extraction → embedding → graph creation → RAG query. Acts as the main controller. |
| `json_to_graph.py`    | Converts structured article data (in JSON) into a Neo4j knowledge graph by identifying entities, relationships, and timestamps. |
| `rag.py`              | Implements Retrieval-Augmented Generation (RAG) using LangChain and an LLM. It fetches top-k relevant chunks based on a user query and formulates an answer. |

## Pipeline Flow

### 1. Crawl Content

- `crawl4_direct.py` and `crawl4_rss.py` scrape news articles from pharma-related web sources.
- Extracted outputs are structured and saved as JSON files.

### 2. JSON to Knowledge Graph

- `json_to_graph.py` loads the JSON article data.
- Entities and relationships (e.g., companies, drugs, clinical studies) are extracted.
- The structured data is ingested into a Neo4j graph database.

### 3. Embedding and RAG

- Article text chunks are embedded using Sentence Transformers (e.g., `all-MiniLM-L6-v2`).
- Embeddings are stored in a vector database (or in-memory store) for semantic similarity search.
- `rag.py` retrieves top-k relevant passages based on the user query.
- LangChain passes the retrieved context to an LLM (e.g., OpenAI, Gemini) which generates a contextualized answer.

### 4. Full Orchestration

- `pipeline.py` ties all components together.
- Can be run as a CLI tool or scheduled job.
- Runs the complete flow: web scraping → knowledge graph update → question answering.
