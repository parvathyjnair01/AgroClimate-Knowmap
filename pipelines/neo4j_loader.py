import streamlit as st
import database
import logging
from py2neo import Node, Relationship

def store_triples_in_neo4j(triples: list):
    graph = database.get_neo4j_graph()
    if not graph:
        st.error("Neo4j connection failed.")
        logging.error("Neo4j graph is None. Check NEO4J_URI/USER/PASSWORD and container.")
        return 0

    tx = graph.begin()
    count = 0
    try:
        for subj, rel, obj in triples:
            node_a = Node("Entity", name=subj)
            tx.merge(node_a, "Entity", "name")
            node_b = Node("Entity", name=obj)
            tx.merge(node_b, "Entity", "name")
            rel_type = rel.upper().replace(" ", "_")
            relationship = Relationship(node_a, rel_type, node_b)
            tx.merge(relationship)
            count += 1
        try:
            tx.commit()
        except Exception as e:
            logging.error(f"Commit failed: {e}")
            st.error(f"Neo4j commit failed: {e}")
            tx.rollback()
            return 0
        st.success(f"✅ Stored {count} triples in Neo4j.")
        return count
    except Exception as e:
        logging.error(f"Error loading data to Neo4j: {e}")
        st.error(f"Error loading data to Neo4j: {e}")
        tx.rollback()
        return 0
