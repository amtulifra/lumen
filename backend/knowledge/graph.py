import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.store import get_all_links


class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    async def build_from_db(self, db: AsyncSession = None) -> None:
        if db is None:
            from database import SessionLocal
            async with SessionLocal() as session:
                await self.load(session)
        else:
            await self.load(db)

    async def load(self, db: AsyncSession) -> None:
        self.graph.clear()
        links = await get_all_links(db)
        for link in links:
            self.graph.add_edge(
                link["source_id"],
                link["target_id"],
                link_type=link["link_type"],
                strength=link["strength"],
                metadata=link["metadata"],
            )

    def add_edge(self, source: str, target: str, link_type: str, strength: float, metadata: dict) -> None:
        self.graph.add_edge(source, target, link_type=link_type, strength=strength, metadata=metadata)

    def neighbors(self, paper_id: str, link_type: str | None = None) -> list[str]:
        if paper_id not in self.graph:
            return []
        edges = list(self.graph.edges(paper_id, data=True))
        edges += [(t, s, d) for s, t, d in self.graph.in_edges(paper_id, data=True)]
        if link_type:
            edges = [(s, t, d) for s, t, d in edges if d.get("link_type") == link_type]
        seen = set()
        result = []
        for source, target, _ in edges:
            neighbor = target if source == paper_id else source
            if neighbor not in seen:
                seen.add(neighbor)
                result.append(neighbor)
        return result

    def shortest_path(self, source: str, target: str) -> list[str]:
        try:
            return nx.shortest_path(self.graph.to_undirected(), source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def subgraph(self, paper_id: str, depth: int = 2) -> dict:
        if paper_id not in self.graph:
            return {"nodes": [], "edges": []}

        undirected = self.graph.to_undirected()
        reachable = nx.single_source_shortest_path_length(undirected, paper_id, cutoff=depth)
        nodes = list(reachable.keys())
        sub = self.graph.subgraph(nodes)

        node_list = [{"id": n} for n in sub.nodes()]
        edge_list = [
            {
                "source": s,
                "target": t,
                "link_type": d.get("link_type"),
                "strength": d.get("strength"),
                "metadata": d.get("metadata"),
            }
            for s, t, d in sub.edges(data=True)
        ]
        return {"nodes": node_list, "edges": edge_list}

    def get_contradictions(self) -> list[dict]:
        return [
            {
                "source": s,
                "target": t,
                "metadata": d.get("metadata"),
            }
            for s, t, d in self.graph.edges(data=True)
            if d.get("link_type") == "CONTRADICTS"
        ]


knowledge_graph = KnowledgeGraph()
