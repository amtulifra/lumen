"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import Link from "next/link";
import { use } from "react";

interface Claim {
  text: string;
  confidence: number;
  evidence: string;
}

interface Method {
  name: string;
  description: string;
  is_novel: boolean;
}

interface Benchmark {
  dataset: string;
  metric: string;
  value: number;
  model: string;
  split: string;
}

interface KnowledgeObject {
  claims: Claim[];
  methods: Method[];
  benchmarks: Benchmark[];
  limitations: string[];
  open_problems: string[];
  keywords: string[];
}

interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  arxiv_url: string;
  knowledge_obj: KnowledgeObject;
}

interface PaperLink {
  source_id: string;
  target_id: string;
  link_type: string;
  strength: number;
  metadata: Record<string, unknown>;
}

interface Researcher {
  id: string;
  name: string;
  institution: string;
  github_username: string;
  h_index: number;
  citation_count: number;
  research_themes: string[];
}

export default function PaperPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: paper } = useSWR(`paper-${id}`, () => api.getPaper(id));
  const { data: links } = useSWR(`links-${id}`, () => api.getPaperLinks(id));
  const { data: researchers } = useSWR(`researchers-${id}`, () => api.getPaperResearchers(id));

  if (!paper) {
    return <p className="text-xs text-muted">loading...</p>;
  }

  const p = paper as Paper;
  const ko = p.knowledge_obj;
  const paperLinks = (links as PaperLink[]) ?? [];
  const authorProfiles = (researchers as Researcher[]) ?? [];

  const linksByType = paperLinks.reduce<Record<string, PaperLink[]>>((acc, link) => {
    acc[link.link_type] = [...(acc[link.link_type] ?? []), link];
    return acc;
  }, {});

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-xl font-semibold text-text">{p.title}</h1>
        <p className="text-xs text-muted">{p.authors?.join(", ")} · {p.year}</p>
        {p.arxiv_url && (
          <a href={p.arxiv_url} target="_blank" rel="noreferrer" className="text-xs text-accent hover:underline">
            arxiv →
          </a>
        )}
      </div>

      {ko?.keywords?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {ko.keywords.map((kw, i) => (
            <span key={i} className="text-xs border border-border rounded px-2 py-0.5 text-muted">
              {kw}
            </span>
          ))}
        </div>
      )}

      <Section title="Claims">
        {ko?.claims?.map((claim, i) => (
          <div key={i} className="border-l-2 border-border pl-4 space-y-1">
            <p className="text-sm text-text">{claim.text}</p>
            <div className="flex items-center gap-3">
              <ConfidenceBar value={claim.confidence} />
              <span className="text-xs text-accent">{(claim.confidence * 100).toFixed(0)}%</span>
            </div>
            <p className="text-xs text-muted italic">{claim.evidence}</p>
          </div>
        ))}
      </Section>

      <Section title="Methods">
        {ko?.methods?.map((method, i) => (
          <div key={i} className="flex gap-3 items-start">
            <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded border ${method.is_novel ? "border-method text-method" : "border-border text-muted"}`}>
              {method.is_novel ? "novel" : "borrowed"}
            </span>
            <div>
              <p className="text-sm text-text font-medium">{method.name}</p>
              <p className="text-xs text-muted">{method.description}</p>
            </div>
          </div>
        ))}
      </Section>

      <Section title="Benchmarks">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted border-b border-border">
              <th className="text-left py-1">dataset</th>
              <th className="text-left py-1">metric</th>
              <th className="text-left py-1">model</th>
              <th className="text-left py-1">split</th>
              <th className="text-right py-1">value</th>
            </tr>
          </thead>
          <tbody>
            {ko?.benchmarks?.map((bm, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                <td className="py-1.5 text-text">{bm.dataset}</td>
                <td className="py-1.5 text-muted">{bm.metric}</td>
                <td className="py-1.5 text-muted">{bm.model}</td>
                <td className="py-1.5 text-muted">{bm.split}</td>
                <td className="py-1.5 text-right text-accent">{bm.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {ko?.limitations?.length > 0 && (
        <Section title="Limitations">
          <ul className="space-y-1">
            {ko.limitations.map((lim, i) => (
              <li key={i} className="text-xs text-muted">— {lim}</li>
            ))}
          </ul>
        </Section>
      )}

      {ko?.open_problems?.length > 0 && (
        <Section title="Open Problems">
          <ul className="space-y-1">
            {ko.open_problems.map((problem, i) => (
              <li key={i} className="text-xs text-muted">→ {problem}</li>
            ))}
          </ul>
        </Section>
      )}

      {Object.entries(linksByType).map(([type, typeLinks]) => (
        <Section key={type} title={`Linked: ${type.toLowerCase().replace("_", " ")}`}>
          {typeLinks.map((link, i) => {
            const otherId = link.source_id === id ? link.target_id : link.source_id;
            return (
              <div key={i} className="flex items-center justify-between text-xs">
                <Link href={`/paper/${otherId}`} className="text-text hover:text-accent transition-colors">
                  {otherId}
                </Link>
                {link.metadata && Object.keys(link.metadata).length > 0 && (
                  <span className="text-muted">
                    {link.metadata.dataset
                      ? `${link.metadata.dataset} · ${link.metadata.metric}`
                      : `strength: ${link.strength?.toFixed(2)}`}
                  </span>
                )}
              </div>
            );
          })}
        </Section>
      ))}

      {authorProfiles.length > 0 && (
        <Section title="Authors">
          <div className="grid grid-cols-2 gap-4">
            {authorProfiles.map((researcher) => (
              <Link
                key={researcher.id}
                href={`/researchers/${researcher.id}`}
                className="border border-border rounded p-3 hover:border-accent transition-colors space-y-1"
              >
                <p className="text-sm text-text">{researcher.name}</p>
                <p className="text-xs text-muted">{researcher.institution}</p>
                <div className="flex gap-3 text-xs text-muted">
                  <span>h={researcher.h_index}</span>
                  <span>{researcher.citation_count?.toLocaleString()} citations</span>
                </div>
                {researcher.github_username && (
                  <p className="text-xs text-accent">@{researcher.github_username}</p>
                )}
              </Link>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-xs font-semibold text-muted uppercase tracking-widest">{title}</h2>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="w-24 h-1 bg-border rounded-full overflow-hidden">
      <div
        className="h-full bg-accent rounded-full"
        style={{ width: `${value * 100}%` }}
      />
    </div>
  );
}
