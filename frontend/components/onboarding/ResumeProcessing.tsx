'use client'

import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'

interface ResumeProcessingProps {
  onComplete: (parsedProfile: {
    primaryRoles: string[]
    experienceLevel: string
    seniority: string
    careerPattern: string
    domains: string[]
    strengths: string[]
  }) => void
}

const processingSteps = [
  'Understanding roles and responsibilities',
  'Interpreting seniority and progression',
  'Inferring skills from context',
]

export function ResumeProcessing({ onComplete }: ResumeProcessingProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<number[]>([])

  useEffect(() => {
    const stepInterval = setInterval(() => {
      setCurrentStep(prev => {
        if (prev < processingSteps.length - 1) {
          setCompletedSteps(completed => [...completed, prev])
          return prev + 1
        }
        return prev
      })
    }, 2000)

    // Complete after all steps
    const completeTimeout = setTimeout(() => {
      setCompletedSteps(completed => [...completed, processingSteps.length - 1])
      
      // Simulate parsed profile data
      setTimeout(() => {
        onComplete({
          primaryRoles: ['Senior Product Manager'],
          experienceLevel: '8+ years',
          seniority: 'Senior IC',
          careerPattern: 'Growing scope and responsibility over time',
          domains: [
            'B2C marketplaces',
            'Growth & activation',
            'Cross-functional collaboration',
            'Scaling products and teams',
          ],
          strengths: [
            'Owning ambiguous problems',
            'Driving execution',
            'Working across design and engineering',
          ],
        })
      }, 800)
    }, 6500)

    return () => {
      clearInterval(stepInterval)
      clearTimeout(completeTimeout)
    }
  }, [onComplete])

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Title */}
      <div className="text-center mb-10">
        <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <Loader2 className="w-8 h-8 text-primary animate-spin" />
        </div>
        <h1 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
          Reading your experience…
        </h1>
      </div>

      {/* Processing Steps */}
      <div className="max-w-sm mx-auto space-y-4">
        {processingSteps.map((step, index) => {
          const isCompleted = completedSteps.includes(index)
          const isCurrent = currentStep === index && !isCompleted
          
          return (
            <div
              key={index}
              className={`flex items-center gap-4 p-4 rounded-xl transition-all duration-500 ${
                isCompleted
                  ? 'bg-green-50 border border-green-200'
                  : isCurrent
                  ? 'bg-orange-50 border border-orange-200'
                  : 'bg-gray-50 border border-gray-100'
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
                  isCompleted
                    ? 'bg-green-500'
                    : isCurrent
                    ? 'bg-primary'
                    : 'bg-gray-200'
                }`}
              >
                {isCompleted ? (
                  <Check className="w-4 h-4 text-white" strokeWidth={3} />
                ) : isCurrent ? (
                  <Loader2 className="w-4 h-4 text-white animate-spin" />
                ) : (
                  <span className="w-2 h-2 bg-gray-400 rounded-full" />
                )}
              </div>
              <span
                className={`font-medium transition-colors duration-300 ${
                  isCompleted
                    ? 'text-green-700'
                    : isCurrent
                    ? 'text-gray-900'
                    : 'text-gray-400'
                }`}
              >
                {step}
              </span>
            </div>
          )
        })}
      </div>

      {/* Time Estimate */}
      <p className="text-center text-sm text-gray-500 mt-8">
        This usually takes under 30 seconds.
      </p>
    </div>
  )
}
