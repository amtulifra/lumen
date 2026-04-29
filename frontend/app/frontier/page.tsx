"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

interface Suggestion {
  direction: string;
  rationale: string;
  papers: string[];
  difficulty: string;
}

interface SuggestResult {
  suggestions: Suggestion[];
  relevant_papers: Array<{ id: string; title: string }>;
}

const DIFFICULTY_COLOR: Record<string, string> = {
  "1-week project": "text-method border-method",
  "1-month project": "text-bench border-bench",
  "PhD-level": "text-contradicts border-contradicts",
};

export default function FrontierPage() {
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SuggestResult | null>(null);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!notes.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await api.getSuggestions(notes) as SuggestResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get suggestions");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">frontier suggestions</h1>
        <p className="text-xs text-muted">
          describe what you&apos;re thinking about — lumen will suggest what to build next
        </p>
      </div>

      <div className="space-y-3">
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="I'm working on efficient attention mechanisms and thinking about whether sparse patterns are sufficient for in-context learning..."
          rows={6}
          className="w-full bg-panel border border-border rounded px-4 py-3 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors resize-none"
        />
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {loading ? "thinking..." : "get suggestions"}
        </button>
      </div>

      {error && <p className="text-xs text-contradicts">{error}</p>}

      {result && (
        <div className="space-y-6">
          {result.suggestions.map((suggestion, i) => (
            <div key={i} className="border border-border rounded p-5 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <p className="text-sm font-medium text-text">{suggestion.direction}</p>
                <span
                  className={`shrink-0 text-xs border rounded px-2 py-0.5 ${DIFFICULTY_COLOR[suggestion.difficulty] ?? "text-muted border-border"}`}
                >
                  {suggestion.difficulty}
                </span>
              </div>
              <p className="text-xs text-muted">{suggestion.rationale}</p>
              {suggestion.papers?.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-muted">read first:</p>
                  <ul className="space-y-0.5">
                    {suggestion.papers.map((paper, j) => (
                      <li key={j} className="text-xs text-text">— {paper}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}

          {result.relevant_papers?.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-muted uppercase tracking-widest">related papers in your graph</p>
              <div className="flex flex-wrap gap-2">
                {result.relevant_papers.map((paper) => (
                  <Link
                    key={paper.id}
                    href={`/paper/${paper.id}`}
                    className="text-xs border border-border rounded px-2 py-1 text-text hover:border-accent transition-colors"
                  >
                    {paper.title.length > 40 ? paper.title.slice(0, 38) + "…" : paper.title}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
