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
    <main className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <header className="w-full py-6 px-6 md:px-12">
        <div className="flex items-center gap-2">
          <Logo size={32} />
          <span 
            className="text-2xl font-bold text-black"
            style={{ fontFamily: "'Zalando Sans Expanded', sans-serif" }}
          >
            hunt
          </span>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 max-w-7xl mx-auto px-6 md:px-12 py-8 md:py-16 w-full">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-16 lg:gap-24 items-start">
          {/* Form - appears first on mobile, second on desktop */}
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

          {/* Value Proposition - appears second on mobile, first on desktop */}
          <div className="w-full order-last md:order-first">
            <ValueProposition />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full py-8 px-6 md:px-12">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-gray-500">
          <p>© {new Date().getFullYear()} Hunt. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-black transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-black transition-colors">Terms of Use</a>
          </div>
        </div>
      </footer>
    </main>
  )
}
