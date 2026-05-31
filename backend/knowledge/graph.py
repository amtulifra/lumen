import networkx as nx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeGraph:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()

    # Backwards-compatible in-memory API (used by unit tests)
    def add_edge(self, source: str, target: str, link_type: str, strength: float, metadata: dict) -> None:
        self.graph.add_edge(source, target, link_type=link_type, strength=strength, metadata=metadata)

    def remove_node(self, paper_id: str) -> None:
        if paper_id in self.graph:
            self.graph.remove_node(paper_id)

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
        return {
            "nodes": [{"id": n} for n in sub.nodes()],
            "edges": [
                {
                    "source": s,
                    "target": t,
                    "link_type": d.get("link_type"),
                    "strength": d.get("strength"),
                    "metadata": d.get("metadata"),
                }
                for s, t, d in sub.edges(data=True)
            ],
        }

    def get_contradictions(self) -> list[dict]:
        return [
            {"source": s, "target": t, "metadata": d.get("metadata")}
            for s, t, d in self.graph.edges(data=True)
            if d.get("link_type") == "CONTRADICTS"
        ]

    # DB-first tenant-scoped API for production routes
    async def neighbors_db(self, paper_id: str, db: AsyncSession, link_type: str | None = None) -> list[str]:
        query = (
            "SELECT DISTINCT CASE WHEN source_id = :id THEN target_id ELSE source_id END AS neighbor_id "
            "FROM paper_links "
            "WHERE workspace_id = current_workspace_id() "
            "AND (source_id = :id OR target_id = :id) "
        )
        params: dict[str, object] = {"id": paper_id}
        if link_type:
            query += "AND link_type = :link_type "
            params["link_type"] = link_type

        rows = await db.execute(text(query), params)
        return [r.neighbor_id for r in rows.all()]

    async def subgraph_db(self, paper_id: str, depth: int, db: AsyncSession) -> dict:
        rows = await db.execute(
            text(
                """
                WITH RECURSIVE walk AS (
                    SELECT :paper_id::text AS node_id, 0 AS depth
                    UNION
                    SELECT
                        CASE WHEN pl.source_id = walk.node_id THEN pl.target_id ELSE pl.source_id END AS node_id,
                        walk.depth + 1 AS depth
                    FROM walk
                    JOIN paper_links pl
                      ON pl.workspace_id = current_workspace_id()
                     AND (pl.source_id = walk.node_id OR pl.target_id = walk.node_id)
                    WHERE walk.depth < :depth
                )
                SELECT DISTINCT node_id FROM walk
                """
            ),
            {"paper_id": paper_id, "depth": depth},
        )
        node_ids = [r.node_id for r in rows.all()]
        if not node_ids:
            return {"nodes": [], "edges": []}

        placeholders = ", ".join([f":n{i}" for i in range(len(node_ids))])
        params = {f"n{i}": node_id for i, node_id in enumerate(node_ids)}

        node_rows = await db.execute(
            text(f"SELECT id, title FROM papers WHERE workspace_id = current_workspace_id() AND id IN ({placeholders})"),
            params,
        )
        edge_rows = await db.execute(
            text(
                f"SELECT source_id, target_id, link_type, strength, metadata "
                f"FROM paper_links "
                f"WHERE workspace_id = current_workspace_id() "
                f"AND source_id IN ({placeholders}) AND target_id IN ({placeholders})"
            ),
            params,
        )

        return {
            "nodes": [{"id": r.id, "title": r.title} for r in node_rows.all()],
            "edges": [
                {
                    "source": r.source_id,
                    "target": r.target_id,
                    "link_type": r.link_type,
                    "strength": r.strength,
                    "metadata": r.metadata,
                }
                for r in edge_rows.all()
            ],
        }

    async def get_contradictions_db(self, db: AsyncSession) -> list[dict]:
        rows = await db.execute(
            text(
                "SELECT source_id AS source, target_id AS target, metadata "
                "FROM paper_links "
                "WHERE workspace_id = current_workspace_id() AND link_type = 'CONTRADICTS'"
            )
        )
        return [dict(r) for r in rows.mappings().all()]


knowledge_graph = KnowledgeGraph()
