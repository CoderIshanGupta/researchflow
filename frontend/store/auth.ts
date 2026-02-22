import { create } from 'zustand'
import { User } from '@supabase/supabase-js'

interface AuthState {
  user: User | null
  loading: boolean
  setUser: (user: User | null) => void
  setLoading: (loading: boolean) => void
  signOut: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  setUser: (user: User | null) => set({ user, loading: false }),
  setLoading: (loading: boolean) => set({ loading }),
  signOut: () => set({ user: null, loading: false }),
}))