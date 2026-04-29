"use client";

import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

interface EvidenceItem {
  paper_id: string;
  claim_text: string;
  strength: number;
}

interface Hypothesis {
  id: string;
  text: string;
  status: "open" | "supported" | "refuted" | "mixed";
  evidence_for: EvidenceItem[];
  evidence_against: EvidenceItem[];
  created_at: string;
  updated_at: string;
}

const STATUS_STYLE: Record<string, string> = {
  open: "text-muted border-border",
  supported: "text-method border-method",
  refuted: "text-contradicts border-contradicts",
  mixed: "text-bench border-bench",
};

export default function HypothesesPage() {
  const { data: hypotheses, mutate } = useSWR("hypotheses", api.listHypotheses);
  const [newText, setNewText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function handleCreate() {
    if (!newText.trim() || submitting) return;
    setSubmitting(true);
    try {
      await api.createHypothesis(newText.trim());
      setNewText("");
      mutate();
    } finally {
      setSubmitting(false);
    }
  }

  const items = (hypotheses as Hypothesis[]) ?? [];

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">hypothesis ledger</h1>
        <p className="text-xs text-muted">
          write down open questions — lumen watches every ingested paper for evidence
        </p>
      </div>

      <div className="flex gap-3">
        <input
          type="text"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          placeholder="I think sparse attention patterns are sufficient for in-context learning..."
          className="flex-1 bg-panel border border-border rounded px-4 py-2.5 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors"
        />
        <button
          onClick={handleCreate}
          disabled={submitting}
          className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 disabled:opacity-40"
        >
          add
        </button>
      </div>

      <div className="space-y-3">
        {items.length === 0 && (
          <p className="text-xs text-muted">no hypotheses yet. write your first one above.</p>
        )}
        {items.map((hypothesis) => (
          <div key={hypothesis.id} className="border border-border rounded">
            <button
              onClick={() => setExpanded(expanded === hypothesis.id ? null : hypothesis.id)}
              className="w-full flex items-start justify-between gap-4 px-4 py-3 text-left"
            >
              <p className="text-sm text-text">{hypothesis.text}</p>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`text-xs border rounded px-2 py-0.5 ${STATUS_STYLE[hypothesis.status]}`}
                >
                  {hypothesis.status}
                </span>
                <span className="text-muted text-xs">{expanded === hypothesis.id ? "−" : "+"}</span>
              </div>
            </button>

            {expanded === hypothesis.id && (
              <div className="px-4 pb-4 space-y-4 border-t border-border pt-4">
                <EvidenceList
                  title="evidence for"
                  items={hypothesis.evidence_for}
                  color="text-method"
                />
                <EvidenceList
                  title="evidence against"
                  items={hypothesis.evidence_against}
                  color="text-contradicts"
                />
                <p className="text-xs text-muted">
                  last updated: {new Date(hypothesis.updated_at).toLocaleDateString()}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceList({
  title,
  items,
  color,
}: {
  title: string;
  items: EvidenceItem[];
  color: string;
}) {
  if (!items?.length) return null;

  return (
    <div className="space-y-2">
      <p className={`text-xs font-semibold uppercase tracking-widest ${color}`}>{title}</p>
      {items.map((item, i) => (
        <div key={i} className="border-l-2 border-border pl-3 space-y-0.5">
          <p className="text-xs text-text">{item.claim_text}</p>
          <p className="text-xs text-muted">
            paper: {item.paper_id} · strength: {(item.strength * 100).toFixed(0)}%
          </p>
        </div>
      ))}
    </div>
  );
}
