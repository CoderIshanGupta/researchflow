import { create } from 'zustand'

export interface ResearchSession {
  id: string
  title: string
  topic: string
  description: string | null
  created_at: string
  updated_at: string
  paper_count?: number
}

interface DashboardState {
  sessions: ResearchSession[]
  activeSession: ResearchSession | null
  loading: boolean
  setSessions: (sessions: ResearchSession[]) => void
  setActiveSession: (session: ResearchSession | null) => void
  setLoading: (loading: boolean) => void
  addSession: (session: ResearchSession) => void
  updateSession: (id: string, updates: Partial<ResearchSession>) => void
  removeSession: (id: string) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  sessions: [],
  activeSession: null,
  loading: false,
  setSessions: (sessions: ResearchSession[]) => set({ sessions }),
  setActiveSession: (session: ResearchSession | null) => set({ activeSession: session }),
  setLoading: (loading: boolean) => set({ loading }),
  addSession: (session: ResearchSession) => set((state) => ({ 
    sessions: [session, ...state.sessions] 
  })),
  updateSession: (id: string, updates: Partial<ResearchSession>) => set((state) => ({
    sessions: state.sessions.map((s) => 
      s.id === id ? { ...s, ...updates } : s
    ),
  })),
  removeSession: (id: string) => set((state) => ({
    sessions: state.sessions.filter((s) => s.id !== id),
  })),
}))