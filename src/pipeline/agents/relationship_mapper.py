import os
from typing import List, Literal
from pydantic import BaseModel, Field
import instructor
from google import genai

from src.semanticgraph.worker import celery_app

# Define strict Pydantic models for the Ontology
class Node(BaseModel):
    id: str = Field(description="Unique identifier for the node")
    label: Literal['Person', 'Company', 'Concept'] = Field(description="Type of the node")
    properties: dict = Field(default_factory=dict, description="Additional properties of the node")

class Edge(BaseModel):
    source: str = Field(description="ID of the source node")
    target: str = Field(description="ID of the target node")
    relation: str = Field(description="Relationship type between source and target")

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(default_factory=list, description="List of nodes in the graph")
    edges: List[Edge] = Field(default_factory=list, description="List of edges in the graph")

# Initialize Gemini client
_client = None
client = None

def get_instructor_client():
    global _client, client
    if client is None:
        api_key = os.getenv("GEMINI_API_KEY", "mock_key")
        _client = genai.Client(api_key=api_key)
        client = instructor.from_gemini(_client)
    return client

def extract_knowledge_graph(text: str, tenant_id: str) -> KnowledgeGraph:
    """
    Synchronous extraction function to get KnowledgeGraph from text.
    """
    if not tenant_id:
        raise ValueError("tenant_id is required")

    instructor_client = get_instructor_client()
    
    SYSTEM_PROMPT = """You are a highly capable AI agent acting as an Ontology Extraction Engine.
Your goal is to parse the input text and strictly extract information according to our predefined Ontology.
Extract all distinct entities as Nodes (types: Person, Company, Concept) and relationships as Edges.
Ensure no hallucinations and focus on factual extraction from the text.
"""

    graph: KnowledgeGraph = instructor_client.chat.completions.create(
        model="gemini-2.5-flash",
        response_model=KnowledgeGraph,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Text:\n{text}"}
        ],
    )
    
    return graph

@celery_app.task
def extract_graph_task(text: str, tenant_id: str) -> dict:
    """
    Celery task to extract a KnowledgeGraph from text using the Instructor-wrapped Gemini client.
    Returns the graph as a dict.
    """
    graph = extract_knowledge_graph(text, tenant_id)
    return graph.model_dump()
