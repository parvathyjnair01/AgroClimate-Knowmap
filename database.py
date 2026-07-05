from py2neo import Graph, Node, Relationship
from decouple import config
import streamlit as st
import logging

# Load Neo4j credentials from .env file
# Default to Docker-mapped Bolt port 7688 so it connects out-of-the-box
NEO4J_URI = config("NEO4J_URI", default="bolt://127.0.0.1:7688")
NEO4J_USER = config("NEO4J_USER", default="neo4j")
NEO4J_PASSWORD = config("NEO4J_PASSWORD")

@st.cache_resource
def get_neo4j_graph():
    """
    Establishes and caches the connection to the Neo4j database.
    Returns the Graph object or None if connection fails.
    """
    try:
        # Explicitly disable encryption to avoid TLS mismatches
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), secure=False)
        # Simple ping to validate connectivity and auth
        ok = graph.run("RETURN 1 AS x").evaluate()
        if ok != 1:
            logging.error("Neo4j ping returned unexpected result")
            return None
        logging.info("✅ Neo4j connection successful.")
        return graph
    except Exception as e:
        # Surface detailed error in Streamlit for easier debugging
        msg = f"Failed to connect to Neo4j at {NEO4J_URI} as {NEO4J_USER}: {e}"
        logging.error(msg)
        try:
            st.error(msg)
        except Exception:
            pass
        return None

def clear_database():
    """
    Deletes all nodes and relationships in the database.
    """
    try:
        graph = get_neo4j_graph()
        if graph:
            graph.run("MATCH (n) DETACH DELETE n")
            logging.info("🛑 Neo4j database cleared.")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to clear database: {e}")
        return False

def get_subgraph_by_names(node_names: list) -> list:
    """
    [NEW FUNCTION]
    Fetches all triples (subject, relation, object) where
    either the subject or object name is in the provided list.
    """
    graph = get_neo4j_graph()
    if not graph or not node_names:
        return []

    # Use a Cypher query with UNWIND to pass the list as a parameter
    # This query finds all nodes with the given names and their direct (1-hop) relationships
    query = """
    UNWIND $names AS nodeName
    MATCH (n:Entity {name: nodeName})
    OPTIONAL MATCH (n)-[r]-(m:Entity)
    RETURN n.name AS source, type(r) AS relation, m.name AS target
    """
    
    try:
        results = graph.run(query, names=node_names)
        triples = []
        for record in results:
            if record["source"] and record["relation"] and record["target"]:
                triples.append((record["source"], record["relation"], record["target"]))
        return list(set(triples)) # Return unique triples
    except Exception as e:
        logging.error(f"Failed to fetch subgraph: {e}")
        st.error(f"Error querying graph: {e}")
        return []