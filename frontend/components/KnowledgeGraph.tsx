"use client";

import * as d3 from "d3";
import { useEffect, useRef } from "react";
import { useAppStore } from "@/lib/store";

interface GraphNode {
  id: string;
  title?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  link_type: string;
  strength?: number;
  metadata?: Record<string, unknown>;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const EDGE_COLOR: Record<string, string> = {
  CITES: "#525252",
  SHARES_METHOD: "#4ade80",
  BENCHMARKS_ON: "#60a5fa",
  CONTRADICTS: "#f87171",
};

export default function KnowledgeGraph({ data }: { data: GraphData }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { setSelectedPaperId, setSelectedEdge } = useAppStore();

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const container = svgRef.current.parentElement!;
    const width = container.clientWidth;
    const height = container.clientHeight;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    const zoomLayer = svg.append("g");

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on("zoom", (event) => {
          zoomLayer.attr("transform", event.transform);
        })
    );

    const nodes = data.nodes.map((n) => ({ ...n }));
    const edgeMap = new Map(nodes.map((n) => [n.id, n]));

    const links = data.edges
      .filter((e) => edgeMap.has(e.source) && edgeMap.has(e.target))
      .map((e) => ({ ...e }));

    const simulation = d3
      .forceSimulation(nodes as d3.SimulationNodeDatum[])
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d: d3.SimulationNodeDatum) => (d as GraphNode).id)
          .distance(120)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(20));

    const linkElements = zoomLayer
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => EDGE_COLOR[d.link_type] ?? "#525252")
      .attr("stroke-width", (d) => (d.link_type === "CONTRADICTS" ? 2 : 1))
      .attr("stroke-opacity", 0.7)
      .style("cursor", "pointer")
      .on("click", (event, d) => {
        event.stopPropagation();
        setSelectedEdge({
          link_type: d.link_type,
          metadata: d.metadata,
          source: (d.source as unknown as GraphNode).id,
          target: (d.target as unknown as GraphNode).id,
        });
      });

    const nodeElements = zoomLayer
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", 7)
      .attr("fill", "#161616")
      .attr("stroke", "#a3e635")
      .attr("stroke-width", 1.5)
      .style("cursor", "pointer")
      .on("click", (_, d) => setSelectedPaperId((d as GraphNode).id))
      .call(
        d3
          .drag<SVGCircleElement, d3.SimulationNodeDatum>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as never
      );

    const labelElements = zoomLayer
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => {
        const title = (d as GraphNode).title ?? (d as GraphNode).id;
        return title.length > 24 ? title.slice(0, 22) + "…" : title;
      })
      .attr("font-size", 9)
      .attr("fill", "#737373")
      .attr("dy", "0.35em")
      .attr("dx", 10);

    simulation.on("tick", () => {
      linkElements
        .attr("x1", (d) => (d.source as d3.SimulationNodeDatum).x ?? 0)
        .attr("y1", (d) => (d.source as d3.SimulationNodeDatum).y ?? 0)
        .attr("x2", (d) => (d.target as d3.SimulationNodeDatum).x ?? 0)
        .attr("y2", (d) => (d.target as d3.SimulationNodeDatum).y ?? 0);

      nodeElements
        .attr("cx", (d) => (d as d3.SimulationNodeDatum).x ?? 0)
        .attr("cy", (d) => (d as d3.SimulationNodeDatum).y ?? 0);

      labelElements
        .attr("x", (d) => (d as d3.SimulationNodeDatum).x ?? 0)
        .attr("y", (d) => (d as d3.SimulationNodeDatum).y ?? 0);
    });

    return () => { simulation.stop(); };
  }, [data, setSelectedPaperId, setSelectedEdge]);

  return <svg ref={svgRef} className="w-full h-full" />;
}
