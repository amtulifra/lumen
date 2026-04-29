"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import Link from "next/link";
import { use } from "react";

interface Researcher {
  id: string;
  name: string;
  institution: string;
  github_username: string | null;
  h_index: number;
  citation_count: number;
  research_themes: string[];
  paper_ids: string[];
  recent_repos: string[];
  refreshed_at: string;
}

export default function ResearcherPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: researcher, mutate } = useSWR(`researcher-${id}`, () => api.getResearcher(id));

  async function handleRefresh() {
    await api.refreshResearcher(id);
    mutate();
  }

  if (!researcher) {
    return <p className="text-xs text-muted">loading...</p>;
  }

  const r = researcher as Researcher;

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-xl font-semibold text-text">{r.name}</h1>
        <p className="text-xs text-muted">{r.institution}</p>
        {r.github_username && (
          <a
            href={`https://github.com/${r.github_username}`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-accent hover:underline"
          >
            @{r.github_username}
          </a>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Stat label="h-index" value={String(r.h_index ?? "—")} />
        <Stat label="citations" value={r.citation_count?.toLocaleString() ?? "—"} />
      </div>

      {r.research_themes?.length > 0 && (
        <Section title="Research Themes">
          <div className="flex flex-wrap gap-2">
            {r.research_themes.map((theme, i) => (
              <span key={i} className="text-xs border border-border rounded px-2 py-0.5 text-muted">
                {theme}
              </span>
            ))}
          </div>
        </Section>
      )}

      {r.paper_ids?.length > 0 && (
        <Section title="Papers in Lumen">
          <ul className="space-y-1">
            {r.paper_ids.map((paperId) => (
              <li key={paperId}>
                <Link href={`/paper/${paperId}`} className="text-xs text-text hover:text-accent transition-colors">
                  {paperId}
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.recent_repos?.length > 0 && (
        <Section title="GitHub Repos">
          <ul className="space-y-1">
            {r.recent_repos.map((repo, i) => (
              <li key={i}>
                <a href={repo} target="_blank" rel="noreferrer" className="text-xs text-accent hover:underline">
                  {repo.replace("https://github.com/", "")}
                </a>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <div className="flex items-center gap-4">
        <button
          onClick={handleRefresh}
          className="text-xs border border-border rounded px-3 py-1.5 text-muted hover:text-text hover:border-accent transition-colors"
        >
          refresh profile
        </button>
        {r.refreshed_at && (
          <p className="text-xs text-muted">
            last updated: {new Date(r.refreshed_at).toLocaleDateString()}
          </p>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-xs font-semibold text-muted uppercase tracking-widest">{title}</h2>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-border rounded p-4 space-y-1">
      <p className="text-xs text-muted">{label}</p>
      <p className="text-2xl font-semibold text-text">{value}</p>
    </div>
  );
}
