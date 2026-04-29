"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type IngestStep = "idle" | "fetching" | "extracting" | "linking" | "done" | "error";

interface KnowledgeObject {
  claims: Array<{ text: string; confidence: number; evidence: string }>;
  methods: Array<{ name: string; description: string; is_novel: boolean }>;
  benchmarks: Array<{ dataset: string; metric: string; value: number; model: string }>;
  limitations: string[];
  open_problems: string[];
  keywords: string[];
}

interface IngestResult {
  paper_id: string;
  knowledge_object: KnowledgeObject;
}

const SAMPLE_PAPERS = [
  { label: "Attention Is All You Need", url: "https://arxiv.org/abs/1706.03762" },
  { label: "LoRA", url: "https://arxiv.org/abs/2106.09685" },
  { label: "Mamba", url: "https://arxiv.org/abs/2312.00752" },
  { label: "RLHF", url: "https://arxiv.org/abs/2203.02155" },
];

const STEPS: Record<IngestStep, string> = {
  idle: "",
  fetching: "Fetching PDF...",
  extracting: "Extracting knowledge...",
  linking: "Linking to graph...",
  done: "Done.",
  error: "Something went wrong.",
};

export default function IngestPage() {
  const [input, setInput] = useState("");
  const [step, setStep] = useState<IngestStep>("idle");
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState("");
  const [expandedSection, setExpandedSection] = useState<string | null>("claims");

  async function handleIngest(url: string) {
    if (!url.trim()) return;
    setError("");
    setResult(null);

    setStep("fetching");
    await delay(400);
    setStep("extracting");

    try {
      const data = await api.ingestUrl(url) as IngestResult;
      setStep("linking");
      await delay(300);
      setStep("done");
      setResult(data);
    } catch (err) {
      setStep("error");
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  function toggleSection(section: string) {
    setExpandedSection(expandedSection === section ? null : section);
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">ingest a paper</h1>
        <p className="text-xs text-muted">paste an arxiv URL to extract structured knowledge</p>
      </div>

      <div className="space-y-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleIngest(input)}
          placeholder="https://arxiv.org/abs/..."
          className="w-full bg-panel border border-border rounded px-4 py-3 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors"
        />

        <div className="flex gap-2 flex-wrap">
          {SAMPLE_PAPERS.map((paper) => (
            <button
              key={paper.url}
              onClick={() => { setInput(paper.url); handleIngest(paper.url); }}
              className="text-xs text-muted border border-border rounded px-3 py-1 hover:border-accent hover:text-text transition-colors"
            >
              {paper.label}
            </button>
          ))}
        </div>

        <button
          onClick={() => handleIngest(input)}
          disabled={step === "fetching" || step === "extracting" || step === "linking"}
          className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          ingest
        </button>
      </div>

      {step !== "idle" && (
        <div className={`text-xs font-mono ${step === "error" ? "text-contradicts" : "text-accent"}`}>
          {STEPS[step]}
          {step === "error" && <p className="text-muted mt-1">{error}</p>}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <p className="text-xs text-muted">
            paper_id: <span className="text-text">{result.paper_id}</span>
          </p>

          <KOSection
            title="claims"
            expanded={expandedSection === "claims"}
            onToggle={() => toggleSection("claims")}
          >
            {result.knowledge_object.claims.map((claim, i) => (
              <div key={i} className="border-l-2 border-border pl-4 space-y-1">
                <p className="text-sm text-text">{claim.text}</p>
                <p className="text-xs text-muted">
                  confidence: <span className="text-accent">{(claim.confidence * 100).toFixed(0)}%</span>
                </p>
                <p className="text-xs text-muted italic">{claim.evidence}</p>
              </div>
            ))}
          </KOSection>

          <KOSection
            title="methods"
            expanded={expandedSection === "methods"}
            onToggle={() => toggleSection("methods")}
          >
            {result.knowledge_object.methods.map((method, i) => (
              <div key={i} className="flex gap-3 items-start">
                <span className={`text-xs px-1.5 py-0.5 rounded border ${method.is_novel ? "border-method text-method" : "border-border text-muted"}`}>
                  {method.is_novel ? "novel" : "borrowed"}
                </span>
                <div>
                  <p className="text-sm text-text font-medium">{method.name}</p>
                  <p className="text-xs text-muted">{method.description}</p>
                </div>
              </div>
            ))}
          </KOSection>

          <KOSection
            title="benchmarks"
            expanded={expandedSection === "benchmarks"}
            onToggle={() => toggleSection("benchmarks")}
          >
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted border-b border-border">
                  <th className="text-left py-1">dataset</th>
                  <th className="text-left py-1">metric</th>
                  <th className="text-left py-1">model</th>
                  <th className="text-right py-1">value</th>
                </tr>
              </thead>
              <tbody>
                {result.knowledge_object.benchmarks.map((bm, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="py-1.5 text-text">{bm.dataset}</td>
                    <td className="py-1.5 text-muted">{bm.metric}</td>
                    <td className="py-1.5 text-muted">{bm.model}</td>
                    <td className="py-1.5 text-right text-accent">{bm.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </KOSection>

          <KOSection
            title="limitations"
            expanded={expandedSection === "limitations"}
            onToggle={() => toggleSection("limitations")}
          >
            <ul className="space-y-2">
              {result.knowledge_object.limitations.map((lim, i) => (
                <li key={i} className="text-sm text-muted before:content-['—'] before:mr-2 before:text-border">
                  {lim}
                </li>
              ))}
            </ul>
          </KOSection>

          <KOSection
            title="open problems"
            expanded={expandedSection === "open_problems"}
            onToggle={() => toggleSection("open_problems")}
          >
            <ul className="space-y-2">
              {result.knowledge_object.open_problems.map((problem, i) => (
                <li key={i} className="text-sm text-muted before:content-['→'] before:mr-2 before:text-bench">
                  {problem}
                </li>
              ))}
            </ul>
          </KOSection>

          <div className="flex flex-wrap gap-2">
            {result.knowledge_object.keywords.map((kw, i) => (
              <span key={i} className="text-xs border border-border rounded px-2 py-0.5 text-muted">
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KOSection({
  title,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border rounded">
      <button
        onClick={onToggle}
        className="w-full flex justify-between items-center px-4 py-3 text-xs font-medium text-muted hover:text-text transition-colors"
      >
        <span>{title}</span>
        <span>{expanded ? "−" : "+"}</span>
      </button>
      {expanded && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </div>
  );
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
