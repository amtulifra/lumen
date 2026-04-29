import { create } from "zustand";

interface AppState {
  selectedPaperId: string | null;
  selectedEdge: Record<string, unknown> | null;
  setSelectedPaperId: (id: string | null) => void;
  setSelectedEdge: (edge: Record<string, unknown> | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedPaperId: null,
  selectedEdge: null,
  setSelectedPaperId: (id) => set({ selectedPaperId: id, selectedEdge: null }),
  setSelectedEdge: (edge) => set({ selectedEdge: edge }),
}));
