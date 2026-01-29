'use client'

import { useState, useCallback } from 'react'
import { Logo } from '@/components/Logo'
import { ValueProposition } from '@/components/ValueProposition'
import { WaitlistForm } from '@/components/WaitlistForm'
import { AdditionalInfo } from '@/components/AdditionalInfo'
import { ThankYou } from '@/components/ThankYou'

type Step = 'initial' | 'additional' | 'complete'

export default function Home() {
  const [step, setStep] = useState<Step>('initial')
  const [waitlistId, setWaitlistId] = useState<string>('')
  const [progress, setProgress] = useState({ current: 0, total: 6 })

  const handleWaitlistSuccess = (id: string) => {
    setWaitlistId(id)
    setStep('additional')
  }

  const handleAdditionalComplete = () => {
    setStep('complete')
  }

  const handleProgress = useCallback((current: number, total: number) => {
    setProgress({ current, total })
  }, [])

  return (
    <main className="min-h-screen md:h-screen bg-white flex flex-col md:overflow-hidden">
      {/* Header */}
      <header className="w-full py-5 md:py-5 lg:py-6 px-6 md:px-8 lg:px-12 shrink-0 border-b border-gray-200">
        <div className="flex items-center justify-center gap-3 md:gap-2">
          <Logo size={32} />
          <span 
            className="text-2xl md:text-xl lg:text-2xl font-bold text-black"
            style={{ fontFamily: "'Zalando Sans Expanded', sans-serif" }}
          >
            hunt<span className="text-[#FF4500]">.</span>
          </span>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 max-w-7xl mx-auto px-6 md:px-10 lg:px-12 py-8 md:py-6 lg:py-8 w-full min-h-0">
        {step === 'initial' ? (
          <div className="grid grid-cols-1 md:grid-cols-[1fr_1px_1fr] gap-10 md:gap-10 lg:gap-14 items-center md:h-full">
            {/* Value Proposition - appears second on mobile, first on desktop */}
            <div className="w-full order-last md:order-first px-2 md:px-0">
              <ValueProposition />
            </div>

            {/* Vertical Divider - hidden on mobile */}
            <div className="hidden md:block w-px bg-gray-200 h-3/4 self-center" />

            {/* Form - appears first on mobile, last on desktop */}
            <div className="w-full order-first md:order-last">
              <WaitlistForm onSuccess={handleWaitlistSuccess} />
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center md:h-full">
            <div className="w-full max-w-md">
              {step === 'additional' && (
                <AdditionalInfo 
                  waitlistId={waitlistId} 
                  onComplete={handleAdditionalComplete}
                  onProgress={handleProgress}
                />
              )}
              {step === 'complete' && (
                <ThankYou />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Progress indicator - shown during questions */}
      {step === 'additional' && progress.current > 0 && (
        <div className="w-full px-6 md:px-8 lg:px-12 pb-4">
          <div className="max-w-md mx-auto">
            <div className="text-sm text-gray-500 text-center mb-2">
              Question {progress.current} of {progress.total}
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-[#FF4500] transition-all duration-300"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="w-full py-5 md:py-4 lg:py-5 px-6 md:px-8 lg:px-12 shrink-0">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-center md:justify-between items-center gap-3 md:gap-2 text-sm md:text-xs lg:text-sm text-gray-500">
          <p>© {new Date().getFullYear()} Hunt. All rights reserved.</p>
          <div className="flex gap-6 md:gap-4 lg:gap-6">
            <a href="#" className="hover:text-black transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-black transition-colors">Terms of Use</a>
          </div>
        </div>
      </footer>
    </main>
  )
}
