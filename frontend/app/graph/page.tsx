"use client";

import { useState } from "react";
import useSWR from "swr";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import Link from "next/link";

const EDGE_TYPES = ["CITES", "SHARES_METHOD", "BENCHMARKS_ON", "CONTRADICTS"];

const EDGE_COLOR: Record<string, string> = {
  CITES: "#525252",
  SHARES_METHOD: "#4ade80",
  BENCHMARKS_ON: "#60a5fa",
  CONTRADICTS: "#f87171",
};

export default function GraphPage() {
  const { data: graphData, isLoading } = useSWR("full-graph", api.getFullGraph);
  const { selectedPaperId, selectedEdge, setSelectedPaperId, setSelectedEdge } = useAppStore();

  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set(EDGE_TYPES));

  const filteredData = graphData
    ? {
        nodes: (graphData as GraphData).nodes,
        edges: (graphData as GraphData).edges.filter((e: GraphEdge) =>
          activeFilters.has(e.link_type)
        ),
      }
    : { nodes: [], edges: [] };

  function toggleFilter(type: string) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col -mx-6 -my-8">
      <div className="px-6 py-3 border-b border-border flex items-center gap-6">
        <span className="text-xs text-muted">filter edges:</span>
        {EDGE_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => toggleFilter(type)}
            className="flex items-center gap-1.5 text-xs transition-opacity"
            style={{ opacity: activeFilters.has(type) ? 1 : 0.3 }}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: EDGE_COLOR[type] }}
            />
            {type.toLowerCase().replace("_", " ")}
          </button>
        ))}
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 relative">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">
              loading graph...
            </div>
          )}
          <KnowledgeGraph data={filteredData as GraphData} />
        </div>

        {(selectedPaperId || selectedEdge) && (
          <aside className="w-80 border-l border-border overflow-y-auto p-4 space-y-4">
            <button
              onClick={() => { setSelectedPaperId(null); setSelectedEdge(null); }}
              className="text-xs text-muted hover:text-text"
            >
              ← close
            </button>

            {selectedPaperId && (
              <PaperPanel paperId={selectedPaperId} />
            )}

            {selectedEdge && (
              <EdgePanel edge={selectedEdge as unknown as GraphEdge} />
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

function PaperPanel({ paperId }: { paperId: string }) {
  const { data: paper } = useSWR(`paper-${paperId}`, () => api.getPaper(paperId));

  if (!paper) return <p className="text-xs text-muted">loading...</p>;

  const p = paper as PaperData;
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium text-text">{p.title}</h2>
      <p className="text-xs text-muted">{p.authors?.join(", ")}</p>
      <p className="text-xs text-muted">{p.year}</p>
      <Link
        href={`/paper/${paperId}`}
        className="text-xs text-accent hover:underline"
      >
        view full paper →
      </Link>
    </div>
  );
}

function EdgePanel({ edge }: { edge: GraphEdge }) {
  const color = EDGE_COLOR[edge.link_type] ?? "#525252";
  const meta = edge.metadata ?? {};

  return (
    <div className="space-y-3">
      <span
        className="text-xs px-2 py-0.5 rounded border"
        style={{ borderColor: color, color }}
      >
        {edge.link_type}
      </span>
      {Object.entries(meta).map(([key, val]) => (
        <div key={key}>
          <p className="text-xs text-muted">{key}</p>
          <p className="text-xs text-text">{String(val)}</p>
        </div>
      ))}
    </div>
  );
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphNode {
  id: string;
  title?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  link_type: string;
  metadata?: Record<string, unknown>;
}

interface PaperData {
  title: string;
  authors: string[];
  year: number;
}
