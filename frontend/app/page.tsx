'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    // Check if user has completed onboarding
    const onboardingCompleted = localStorage.getItem('onboarding_completed')
    
    if (onboardingCompleted) {
      router.push('/auth')
    } else {
      router.push('/onboarding')
    }
  }, [router])

  // Loading state while checking
  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 to-emerald-50 flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-gray-600">Loading...</p>
      </div>
    </div>
  )
}