'use client'

import { useState, useEffect } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
import confetti from 'canvas-confetti'
import { getSupabase } from '@/lib/supabase'
import { TECH_FIELDS, SENIORITY_LEVELS, COUNTRIES, WORK_TYPES, ROLE_TYPES } from '@/lib/data'

type AdditionalInfoProps = {
  waitlistId: string
  onComplete: () => void
  onProgress?: (current: number, total: number) => void
}

type Step = 'welcome' | 'field' | 'seniority' | 'pay' | 'country' | 'workType' | 'roleType'

const STEPS: Step[] = ['welcome', 'field', 'seniority', 'pay', 'country', 'workType', 'roleType']

export function AdditionalInfo({ waitlistId, onComplete, onProgress }: AdditionalInfoProps) {
  const [currentStep, setCurrentStep] = useState<Step>('welcome')
  const [field, setField] = useState('')
  const [seniority, setSeniority] = useState('')
  const [expectedPay, setExpectedPay] = useState('')
  const [country, setCountry] = useState('')
  const [workType, setWorkType] = useState<string[]>([])
  const [roleType, setRoleType] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    // Fire confetti once on mount - one pump from each side
    const colors = ['#FF0000', '#FF7F00', '#FFFF00', '#00FF00', '#0000FF', '#4B0082', '#9400D3']

    // Left side
    confetti({
      particleCount: 50,
      angle: 60,
      spread: 55,
      origin: { x: 0, y: 0.8 },
      colors,
    })

    // Right side
    confetti({
      particleCount: 50,
      angle: 120,
      spread: 55,
      origin: { x: 1, y: 0.8 },
      colors,
    })
  }, [])

  // Report progress to parent
  useEffect(() => {
    const currentIndex = STEPS.indexOf(currentStep)
    const totalQuestions = STEPS.length - 1 // Exclude welcome step
    const questionNumber = currentIndex // welcome is 0, so first question is 1
    onProgress?.(questionNumber, totalQuestions)
  }, [currentStep, onProgress])

  const toggleWorkType = (id: string) => {
    setWorkType(prev => 
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    )
  }

  const toggleRoleType = (id: string) => {
    setRoleType(prev => 
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    )
  }

  const goToNextStep = () => {
    const currentIndex = STEPS.indexOf(currentStep)
    if (currentIndex < STEPS.length - 1) {
      setCurrentStep(STEPS[currentIndex + 1])
    }
  }

  const handleSubmit = async () => {
    setIsLoading(true)

    try {
      await getSupabase().from('waitlist_details').insert({
        waitlist_id: waitlistId,
        field: field || null,
        seniority: seniority || null,
        expected_pay: expectedPay ? parseInt(expectedPay) : null,
        country: country || null,
        work_type: workType.length > 0 ? workType : null,
        role_type: roleType.length > 0 ? roleType : null,
      })

      onComplete()
    } catch {
      // Still complete even if details fail to save
      onComplete()
    }
  }

  const handleSkip = () => {
    goToNextStep()
  }

  const handleFinalSkip = () => {
    handleSubmit()
  }

  const currentStepIndex = STEPS.indexOf(currentStep)
  const totalQuestions = STEPS.length - 1 // Exclude welcome step
  const questionNumber = currentStepIndex // Since welcome is 0, first question is 1

  // Welcome step with thank you message
  if (currentStep === 'welcome') {
    return (
      <div className="p-8 md:p-10 text-center">
        <div className="flex justify-center mb-6">
          <img src="/party.png" alt="Celebration" className="w-20 h-20 object-contain" />
        </div>
        
        <h2 className="text-2xl md:text-3xl font-bold text-black mb-4">
          You're on the list!
        </h2>
        
        <p className="text-gray-600 mb-8 max-w-md mx-auto">
          We would love to know a bit more about you to help define hunt's next steps by answering a few questions.
        </p>

        <button
          onClick={goToNextStep}
          className="w-full bg-[#FF4500] hover:bg-[#E63E00] text-white font-semibold py-3 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors"
        >
          Continue
          <ArrowRight className="w-5 h-5" />
        </button>

        <button
          onClick={onComplete}
          className="w-full text-gray-500 hover:text-black font-medium py-3 mt-3 transition-colors"
        >
          Skip for now
        </button>
      </div>
    )
  }

  // Question steps
  return (
    <div className="p-8 md:p-10">
      {/* Field question */}
      {currentStep === 'field' && (
        <div>
          <h3 className="text-xl font-bold text-black mb-2">
            What field are you working in?
          </h3>
          <p className="text-gray-500 text-sm mb-6">
            This helps us show you relevant opportunities.
          </p>
          <div className="relative mb-6">
            <select
              value={field}
              onChange={(e) => setField(e.target.value)}
              className="w-full pl-4 pr-10 py-3 rounded-lg border border-gray-200 bg-white text-black focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all appearance-none cursor-pointer"
            >
              <option value="">Select your field...</option>
              {TECH_FIELDS.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4">
              <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* Seniority question */}
      {currentStep === 'seniority' && (
        <div>
          <h3 className="text-xl font-bold text-black mb-2">
            What's your level of seniority?
          </h3>
          <p className="text-gray-500 text-sm mb-6">
            We'll match you with roles at your experience level.
          </p>
          <div className="relative mb-6">
            <select
              value={seniority}
              onChange={(e) => setSeniority(e.target.value)}
              className="w-full pl-4 pr-10 py-3 rounded-lg border border-gray-200 bg-white text-black focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all appearance-none cursor-pointer"
            >
              <option value="">Select your level...</option>
              {SENIORITY_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4">
              <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* Pay question */}
      {currentStep === 'pay' && (
        <div>
          <h3 className="text-xl font-bold text-black mb-2">
            What's your expected annual pay?
          </h3>
          <p className="text-gray-500 text-sm mb-6">
            Pre-tax amount helps us filter opportunities for you.
          </p>
          <div className="relative mb-6">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">$</span>
            <input
              type="number"
              value={expectedPay}
              onChange={(e) => setExpectedPay(e.target.value)}
              placeholder="e.g. 120000"
              min="0"
              className="w-full pl-8 pr-4 py-3 rounded-lg border border-gray-200 bg-white text-black placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all"
            />
          </div>
        </div>
      )}

      {/* Country question */}
      {currentStep === 'country' && (
        <div>
          <h3 className="text-xl font-bold text-black mb-2">
            Where are you located?
          </h3>
          <p className="text-gray-500 text-sm mb-6">
            We'll prioritize opportunities in your region.
          </p>
          <div className="relative mb-6">
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="w-full pl-4 pr-10 py-3 rounded-lg border border-gray-200 bg-white text-black focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all appearance-none cursor-pointer"
            >
              <option value="">Select your country...</option>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4">
              <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* Work type question */}
      {currentStep === 'workType' && (
        <div>
          <h3 className="text-xl font-bold text-black mb-2">
            Remote or onsite?
          </h3>
          <p className="text-gray-500 text-sm mb-6">
            Select all that apply to you.
          </p>
          <div className="flex flex-wrap gap-3 mb-6">
            {WORK_TYPES.map((type) => (
              <button
                key={type.id}
                type="button"
                onClick={() => toggleWorkType(type.id)}
                className={`px-4 py-2 rounded-lg border-2 font-medium transition-all ${
                  workType.includes(type.id)
                    ? 'border-[#FF4500] bg-[#FF4500] text-white'
                    : 'border-gray-200 bg-white text-black hover:border-gray-300'
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Role type question */}
      {currentStep === 'roleType' && (
        <div>
          <h3 className="text-xl font-bold text-black mb-2">
            Permanent or contract?
          </h3>
          <p className="text-gray-500 text-sm mb-6">
            Select all that apply to you.
          </p>
          <div className="flex flex-wrap gap-3 mb-6">
            {ROLE_TYPES.map((type) => (
              <button
                key={type.id}
                type="button"
                onClick={() => toggleRoleType(type.id)}
                className={`px-4 py-2 rounded-lg border-2 font-medium transition-all ${
                  roleType.includes(type.id)
                    ? 'border-[#FF4500] bg-[#FF4500] text-white'
                    : 'border-gray-200 bg-white text-black hover:border-gray-300'
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex flex-col gap-3">
        {currentStep === 'roleType' ? (
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            className="w-full bg-[#FF4500] hover:bg-[#E63E00] text-white font-semibold py-3 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                Finish
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        ) : (
          <button
            onClick={goToNextStep}
            className="w-full bg-[#FF4500] hover:bg-[#E63E00] text-white font-semibold py-3 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            Continue
            <ArrowRight className="w-5 h-5" />
          </button>
        )}
        <button
          onClick={currentStep === 'roleType' ? handleFinalSkip : handleSkip}
          className="w-full text-gray-500 hover:text-black font-medium py-2 transition-colors"
        >
          Skip
        </button>
      </div>

    </div>
  )
}
