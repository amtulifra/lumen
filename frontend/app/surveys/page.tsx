"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

interface KeyMethod {
  name: string;
  description: string;
  first_paper: string;
  year: number;
  novelty: string;
}

interface BenchmarkProgression {
  dataset: string;
  metric: string;
  trajectory: string;
}

interface Contradiction {
  description: string;
  papers_for: string[];
  papers_against: string[];
}

interface Survey {
  title: string;
  topic: string;
  since_year: number;
  paper_count: number;
  paper_ids: string[];
  key_methods: KeyMethod[];
  benchmark_progression: BenchmarkProgression[];
  unresolved_problems: string[];
  contradictions: Contradiction[];
  research_gaps: string[];
  recommended_reading_order: string[];
}

const NOVELTY_COLOR: Record<string, string> = {
  foundational: "text-accent border-accent",
  incremental: "text-bench border-bench",
  applied: "text-muted border-border",
};

export default function SurveysPage() {
  const [topic, setTopic] = useState("");
  const [sinceYear, setSinceYear] = useState("");
  const [loading, setLoading] = useState(false);
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [error, setError] = useState("");

  async function handleGenerate() {
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    setSurvey(null);
    try {
      const year = sinceYear ? parseInt(sinceYear) : 0;
      const data = await api.generateSurvey(topic.trim(), year) as Survey;
      setSurvey(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate survey");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">survey generation</h1>
        <p className="text-xs text-muted">
          generate a structured survey from papers already in your graph
        </p>
      </div>

      <div className="flex gap-3 items-end">
        <div className="flex-1 space-y-1">
          <label className="text-xs text-muted">topic</label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. sparse attention mechanisms"
            className="w-full bg-panel border border-border rounded px-3 py-2 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors"
            onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
          />
        </div>
        <div className="w-28 space-y-1">
          <label className="text-xs text-muted">since year</label>
          <input
            value={sinceYear}
            onChange={(e) => setSinceYear(e.target.value)}
            placeholder="e.g. 2022"
            className="w-full bg-panel border border-border rounded px-3 py-2 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors"
          />
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 transition-opacity disabled:opacity-40 whitespace-nowrap"
        >
          {loading ? "generating..." : "generate survey"}
        </button>
      </div>

      {error && <p className="text-xs text-contradicts">{error}</p>}

      {survey && (
        <div className="space-y-8">
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-text">{survey.title}</h2>
            <p className="text-xs text-muted">
              {survey.paper_count} papers · {survey.since_year ? `since ${survey.since_year}` : "all years"}
            </p>
          </div>

          {survey.key_methods?.length > 0 && (
            <SurveySection title="Key Methods">
              <div className="space-y-3">
                {survey.key_methods.map((method, i) => (
                  <div key={i} className="flex gap-3 items-start">
                    <span className={`shrink-0 text-xs border rounded px-1.5 py-0.5 ${NOVELTY_COLOR[method.novelty] ?? "text-muted border-border"}`}>
                      {method.novelty}
                    </span>
                    <div>
                      <p className="text-sm text-text font-medium">{method.name}</p>
                      <p className="text-xs text-muted">{method.description}</p>
                      <p className="text-xs text-muted mt-0.5">first in: {method.first_paper} ({method.year})</p>
                    </div>
                  </div>
                ))}
              </div>
            </SurveySection>
          )}

          {survey.benchmark_progression?.length > 0 && (
            <SurveySection title="Benchmark Progression">
              <div className="space-y-2">
                {survey.benchmark_progression.map((bp, i) => (
                  <div key={i} className="text-xs">
                    <span className="text-accent font-medium">{bp.dataset} / {bp.metric}</span>
                    <p className="text-muted mt-0.5">{bp.trajectory}</p>
                  </div>
                ))}
              </div>
            </SurveySection>
          )}

          {survey.contradictions?.length > 0 && (
            <SurveySection title="Unresolved Contradictions">
              <div className="space-y-3">
                {survey.contradictions.map((c, i) => (
                  <div key={i} className="border-l-2 border-contradicts pl-3 space-y-1">
                    <p className="text-sm text-text">{c.description}</p>
                    <div className="text-xs text-muted">
                      <span className="text-method">for: </span>{c.papers_for?.join(", ")}
                    </div>
                    <div className="text-xs text-muted">
                      <span className="text-contradicts">against: </span>{c.papers_against?.join(", ")}
                    </div>
                  </div>
                ))}
              </div>
            </SurveySection>
          )}

          {survey.unresolved_problems?.length > 0 && (
            <SurveySection title="Unresolved Problems">
              <ul className="space-y-1">
                {survey.unresolved_problems.map((p, i) => (
                  <li key={i} className="text-xs text-muted">→ {p}</li>
                ))}
              </ul>
            </SurveySection>
          )}

          {survey.research_gaps?.length > 0 && (
            <SurveySection title="Research Gaps">
              <ul className="space-y-1">
                {survey.research_gaps.map((g, i) => (
                  <li key={i} className="text-xs text-muted">— {g}</li>
                ))}
              </ul>
            </SurveySection>
          )}

          {survey.recommended_reading_order?.length > 0 && (
            <SurveySection title="Recommended Reading Order">
              <ol className="space-y-1">
                {survey.recommended_reading_order.map((t, i) => (
                  <li key={i} className="text-xs text-text">{i + 1}. {t}</li>
                ))}
              </ol>
            </SurveySection>
          )}

          {survey.paper_ids?.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-muted uppercase tracking-widest">papers surveyed</p>
              <div className="flex flex-wrap gap-2">
                {survey.paper_ids.map((pid) => (
                  <Link
                    key={pid}
                    href={`/paper/${pid}`}
                    className="text-xs border border-border rounded px-2 py-1 text-text hover:border-accent transition-colors"
                  >
                    {pid}
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

function SurveySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-muted uppercase tracking-widest">{title}</h3>
      {children}
    </div>
  );
}
