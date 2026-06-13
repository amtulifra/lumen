"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";

type Severity = "possible" | "likely" | "strong" | "verified";

interface ConflictItem {
  id: string;
  paper_a_id: string;
  paper_b_id: string;
  paper_a_title: string;
  paper_b_title: string;
  paper_a_year: number;
  paper_b_year: number;
  dataset: string;
  metric: string;
  model: string;
  split_a: string;
  split_b: string;
  value_a: number;
  value_b: number;
  delta: number;
  severity: Severity;
  context_mismatch: boolean;
  reasoning: string;
  user_feedback?: "agree" | "disagree" | null;
}

interface ClaimConflictItem {
  id: string;
  parent_claim_id: string;
  child_claim_id: string;
  parent_paper_id: string;
  child_paper_id: string;
  relation: "challenges" | "refines";
  severity: Severity;
  confidence: number;
  reasoning: string;
  parent_claim_text: string;
  child_claim_text: string;
  parent_paper_title: string;
  child_paper_title: string;
  user_feedback?: "agree" | "disagree" | null;
}

const SEVERITIES: Severity[] = ["possible", "likely", "strong", "verified"];
const CLAIM_RELATIONS: Array<"challenges" | "refines"> = ["challenges", "refines"];
const SEVERITY_STYLES: Record<Severity, string> = {
  possible: "border-muted text-muted",
  likely: "border-bench text-bench",
  strong: "border-contradicts text-contradicts",
  verified: "border-contradicts text-contradicts",
};

export default function ConflictsPage() {
  const [mode, setMode] = useState<"benchmark" | "claim">("benchmark");
  const [severity, setSeverity] = useState<"" | Severity>("");
  const [dataset, setDataset] = useState("");
  const [relation, setRelation] = useState<"" | "challenges" | "refines">("");

  const { data: benchmarkData, mutate: mutateBenchmark } = useSWR(
    ["conflicts-benchmark", severity, dataset],
    () => api.listConflicts(severity || undefined, dataset.trim() || undefined, 200),
  );
  const benchmarkItems = (benchmarkData as ConflictItem[]) ?? [];

  const { data: claimData, mutate: mutateClaim } = useSWR(
    ["conflicts-claim", severity, relation],
    () => api.listClaimConflicts(severity || undefined, relation || undefined, 200),
  );
  const claimItems = (claimData as ClaimConflictItem[]) ?? [];

  const datasetOptions = useMemo(
    () => Array.from(new Set(benchmarkItems.map((item) => item.dataset))).sort(),
    [benchmarkItems],
  );

  async function handleBenchmarkFeedback(conflictId: string, feedback: "agree" | "disagree") {
    await api.submitConflictFeedback(conflictId, feedback);
    mutateBenchmark();
  }

  async function handleClaimFeedback(conflictId: string, feedback: "agree" | "disagree") {
    await api.submitClaimConflictFeedback(conflictId, feedback);
    mutateClaim();
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">conflicts</h1>
        <p className="text-xs text-muted">
          benchmark conflicts ranked by severity with context mismatch and feedback.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setMode("benchmark")}
          className={`text-xs border rounded px-3 py-1.5 ${
            mode === "benchmark" ? "border-accent text-accent" : "border-border text-muted"
          }`}
        >
          benchmark
        </button>
        <button
          onClick={() => setMode("claim")}
          className={`text-xs border rounded px-3 py-1.5 ${
            mode === "claim" ? "border-accent text-accent" : "border-border text-muted"
          }`}
        >
          claim
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as "" | Severity)}
          className="bg-panel border border-border rounded px-3 py-2 text-xs text-text"
        >
          <option value="">all severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        {mode === "benchmark" ? (
          <select
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
            className="bg-panel border border-border rounded px-3 py-2 text-xs text-text"
          >
            <option value="">all datasets</option>
            {datasetOptions.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        ) : (
          <select
            value={relation}
            onChange={(e) => setRelation(e.target.value as "" | "challenges" | "refines")}
            className="bg-panel border border-border rounded px-3 py-2 text-xs text-text"
          >
            <option value="">all relations</option>
            {CLAIM_RELATIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        )}
      </div>

      {mode === "benchmark" && benchmarkItems.length === 0 ? (
        <p className="text-xs text-muted">no benchmark conflicts detected yet.</p>
      ) : null}

      {mode === "claim" && claimItems.length === 0 ? (
        <p className="text-xs text-muted">no claim conflicts detected yet.</p>
      ) : null}

      {mode === "benchmark" ? (
        <div className="space-y-3">
          {benchmarkItems.map((item) => (
            <article key={item.id} className="border border-border rounded p-4 space-y-2 bg-panel/50">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] border rounded px-2 py-0.5 uppercase ${SEVERITY_STYLES[item.severity]}`}>
                    {item.severity}
                  </span>
                  <span className="text-xs text-muted">
                    {item.dataset} · {item.metric}
                  </span>
                </div>
                <span className="text-xs text-muted">|delta| {Math.abs(item.delta).toFixed(2)}</span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="space-y-1">
                  <p className="text-text">{item.paper_a_title}</p>
                  <p className="text-muted">
                    {item.paper_a_year} · value {item.value_a}
                  </p>
                  <Link href={`/paper/${item.paper_a_id}`} className="text-accent hover:underline">
                    open paper A
                  </Link>
                </div>
                <div className="space-y-1">
                  <p className="text-text">{item.paper_b_title}</p>
                  <p className="text-muted">
                    {item.paper_b_year} · value {item.value_b}
                  </p>
                  <Link href={`/paper/${item.paper_b_id}`} className="text-accent hover:underline">
                    open paper B
                  </Link>
                </div>
              </div>

              <p className="text-xs text-muted">
                context: model {item.model || "n/a"} · split {item.split_a || "n/a"} vs {item.split_b || "n/a"} ·{" "}
                {item.context_mismatch ? "mismatch" : "matched"}
              </p>
              <p className="text-xs text-text">{item.reasoning}</p>

              <div className="flex gap-2">
                <button
                  onClick={() => handleBenchmarkFeedback(item.id, "agree")}
                  className={`text-[10px] border rounded px-2 py-0.5 ${
                    item.user_feedback === "agree"
                      ? "border-method text-method"
                      : "border-border text-muted hover:text-text"
                  }`}
                >
                  agree
                </button>
                <button
                  onClick={() => handleBenchmarkFeedback(item.id, "disagree")}
                  className={`text-[10px] border rounded px-2 py-0.5 ${
                    item.user_feedback === "disagree"
                      ? "border-contradicts text-contradicts"
                      : "border-border text-muted hover:text-text"
                  }`}
                >
                  disagree
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {mode === "claim" ? (
        <div className="space-y-3">
          {claimItems.map((item) => (
            <article key={item.id} className="border border-border rounded p-4 space-y-2 bg-panel/50">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] border rounded px-2 py-0.5 uppercase ${SEVERITY_STYLES[item.severity]}`}>
                    {item.severity}
                  </span>
                  <span className="text-xs text-muted">{item.relation}</span>
                </div>
                <span className="text-xs text-muted">confidence {Math.round(item.confidence * 100)}%</span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="space-y-1">
                  <p className="text-muted">parent claim</p>
                  <p className="text-text">{item.parent_claim_text}</p>
                  <Link href={`/paper/${item.parent_paper_id}`} className="text-accent hover:underline">
                    open parent paper
                  </Link>
                </div>
                <div className="space-y-1">
                  <p className="text-muted">child claim</p>
                  <p className="text-text">{item.child_claim_text}</p>
                  <Link href={`/paper/${item.child_paper_id}`} className="text-accent hover:underline">
                    open child paper
                  </Link>
                </div>
              </div>

              <p className="text-xs text-text">{item.reasoning}</p>

              <div className="flex gap-2">
                <button
                  onClick={() => handleClaimFeedback(item.id, "agree")}
                  className={`text-[10px] border rounded px-2 py-0.5 ${
                    item.user_feedback === "agree"
                      ? "border-method text-method"
                      : "border-border text-muted hover:text-text"
                  }`}
                >
                  agree
                </button>
                <button
                  onClick={() => handleClaimFeedback(item.id, "disagree")}
                  className={`text-[10px] border rounded px-2 py-0.5 ${
                    item.user_feedback === "disagree"
                      ? "border-contradicts text-contradicts"
                      : "border-border text-muted hover:text-text"
                  }`}
                >
                  disagree
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}
