from src.pipeline.agents.relationship_mapper import extract_graph_task, KnowledgeGraph, Node, Edge

def test():
    print("Imports successful!")
    print(f"Node schema: {Node.model_json_schema()}")
    print(f"Edge schema: {Edge.model_json_schema()}")
    print(f"KnowledgeGraph schema: {KnowledgeGraph.model_json_schema()}")
    print(f"Task function: {extract_graph_task}")

if __name__ == '__main__':
    test()
