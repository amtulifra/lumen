const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  ingestUrl: (url: string) =>
    request("/ingest", { method: "POST", body: JSON.stringify({ url }) }),

  ingestAbstract: (title: string, abstract: string) =>
    request("/ingest/abstract", {
      method: "POST",
      body: JSON.stringify({ title, abstract }),
    }),

  listPapers: () => request("/papers"),

  getPaper: (id: string) => request(`/papers/${id}`),

  getPaperLinks: (id: string) => request(`/papers/${id}/links`),

  getPaperResearchers: (id: string) => request(`/papers/${id}/researchers`),

  getSubgraph: (id: string, depth = 2) =>
    request(`/graph/subgraph/${id}?depth=${depth}`),

  getFullGraph: () => request("/graph/full"),

  getContradictions: () => request("/graph/contradictions"),

  getResearcher: (id: string) => request(`/researchers/${id}`),

  refreshResearcher: (id: string) =>
    request(`/researchers/${id}/refresh`, { method: "POST" }),

  getSuggestions: (notes: string) =>
    request("/suggestions", { method: "POST", body: JSON.stringify({ notes }) }),

  createHypothesis: (text: string) =>
    request("/hypotheses", { method: "POST", body: JSON.stringify({ text }) }),

  listHypotheses: () => request("/hypotheses"),

  getHypothesis: (id: string) => request(`/hypotheses/${id}`),

  getBenchmarkDrift: (dataset: string, metric: string) =>
    request(`/benchmarks/drift?dataset=${encodeURIComponent(dataset)}&metric=${encodeURIComponent(metric)}`),

  listDatasets: () => request("/benchmarks/datasets"),

  getRSSStatus: () => request("/rss/status"),

  triggerRSSRun: () => request("/rss/run", { method: "POST" }),
};
