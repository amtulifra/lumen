const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") {
    return {};
  }
  const workspaceId = window.localStorage.getItem("lumen.workspaceId");
  const token = window.localStorage.getItem("lumen.accessToken");
  const role = window.localStorage.getItem("lumen.role");
  const userId = window.localStorage.getItem("lumen.userId");

  return {
    ...(workspaceId ? { "X-Workspace-Id": workspaceId } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(role ? { "X-Role": role } : {}),
    ...(userId ? { "X-User-Id": userId } : {}),
  };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders() },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

async function requestBlob(path: string, options?: RequestInit): Promise<Blob> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { ...authHeaders(), ...(options?.headers ?? {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.blob();
}

export const api = {
  ingestUrl: (url: string) =>
    request("/ingest", { method: "POST", body: JSON.stringify({ url }) }),

  ingestAbstract: (title: string, abstract: string) =>
    request("/ingest/abstract", {
      method: "POST",
      body: JSON.stringify({ title, abstract }),
    }),

  listPapers: (q?: string) =>
    request(`/papers${q && q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`),

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

  listRSSSubscriptions: () => request("/rss/subscriptions"),

  addRSSSubscription: (category: string, url: string) =>
    request("/rss/subscriptions", {
      method: "POST",
      body: JSON.stringify({ category, url }),
    }),

  removeRSSSubscription: (category: string) =>
    request(`/rss/subscriptions/${encodeURIComponent(category)}`, { method: "DELETE" }),

  deletePaper: (id: string) => request(`/papers/${id}`, { method: "DELETE" }),

  getNeighbors: (id: string, linkType?: string) =>
    request(`/papers/${id}/neighbors${linkType ? `?link_type=${linkType}` : ""}`),

  getNotifications: (unreadOnly = false) =>
    request(`/notifications${unreadOnly ? "?unread_only=true" : ""}`),

  markRead: (id: string) =>
    request(`/notifications/${id}/read`, { method: "POST" }),

  markAllRead: () => request("/notifications/read-all", { method: "POST" }),

  // Phase 11: Research Memory
  queryMemory: (question: string) =>
    request(`/memory/query?question=${encodeURIComponent(question)}`, { method: "POST" }),
  listMemoryEvents: (limit = 50, eventType?: string) =>
    request(`/memory/events?limit=${limit}${eventType ? `&event_type=${eventType}` : ""}`),

  // Phase 8: Claim Intelligence
  getClaimLineage: (claimId: string) => request(`/claims/${claimId}/lineage`),
  getClaimScore: (claimId: string) => request(`/claims/${claimId}/score`),
  getPaperClaimScores: (paperId: string) => request(`/papers/${paperId}/claim-scores`),

  // Phase 9: Research Rabbit Mode + Missing Experiments
  getRabbitHole: (paperId: string) => request(`/papers/${paperId}/rabbit-hole`),
  getMissingExperiments: (paperId: string) => request(`/papers/${paperId}/missing-experiments`),

  // Phase 10: Survey, Gap Ranking, Contamination
  generateSurvey: (topic: string, sinceYear = 0) =>
    request(`/surveys/generate?topic=${encodeURIComponent(topic)}&since_year=${sinceYear}`, {
      method: "POST",
    }),
  getResearchGaps: (limit = 20) => request(`/gaps?limit=${limit}`),
  getBenchmarkContamination: () => request("/benchmarks/contamination"),
  getPaperContaminationWarnings: (paperId: string) =>
    request(`/papers/${paperId}/contamination-warnings`),

  // Phase 12: Export
  exportBibtex: () => requestBlob("/export/bibtex"),
  exportObsidian: (topic?: string) =>
    requestBlob(`/export/obsidian${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`),
  exportNotion: (databaseId: string, topic?: string) => {
    const params = new URLSearchParams({ database_id: databaseId });
    if (topic) params.set("topic", topic);
    return request(`/export/notion?${params.toString()}`, { method: "POST" });
  },
};
