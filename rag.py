
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_google_vertexai import ChatVertexAI
from langchain.prompts import PromptTemplate
import os
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Neo4j Connection Setup ===
# Establishes connection to the local Neo4j instance using credentials from environment variables

def setup_neo4j_connection():
    try:
        # Use environment variables for credentials
        NEO4J_URI = os.getenv("NEO4J_URI", "")
        USERNAME = os.getenv("NEO4J_USERNAME", "")
        PASSWORD = os.getenv("NEO4J_PASSWORD", "")
        
        # Connect to Neo4j graph
        graph = Neo4jGraph(
            url=NEO4J_URI,
            username=USERNAME,
            password=PASSWORD
        )
        
        # Refresh schema and handle potential errors
        graph.refresh_schema()
        logger.info("Successfully connected to Neo4j and refreshed schema")
        
        return graph
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise

# === Cypher QA Chain Setup ===
# Constructs a LangChain pipeline that:
# - Generates Cypher queries from natural language questions
# - Executes the queries on the Neo4j database
# - Converts query results into natural language answers

def create_cypher_chain(graph):
    # Prompt for Cypher generation
    cypher_generation_template = """
    Task:
    Generate Cypher query for a Neo4j graph database.

    Instructions:
    Use only the provided relationship types and properties in the schema.
    Do not use any other relationship types or properties that are not provided.

    Schema:
    {schema}

    Note:
    Do not include any explanations or apologies in your responses.
    Do not respond to any questions that might ask anything other than
    for you to construct a Cypher statement. Do not include any text except
    the generated Cypher statement. Make sure the direction of the relationship is
    correct in your queries. Make sure you alias both entities and relationships
    properly. Do not run any queries that would add to or delete from
    the database. Make sure to alias all statements that follow as with
    statement (e.g. WITH c as content, p.name as product_name).
    If you need to divide numbers, make sure to
    filter the denominator to be non-zero.

    Examples:
    # Retrieve the latest published content from each web source.
    MATCH (w:WebSource)-[:PUBLISHED]->(c:Content)
    WITH w.id AS web_source, MAX(c.published_date) AS latest_date
    RETURN web_source, latest_date

    # List all products mentioned in content published by 'THERALASE PRESS RELEASE'.
    MATCH (w:WebSource {{id: "THERALASE PRESS RELEASE"}})-[:PUBLISHED]->(c:Content)-[:HAS]->(p:Product)
    RETURN DISTINCT p.name AS product_name

    # Find targets linked to the product 'TLD-1433'.
    MATCH (p:Product {{name: "TLD-1433"}})-[:FOR]->(t:Target)
    RETURN t.name AS target_name

    # Count how many contents mention each product.
    MATCH (c:Content)-[:HAS]->(p:Product)
    RETURN p.name AS product_name, COUNT(c) AS mentions
    ORDER BY mentions DESC

    # Find all content titles that mention a specific target.
    MATCH (c:Content)-[:HAS]->(:Product)-[:FOR]->(t:Target {{name: "Ruthenium-based photosensitizer"}})
    RETURN c.title AS content_title

    String category values:
    Use existing strings and values from the schema provided. 

    The question is:
    {question}
    """

    cypher_generation_prompt = PromptTemplate(
        input_variables=["schema", "question"],
        template=cypher_generation_template
    )

    # Prompt for final answer generation
    qa_generation_template_str = """
    You are an assistant that reads the results of a Cypher query executed on a Neo4j graph database and provides a helpful, human-readable answer based on them.

    Query Results:
    {context}

    Question:
    {question}

    Guidelines:
    - Only use the provided query results to generate the answer. Do not use any external knowledge.
    - If the query results are empty (shown as: []), clearly respond that the answer is not available based on the data.
    - If results are available, generate a coherent answer using the values. Do not restate raw data — explain it as a helpful response.
    - If the question mentions dates or durations, assume the data is in days unless the format or units specify otherwise.
    - When handling names (like drug names, product names, or source names), keep punctuation intact. For example, 'Jones, Brown and Murray' is a single entity.
    - If the result contains multiple items (like a list of products or titles), present them clearly as a bullet list or comma-separated, depending on what fits best.
    - Do not say "based on the data provided" or similar boilerplate. Just give the answer naturally.
    - Never say you lack information if results are present — always use what's available.

    Helpful Answer:
    """

    qa_generation_prompt = PromptTemplate(
        input_variables=["context", "question"], 
        template=qa_generation_template_str
    )

    try:
        # Create the chain with error handling
        cypher_chain = GraphCypherQAChain.from_llm(
            top_k=10,
            graph=graph,
            verbose=True,
            validate_cypher=True,
            qa_prompt=qa_generation_prompt,
            cypher_prompt=cypher_generation_prompt,
            qa_llm=ChatVertexAI(model="gemini-2.5-flash", temperature=0),
            cypher_llm=ChatVertexAI(model="gemini-2.5-flash", temperature=0),
            allow_dangerous_requests=True
        )
        
        logger.info("Successfully created Cypher QA chain")
        return cypher_chain
        
    except Exception as e:
        logger.error(f"Failed to create Cypher chain: {e}")
        raise

# === Question Answering Function ===
# Takes a user question and runs it through the chain to get a final response
def ask_question(cypher_chain, question):
    try:
        logger.info(f"Processing question: {question}")
        response = cypher_chain.invoke(question)
        return response.get("result")
        
    except Exception as e:
        logger.error(f"Error processing question '{question}': {e}")
        return f"Sorry, I encountered an error while processing your question: {e}"

# === Main Execution Pipeline ===
# Orchestrates the process:
# 1. Connects to Neo4j
# 2. Displays schema for debugging
# 3. Builds the Cypher QA chain
def rag(question):
    try:
        # Setup Neo4j connection
        graph = setup_neo4j_connection()
        
        # Print schema for debugging
        print("Neo4j Schema:")
        print(graph.schema)
        print("\n" + "="*50 + "\n")
        
        # Create the QA chain
        cypher_chain = create_cypher_chain(graph)
        
        
       
        result = ask_question(cypher_chain, question)
        print(f"Answer: {result}")

            
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"Application failed to run: {e}")


