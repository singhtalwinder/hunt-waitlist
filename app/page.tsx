'use client'

import { useState } from 'react'
import { Logo } from '@/components/Logo'
import { ValueProposition } from '@/components/ValueProposition'
import { WaitlistForm } from '@/components/WaitlistForm'
import { AdditionalInfo } from '@/components/AdditionalInfo'
import { ThankYou } from '@/components/ThankYou'

type Step = 'initial' | 'additional' | 'complete'

export default function Home() {
  const [step, setStep] = useState<Step>('initial')
  const [waitlistId, setWaitlistId] = useState<string>('')

  const handleWaitlistSuccess = (id: string) => {
    setWaitlistId(id)
    setStep('additional')
  }

  const handleAdditionalComplete = () => {
    setStep('complete')
  }

  return (
    <main className="min-h-screen md:h-screen bg-white flex flex-col md:overflow-hidden">
      {/* Header */}
      <header className="w-full py-4 lg:py-6 px-4 md:px-8 lg:px-12 shrink-0 border-b border-gray-200">
        <div className="flex items-center justify-center gap-2">
          <Logo size={28} />
          <span 
            className="text-xl lg:text-2xl font-bold text-black"
            style={{ fontFamily: "'Zalando Sans Expanded', sans-serif" }}
          >
            hunt.
          </span>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 max-w-7xl mx-auto px-4 md:px-8 lg:px-12 py-4 md:py-6 lg:py-8 w-full min-h-0">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1px_1fr] gap-8 md:gap-8 lg:gap-12 items-center md:h-full">
          {/* Value Proposition - appears second on mobile, first on desktop */}
          <div className="w-full order-last md:order-first">
            <ValueProposition />
          </div>

          {/* Vertical Divider - hidden on mobile */}
          <div className="hidden md:block w-px bg-gray-200 h-3/4 self-center" />

          {/* Form - appears first on mobile, last on desktop */}
          <div className="w-full order-first md:order-last">
            {step === 'initial' && (
              <WaitlistForm onSuccess={handleWaitlistSuccess} />
            )}
            {step === 'additional' && (
              <AdditionalInfo 
                waitlistId={waitlistId} 
                onComplete={handleAdditionalComplete} 
              />
            )}
            {step === 'complete' && (
              <ThankYou />
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full py-3 lg:py-4 px-4 md:px-8 lg:px-12 shrink-0">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-2 text-xs lg:text-sm text-gray-500">
          <p>© {new Date().getFullYear()} Hunt. All rights reserved.</p>
          <div className="flex gap-4 lg:gap-6">
            <a href="#" className="hover:text-black transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-black transition-colors">Terms of Use</a>
          </div>
        </div>
      </footer>
    </main>
  )
}
