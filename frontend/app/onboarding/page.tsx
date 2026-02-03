'use client'

import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { ResumeUpload } from '@/components/onboarding/ResumeUpload'
import { ResumeProcessing } from '@/components/onboarding/ResumeProcessing'
import { OnboardingQuestions } from '@/components/onboarding/OnboardingQuestions'
import { ProfileReview } from '@/components/onboarding/ProfileReview'
import { AllSet } from '@/components/onboarding/AllSet'
import { FirstMatches } from '@/components/onboarding/FirstMatches'

export type OnboardingStep = 
  | 'resume-upload'
  | 'resume-processing'
  | 'questions'
  | 'profile-review'
  | 'all-set'
  | 'first-matches'

export interface OnboardingData {
  resumeFile?: File
  linkedInConnected?: boolean
  direction?: string
  matchStrictness?: string
  workStrengths?: string[]
  guardrails?: string[]
  guardrailsFollowUp?: string[]
  // Parsed profile data (simulated)
  parsedProfile?: {
    primaryRoles: string[]
    experienceLevel: string
    seniority: string
    careerPattern: string
    domains: string[]
    strengths: string[]
  }
}

export default function OnboardingPage() {
  const [step, setStep] = useState<OnboardingStep>('resume-upload')
  const [data, setData] = useState<OnboardingData>({})

  const updateData = (newData: Partial<OnboardingData>) => {
    setData(prev => ({ ...prev, ...newData }))
  }

  const getStepNumber = () => {
    const steps = ['resume-upload', 'resume-processing', 'questions', 'profile-review', 'all-set', 'first-matches']
    return steps.indexOf(step) + 1
  }

  const totalSteps = 6

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <header className="w-full py-5 px-6 md:px-12 lg:px-20 shrink-0 border-b border-gray-100">
        <nav className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/paper.png"
              alt="Hunt"
              width={32}
              height={32}
              priority
            />
            <span className="text-2xl font-bold text-black font-hunt">
              hunt<span className="text-primary">.</span>
            </span>
          </Link>
        </nav>
      </header>

      {/* Main content */}
      <div className="flex-1 flex items-center justify-center px-6 py-8 md:py-12">
        <div className="w-full max-w-xl">
          {step === 'resume-upload' && (
            <ResumeUpload
              onContinue={(resumeData) => {
                updateData(resumeData)
                setStep('resume-processing')
              }}
            />
          )}
          
          {step === 'resume-processing' && (
            <ResumeProcessing
              onComplete={(parsedProfile) => {
                updateData({ parsedProfile })
                setStep('questions')
              }}
            />
          )}
          
          {step === 'questions' && (
            <OnboardingQuestions
              onComplete={(answers) => {
                updateData(answers)
                setStep('profile-review')
              }}
            />
          )}
          
          {step === 'profile-review' && (
            <ProfileReview
              data={data}
              onConfirm={(updatedData) => {
                updateData(updatedData)
                setStep('all-set')
              }}
            />
          )}
          
          {step === 'all-set' && (
            <AllSet
              onShowMatches={() => setStep('first-matches')}
            />
          )}
          
          {step === 'first-matches' && (
            <FirstMatches />
          )}
        </div>
      </div>

      {/* Progress indicator */}
      {step !== 'first-matches' && (
        <div className="w-full px-6 md:px-12 pb-6">
          <div className="max-w-xl mx-auto">
            <div className="flex items-center justify-center gap-2 mb-3">
              {['resume-upload', 'resume-processing', 'questions', 'profile-review', 'all-set'].map((s, index) => (
                <div
                  key={s}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    index < getStepNumber() ? 'bg-primary w-12' : 'bg-gray-200 w-8'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="w-full py-4 px-6 md:px-12 shrink-0 border-t border-gray-100">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-center md:justify-between items-center gap-2 text-sm text-gray-500">
          <p>© {new Date().getFullYear()} Hunt. All rights reserved.</p>
          <div className="flex gap-6">
            <Link href="/privacy" className="hover:text-black transition-colors">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-black transition-colors">Terms of Use</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
