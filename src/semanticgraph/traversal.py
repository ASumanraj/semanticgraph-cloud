def run_leiden_community_detection(graph_client):
    pass


def run_semantic_pagerank(graph_client, entry_nodes: list, query: str):
    pass


class SearchEngine:
    def __init__(self, graph_client):
        self.graph_client = graph_client

    def global_search(self, query: str):
        return run_leiden_community_detection(self.graph_client)

    def local_search(self, query: str, entry_nodes: list):
        return run_semantic_pagerank(self.graph_client, entry_nodes, query)
