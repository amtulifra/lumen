"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

interface GapEntry {
  topic: string;
  gap_score: number;
  paper_count: number;
  open_problem_count: number;
  claim_count: number;
  growth_rate: number;
  year_range: string;
}

interface ContaminationEntry {
  dataset: string;
  known_issues: string[];
  first_year: number;
  common_criticism: string;
  usage_count: number;
}

export default function GapsPage() {
  const { data: gaps, isLoading: gapsLoading } = useSWR("gaps", () =>
    api.getResearchGaps(30)
  );
  const { data: contamination, isLoading: contLoading } = useSWR(
    "contamination",
    () => api.getBenchmarkContamination()
  );

  const gapList = (gaps as GapEntry[]) ?? [];
  const contList = (contamination as ContaminationEntry[]) ?? [];

  return (
    <div className="max-w-3xl mx-auto space-y-12">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">research gaps</h1>
        <p className="text-xs text-muted">
          topics ranked by open questions relative to claimed solutions
        </p>
      </div>

      {gapsLoading ? (
        <p className="text-xs text-muted">loading...</p>
      ) : gapList.length === 0 ? (
        <p className="text-xs text-muted">no data yet — ingest papers to see gaps</p>
      ) : (
        <div className="space-y-2">
          {gapList.map((g, i) => (
            <div
              key={i}
              className="flex items-center justify-between border border-border rounded px-4 py-3 gap-4"
            >
              <div className="flex-1 min-w-0 space-y-0.5">
                <p className="text-sm text-text truncate">{g.topic}</p>
                <p className="text-xs text-muted">
                  {g.paper_count} papers · {g.open_problem_count} open problems · {g.year_range}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-sm font-mono text-accent">{g.gap_score.toFixed(2)}</p>
                <p className="text-xs text-muted">gap score</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-text">benchmark quality flags</h2>
          <p className="text-xs text-muted">
            known contamination, saturation, and coverage issues in common benchmarks
          </p>
        </div>

        {contLoading ? (
          <p className="text-xs text-muted">loading...</p>
        ) : contList.length === 0 ? (
          <p className="text-xs text-muted">no flagged benchmarks in your graph</p>
        ) : (
          <div className="space-y-2">
            {contList.map((c, i) => (
              <div
                key={i}
                className="border border-yellow-800 rounded px-4 py-3 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-yellow-400">{c.dataset}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted">{c.usage_count} papers use this</span>
                    <span className="text-xs text-muted">· {c.first_year}</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  {c.known_issues.map((issue, j) => (
                    <span
                      key={j}
                      className="text-xs border border-yellow-800 text-yellow-500 rounded px-1.5 py-0.5"
                    >
                      {issue}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted">{c.common_criticism}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
