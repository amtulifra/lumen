import pytest

from knowledge.graph import KnowledgeGraph


@pytest.fixture
def graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    g.add_edge("paper_a", "paper_b", "CITES", strength=1.0, metadata={})
    g.add_edge("paper_b", "paper_c", "SHARES_METHOD", strength=0.9, metadata={"method_a": "LoRA"})
    g.add_edge("paper_a", "paper_c", "CONTRADICTS", strength=2.5, metadata={"delta": 2.5})
    return g


class TestKnowledgeGraphEdges:
    def test_add_edge_creates_nodes(self, graph: KnowledgeGraph):
        assert "paper_a" in graph.graph.nodes
        assert "paper_b" in graph.graph.nodes
        assert "paper_c" in graph.graph.nodes

    def test_add_edge_stores_attributes(self, graph: KnowledgeGraph):
        data = graph.graph["paper_b"]["paper_c"]
        assert data["link_type"] == "SHARES_METHOD"
        assert data["strength"] == 0.9


class TestKnowledgeGraphNeighbors:
    def test_outgoing_neighbors(self, graph: KnowledgeGraph):
        neighbors = graph.neighbors("paper_a")
        assert "paper_b" in neighbors
        assert "paper_c" in neighbors

    def test_incoming_neighbors(self, graph: KnowledgeGraph):
        neighbors = graph.neighbors("paper_b")
        assert "paper_a" in neighbors
        assert "paper_c" in neighbors

    def test_filter_by_link_type(self, graph: KnowledgeGraph):
        neighbors = graph.neighbors("paper_a", link_type="CITES")
        assert "paper_b" in neighbors
        assert "paper_c" not in neighbors

    def test_unknown_paper_returns_empty(self, graph: KnowledgeGraph):
        assert graph.neighbors("nonexistent") == []

    def test_no_duplicate_neighbors(self):
        g = KnowledgeGraph()
        g.add_edge("a", "b", "CITES", strength=1.0, metadata={})
        g.add_edge("b", "a", "CITES", strength=1.0, metadata={})
        neighbors = g.neighbors("a")
        assert neighbors.count("b") == 1


class TestKnowledgeGraphShortestPath:
    def test_finds_direct_path(self, graph: KnowledgeGraph):
        path = graph.shortest_path("paper_a", "paper_b")
        assert path == ["paper_a", "paper_b"]

    def test_finds_indirect_path(self):
        g = KnowledgeGraph()
        g.add_edge("x", "y", "CITES", strength=1.0, metadata={})
        g.add_edge("y", "z", "CITES", strength=1.0, metadata={})
        path = g.shortest_path("x", "z")
        assert "x" in path and "z" in path

    def test_returns_empty_when_no_path(self):
        g = KnowledgeGraph()
        g.add_edge("a", "b", "CITES", strength=1.0, metadata={})
        path = g.shortest_path("a", "c")
        assert path == []

    def test_same_node_returns_single_element(self, graph: KnowledgeGraph):
        path = graph.shortest_path("paper_a", "paper_a")
        assert path == ["paper_a"]


class TestKnowledgeGraphSubgraph:
    def test_subgraph_includes_root(self, graph: KnowledgeGraph):
        result = graph.subgraph("paper_a", depth=1)
        node_ids = [n["id"] for n in result["nodes"]]
        assert "paper_a" in node_ids

    def test_subgraph_depth_1_excludes_distant(self):
        g = KnowledgeGraph()
        g.add_edge("a", "b", "CITES", strength=1.0, metadata={})
        g.add_edge("b", "c", "CITES", strength=1.0, metadata={})
        g.add_edge("c", "d", "CITES", strength=1.0, metadata={})

        result = g.subgraph("a", depth=1)
        node_ids = [n["id"] for n in result["nodes"]]
        assert "d" not in node_ids

    def test_subgraph_unknown_paper_returns_empty(self, graph: KnowledgeGraph):
        result = graph.subgraph("ghost_paper", depth=2)
        assert result == {"nodes": [], "edges": []}

    def test_subgraph_edges_have_required_fields(self, graph: KnowledgeGraph):
        result = graph.subgraph("paper_a", depth=2)
        for edge in result["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "link_type" in edge


class TestKnowledgeGraphContradictions:
    def test_returns_only_contradicts_edges(self, graph: KnowledgeGraph):
        contradictions = graph.get_contradictions()
        assert len(contradictions) == 1
        assert contradictions[0]["source"] == "paper_a"
        assert contradictions[0]["target"] == "paper_c"

    def test_returns_empty_when_no_contradictions(self):
        g = KnowledgeGraph()
        g.add_edge("a", "b", "CITES", strength=1.0, metadata={})
        assert g.get_contradictions() == []
