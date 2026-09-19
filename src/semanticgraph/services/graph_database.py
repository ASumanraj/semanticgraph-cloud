from typing import Any

class GraphDatabase:
    def save_graph(self, graph: Any, tenant_id: str) -> bool:
        # Minimal database port/adapter simulating a Neo4j save
        # Must enforce tenant_id strictly.
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        # Simulate saving the graph
        return True
