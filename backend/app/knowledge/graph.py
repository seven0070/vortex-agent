"""Knowledge Graph – persistent graph storage and traversal."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from ..models import KnowledgeNode, KnowledgeEdge, SessionLocal


class KnowledgeGraph:
    """
    Thin wrapper around the KnowledgeNode / KnowledgeEdge tables.
    Provides CRUD and traversal helpers.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------
    def add_node(
        self,
        *,
        user_id: str,
        entity_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            node_id=str(uuid4()),
            user_id=user_id,
            agent_id=agent_id,
            entity_type=entity_type,
            name=name,
            properties=properties or {},
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.db.query(KnowledgeNode).filter_by(node_id=node_id).first()

    def find_nodes(
        self,
        *,
        user_id: str,
        entity_type: Optional[str] = None,
        name_contains: Optional[str] = None,
        limit: int = 50,
    ) -> List[KnowledgeNode]:
        q = self.db.query(KnowledgeNode).filter_by(user_id=user_id)
        if entity_type:
            q = q.filter_by(entity_type=entity_type)
        if name_contains:
            q = q.filter(KnowledgeNode.name.ilike(f"%{name_contains}%"))
        return q.limit(limit).all()

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------
    def add_edge(
        self,
        *,
        source_node: str,
        target_node: str,
        relationship: str,
        weight: float = 1.0,
    ) -> KnowledgeEdge:
        edge = KnowledgeEdge(
            edge_id=str(uuid4()),
            source_node=source_node,
            target_node=target_node,
            relationship=relationship,
            weight=weight,
        )
        self.db.add(edge)
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def get_edges(
        self,
        *,
        source_node: Optional[str] = None,
        target_node: Optional[str] = None,
        relationship: Optional[str] = None,
        limit: int = 100,
    ) -> List[KnowledgeEdge]:
        q = self.db.query(KnowledgeEdge)
        if source_node:
            q = q.filter_by(source_node=source_node)
        if target_node:
            q = q.filter_by(target_node=target_node)
        if relationship:
            q = q.filter_by(relationship=relationship)
        return q.limit(limit).all()

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------
    def neighbors(
        self,
        node_id: str,
        *,
        direction: str = "both",  # "outgoing", "incoming", "both"
        relationship: Optional[str] = None,
        max_depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Breadth‑first search up to max_depth.
        Returns a list of dicts with keys: node, edge, depth.
        """
        visited = set()
        results = []
        from collections import deque

        queue = deque([(node_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)

            # Outgoing edges
            if direction in ("outgoing", "both"):
                out_edges = self.get_edges(source_node=current, relationship=relationship)
                for e in out_edges:
                    target = self.get_node(e.target_node)
                    if target:
                        results.append({"node": target, "edge": e, "depth": depth})
                        queue.append((target.node_id, depth + 1))

            # Incoming edges
            if direction in ("incoming", "both"):
                in_edges = self.get_edges(target_node=current, relationship=relationship)
                for e in in_edges:
                    source = self.get_node(e.source_node)
                    if source:
                        results.append({"node": source, "edge": e, "depth": depth})
                        queue.append((source.node_id, depth + 1))

        return results

    def path_between(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 4,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Find any path between two nodes (shortest in terms of hops).
        Returns list of dicts {node, edge, depth} or None.
        """
        # Simple BFS from start to end
        from collections import deque

        queue = deque([(start_id, [])])
        visited = {start_id}

        while queue:
            current, path = queue.popleft()
            if current == end_id:
                # Reconstruct full path details
                full = []
                # path stores edges; we need nodes too
                return path + [{"node": self.get_node(end_id), "edge": None, "depth": len(path)}]

            if len(path) >= max_depth:
                continue

            for e in self.get_edges(source_node=current):
                nxt = e.target_node
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [{"node": self.get_node(current), "edge": e, "depth": len(path)}]))

        return None

    # ------------------------------------------------------------------
    # Statistics / inspection
    # ------------------------------------------------------------------
    def stats(self, user_id: str) -> Dict[str, int]:
        node_count = self.db.query(KnowledgeNode).filter_by(user_id=user_id).count()
        edge_count = self.db.query(KnowledgeEdge).filter_by(user_id=user_id).count()
        return {"nodes": node_count, "edges": edge_count}


# ----------------------------------------------------------------------
# Factory used by orchestration to obtain a KG instance
# ----------------------------------------------------------------------
def KnowledgeGraphFactory(db: Session) -> KnowledgeGraph:
    return KnowledgeGraph(db)