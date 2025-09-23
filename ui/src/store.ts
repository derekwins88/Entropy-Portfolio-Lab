import { create } from "zustand";

type LiveState = {
  lastPing: number | null;
  setLastPing: (t: number) => void;
};

export const useLive = create<LiveState>((set) => ({
  lastPing: null,
  setLastPing: (t) => set({ lastPing: t })
}));
