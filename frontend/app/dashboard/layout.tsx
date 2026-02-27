'use client'

import React, { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { FiLogOut, FiUser, FiHome } from 'react-icons/fi'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/store/auth'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, loading, signOut } = useAuthStore()

  const displayName =
    (user?.user_metadata as any)?.full_name || user?.email || 'User'

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/auth')
    }
  }, [loading, user, router])

  const handleSignOut = async () => {
    try {
      await supabase.auth.signOut()
    } catch (e) {
      console.error('Error signing out:', e)
    } finally {
      signOut()
      router.replace('/auth')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Navigation */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Increased nav height from h-16 to h-20 */}
          <div className="flex justify-between items-center h-20">
            {/* Left: Logo + Breadcrumb */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => router.push('/dashboard')}
                className="flex items-center gap-2"
              >
                <h1 className="text-2xl font-bold bg-gradient-to-r from-teal-600 to-emerald-600 bg-clip-text text-transparent">
                  ResearchFlow
                </h1>
              </button>

              {pathname?.startsWith('/dashboard/session/') && (
                <div className="hidden sm:flex items-center gap-2 text-gray-400">
                  <span>/</span>
                  <button
                    type="button"
                    onClick={() => router.push('/dashboard')}
                    className="text-sm hover:text-teal-600 transition-colors flex items-center gap-1"
                  >
                    <FiHome className="w-4 h-4" />
                    Dashboard
                  </button>
                </div>
              )}
            </div>

            {/* Right: User + Sign Out */}
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 text-sm text-gray-700 max-w-[200px]">
                <FiUser className="w-4 h-4" />
                <span className="truncate">{displayName}</span>
              </div>
              <button
                type="button"
                onClick={handleSignOut}
                className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <FiLogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}