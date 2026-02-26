'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { FiSearch, FiMessageSquare, FiFileText, FiTrendingUp, FiArrowRight, FiArrowLeft } from 'react-icons/fi'

interface OnboardingStep {
  icon: React.ReactNode
  title: string
  description: string
}

const steps: OnboardingStep[] = [
  {
    icon: <FiSearch className="w-12 h-12 sm:w-16 sm:h-16" />,
    title: 'Discover Research Papers',
    description: 'Search across millions of papers from Semantic Scholar and arXiv. Get AI-powered relevance ranking.',
  },
  {
    icon: <FiMessageSquare className="w-12 h-12 sm:w-16 sm:h-16" />,
    title: 'Chat with Your Sources',
    description: 'Ask questions and get answers from your research papers with precise citations.',
  },
  {
    icon: <FiFileText className="w-12 h-12 sm:w-16 sm:h-16" />,
    title: 'Generate Cited Drafts',
    description: 'Transform your research into well-structured documents with automatic citations.',
  },
  {
    icon: <FiTrendingUp className="w-12 h-12 sm:w-16 sm:h-16" />,
    title: 'Accelerate Your Research',
    description: 'Join thousands using ResearchFlow to work smarter, not harder.',
  },
]

export default function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState(0)
  const router = useRouter()

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      localStorage.setItem('onboarding_completed', 'true')
      router.push('/auth')
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSkip = () => {
    localStorage.setItem('onboarding_completed', 'true')
    router.push('/auth')
  }

  return (
    <div className="min-h-[100dvh] bg-gradient-to-br from-teal-500 via-emerald-500 to-cyan-500 flex flex-col items-center justify-center p-4">
      {/* Skip Button */}
      <div className="w-full max-w-lg flex justify-end mb-4">
        <button
          onClick={handleSkip}
          className="text-white/80 hover:text-white transition-colors font-medium text-sm sm:text-base"
        >
          Skip
        </button>
      </div>

      {/* Main Card */}
      <div className="w-full max-w-lg bg-white rounded-2xl sm:rounded-3xl shadow-2xl overflow-hidden">
        <div className="p-6 sm:p-8 md:p-12">
          {/* Progress Dots */}
          <div className="flex justify-center gap-2 mb-8 sm:mb-12">
            {steps.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentStep(index)}
                className={`h-2 rounded-full transition-all duration-300 ${
                  index === currentStep
                    ? 'w-8 bg-teal-600'
                    : index < currentStep
                    ? 'w-2 bg-teal-400'
                    : 'w-2 bg-gray-300'
                }`}
              />
            ))}
          </div>

          {/* Content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className="text-center"
            >
              {/* Icon */}
              <div className="flex justify-center mb-6 sm:mb-8">
                <div className="p-5 sm:p-6 bg-gradient-to-br from-teal-100 to-emerald-100 rounded-2xl sm:rounded-3xl text-teal-600">
                  {steps[currentStep].icon}
                </div>
              </div>

              {/* Title */}
              <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-3 sm:mb-4">
                {steps[currentStep].title}
              </h2>

              {/* Description */}
              <p className="text-base sm:text-lg text-gray-600 max-w-md mx-auto mb-8 sm:mb-12 px-2">
                {steps[currentStep].description}
              </p>

              {/* Navigation Buttons */}
              <div className="flex items-center justify-between max-w-xs sm:max-w-md mx-auto">
                <button
                  onClick={handlePrevious}
                  disabled={currentStep === 0}
                  className="p-2.5 sm:p-3 rounded-full hover:bg-gray-100 transition-colors disabled:opacity-0 disabled:cursor-not-allowed"
                >
                  <FiArrowLeft className="w-5 h-5 sm:w-6 sm:h-6 text-gray-600" />
                </button>

                <button
                  onClick={handleNext}
                  className="px-6 sm:px-8 py-3 sm:py-4 bg-gradient-to-r from-teal-600 to-emerald-600 text-white rounded-full font-semibold hover:shadow-lg transform hover:scale-105 transition-all duration-200 flex items-center gap-2 text-sm sm:text-base"
                >
                  {currentStep === steps.length - 1 ? 'Get Started' : 'Next'}
                  <FiArrowRight className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>

                <div className="w-10 sm:w-12" />
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Page Indicator */}
      <p className="text-white/80 text-sm mt-6">
        {currentStep + 1} of {steps.length}
      </p>
    </div>
  )
}