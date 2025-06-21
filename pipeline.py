
import snowflake.connector
import asyncio
from crawl4rss import crawl_rss
from crawl4 import crawl_html
import json
from neo_json import build_graph
from neo4j import GraphDatabase
from rag import rag


# === Snowflake Connection Setup ===
def snowflakeConnectionIntellia():
    """
    Establish a connection to the Snowflake database.
    Returns the connection context and cursor object.
    """
    ctx = snowflake.connector.connect(
        user='yourusername',
        password='yourpassword',
        account='youraccount',
        database='yourdatabase',
        role='yourrole',
        warehouse='yourwarehouse'
    )
    cs = ctx.cursor()
    return ctx, cs



db, cur = snowflakeConnectionIntellia()

# Query to retrieve web source details (RSS/HTML) with required metadata
query = """
SELECT 
    s.web_src_id,
    s.web_url,
    s.src_typ,
    s.selector,
    t.web_src_nm,
    t.web_src_desc 
FROM intellia_db.intellia_cnf_zn.web_src_lib t 
INNER JOIN intellia_db.intellia_lnd_zn.crawl_src s 
    ON s.web_src_id = t.web_src_id 
WHERE s.web_src_id IN (54, 53)
"""


cur.execute(query)
rows = cur.fetchall()

# === Web Crawling ===
# Loop through each source and run appropriate crawling method
for r in rows:
    if r[2] == "RSS":
        
        asyncio.run(crawl_rss([r[1]]))
    elif r[2] == "HTML":

        print(r[1])  
        asyncio.run(crawl_html(
            [r[1]],
            r[3],  # selector
            r[4],  # web source name
            r[5],  # web source description
            max_concurrent=2,
        ))


# Read crawled articles from local JSON file
with open("extracted_articles.json", "r", encoding="utf-8") as f:
    articles = json.load(f)


# Connect to Neo4j database (update auth info as needed)
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("yourusername", "yourpassword"))

# Load crawled data into the graph using the `build_graph` function
with driver.session(database="neo4j") as session:
    session.execute_write(build_graph, articles)


# Accept natural language question input from user
q = input("Ask question: ")

# Run retrieval-augmented generation to get the answer from the graph
rag(q)

driver.close()
