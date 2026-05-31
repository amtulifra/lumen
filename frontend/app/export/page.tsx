"use client";

import { useState } from "react";
import { api } from "@/lib/api";

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportPage() {
  const [bibtexLoading, setBibtexLoading] = useState(false);
  const [obsidianLoading, setObsidianLoading] = useState(false);
  const [notionLoading, setNotionLoading] = useState(false);
  const [obsidianTopic, setObsidianTopic] = useState("");
  const [notionDbId, setNotionDbId] = useState("");
  const [notionTopic, setNotionTopic] = useState("");
  const [notionResult, setNotionResult] = useState<{ exported: number; total: number; errors: string[] } | null>(null);
  const [error, setError] = useState("");

  async function handleBibtex() {
    setBibtexLoading(true);
    setError("");
    try {
      const blob = await api.exportBibtex();
      downloadBlob(blob, "lumen_library.bib");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBibtexLoading(false);
    }
  }

  async function handleObsidian() {
    setObsidianLoading(true);
    setError("");
    try {
      const blob = await api.exportObsidian(obsidianTopic || undefined);
      downloadBlob(blob, "lumen_vault.zip");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setObsidianLoading(false);
    }
  }

  async function handleNotion() {
    if (!notionDbId.trim()) {
      setError("Notion database ID is required");
      return;
    }
    setNotionLoading(true);
    setError("");
    setNotionResult(null);
    try {
      const data = (await api.exportNotion(
        notionDbId.trim(),
        notionTopic.trim() || undefined
      )) as { exported: number; total: number; errors: string[] };
      setNotionResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setNotionLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-10">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-text">export</h1>
        <p className="text-xs text-muted">export your knowledge graph to other tools</p>
      </div>

      {error && <p className="text-xs text-contradicts">{error}</p>}

      {/* BibTeX */}
      <ExportCard
        title="BibTeX"
        description="Download all ingested papers as a .bib file compatible with LaTeX, Zotero, and any reference manager."
      >
        <button
          onClick={handleBibtex}
          disabled={bibtexLoading}
          className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {bibtexLoading ? "generating..." : "download .bib"}
        </button>
      </ExportCard>

      {/* Obsidian */}
      <ExportCard
        title="Obsidian Vault"
        description="Export as a zip of interlinked Markdown notes. Each paper gets its own .md file with [[wikilinks]] to related papers. Open the unzipped folder as an Obsidian vault."
      >
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs text-muted">filter by topic (optional)</label>
            <input
              value={obsidianTopic}
              onChange={(e) => setObsidianTopic(e.target.value)}
              placeholder="e.g. sparse attention — leave empty for all papers"
              className="w-full bg-surface border border-border rounded px-3 py-1.5 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors"
            />
          </div>
          <button
            onClick={handleObsidian}
            disabled={obsidianLoading}
            className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {obsidianLoading ? "generating..." : "download vault.zip"}
          </button>
        </div>
      </ExportCard>

      {/* Notion */}
      <ExportCard
        title="Notion"
        description="Push papers as database entries into an existing Notion database. Requires NOTION_API_KEY set in backend environment."
      >
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs text-muted">notion database ID</label>
            <input
              value={notionDbId}
              onChange={(e) => setNotionDbId(e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="w-full bg-surface border border-border rounded px-3 py-1.5 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors font-mono"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted">filter by topic (optional)</label>
            <input
              value={notionTopic}
              onChange={(e) => setNotionTopic(e.target.value)}
              placeholder="e.g. sparse attention"
              className="w-full bg-surface border border-border rounded px-3 py-1.5 text-sm text-text placeholder-muted outline-none focus:border-accent transition-colors"
            />
          </div>
          <button
            onClick={handleNotion}
            disabled={notionLoading}
            className="bg-accent text-surface text-xs font-semibold px-4 py-2 rounded hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {notionLoading ? "exporting..." : "export to notion"}
          </button>
          {notionResult && (
            <div className="text-xs space-y-1">
              <p className="text-method">
                exported {notionResult.exported} / {notionResult.total} papers
              </p>
              {notionResult.errors.length > 0 && (
                <ul className="text-contradicts space-y-0.5">
                  {notionResult.errors.map((e, i) => <li key={i}>— {e}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      </ExportCard>
    </div>
  );
}

function ExportCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border rounded p-5 space-y-4">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold text-text">{title}</h2>
        <p className="text-xs text-muted">{description}</p>
      </div>
      {children}
    </div>
  );
}
