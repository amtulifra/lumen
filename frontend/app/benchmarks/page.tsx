"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import Link from "next/link";

interface Dataset {
  dataset: string;
  metric: string;
}

interface DriftPoint {
  year: number;
  sota_value: number;
  model: string;
  paper_id: string;
  paper_title: string;
}

export default function BenchmarksPage() {
  const { data: datasets } = useSWR("datasets", api.listDatasets);
  const [selected, setSelected] = useState<Dataset | null>(null);

  const { data: driftData } = useSWR(
    selected ? `drift-${selected.dataset}-${selected.metric}` : null,
    () => api.getBenchmarkDrift(selected!.dataset, selected!.metric)
  );

  const datasetList = (datasets as Dataset[]) ?? [];
  const points = (driftData as DriftPoint[]) ?? [];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">benchmark drift</h1>
        <p className="text-xs text-muted">SOTA leaderboard shifts over time across ingested papers</p>
      </div>

      {datasetList.length === 0 ? (
        <p className="text-xs text-muted">no benchmark data yet. ingest some papers first.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {datasetList.map((ds, i) => (
            <button
              key={i}
              onClick={() => setSelected(ds)}
              className={`text-xs border rounded px-3 py-1.5 transition-colors ${
                selected?.dataset === ds.dataset && selected?.metric === ds.metric
                  ? "border-accent text-text"
                  : "border-border text-muted hover:border-accent hover:text-text"
              }`}
            >
              {ds.dataset} · {ds.metric}
            </button>
          ))}
        </div>
      )}

      {selected && points.length > 0 && (
        <div className="space-y-6">
          <div className="border border-border rounded p-4">
            <p className="text-xs text-muted mb-4">
              {selected.dataset} — {selected.metric}
            </p>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={points}>
                <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
                <XAxis
                  dataKey="year"
                  tick={{ fill: "#525252", fontSize: 10 }}
                  axisLine={{ stroke: "#262626" }}
                />
                <YAxis
                  tick={{ fill: "#525252", fontSize: 10 }}
                  axisLine={{ stroke: "#262626" }}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  contentStyle={{
                    background: "#161616",
                    border: "1px solid #262626",
                    borderRadius: 4,
                    fontSize: 11,
                    color: "#e5e5e5",
                  }}
                  formatter={(value: number, name: string) => [value, name]}
                  labelFormatter={(label) => `Year: ${label}`}
                />
                <Line
                  type="monotone"
                  dataKey="sota_value"
                  stroke="#a3e635"
                  strokeWidth={2}
                  dot={{ fill: "#a3e635", r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2">
            <p className="text-xs text-muted uppercase tracking-widest">data points</p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1">year</th>
                  <th className="text-left py-1">model</th>
                  <th className="text-right py-1">value</th>
                  <th className="text-left py-1 pl-4">paper</th>
                </tr>
              </thead>
              <tbody>
                {points.map((point, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="py-1.5 text-text">{point.year}</td>
                    <td className="py-1.5 text-muted">{point.model}</td>
                    <td className="py-1.5 text-right text-accent">{point.sota_value}</td>
                    <td className="py-1.5 pl-4">
                      <Link href={`/paper/${point.paper_id}`} className="text-text hover:text-accent transition-colors">
                        {point.paper_title?.length > 40
                          ? point.paper_title.slice(0, 38) + "…"
                          : point.paper_title}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
