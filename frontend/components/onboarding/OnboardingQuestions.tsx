'use client'

import { useState } from 'react'
import { ArrowRight, ArrowLeft, Check } from 'lucide-react'

interface OnboardingQuestionsProps {
  onComplete: (answers: {
    direction: string
    matchStrictness: string
    workStrengths: string[]
    guardrails: string[]
    guardrailsFollowUp?: string[]
  }) => void
}

interface Question {
  id: string
  title: string
  prompt: string
  options: { id: string; label: string }[]
  multiSelect?: boolean
  maxSelections?: number
}

const questions: Question[] = [
  {
    id: 'direction',
    title: 'Direction',
    prompt: "What best describes what you're looking for next?",
    options: [
      { id: 'similar', label: "A role similar to what I've done before" },
      { id: 'more-scope', label: 'More scope or responsibility than my last role' },
      { id: 'different', label: 'Something meaningfully different' },
      { id: 'open', label: "I'm open — I want to see what fits" },
    ],
  },
  {
    id: 'matchStrictness',
    title: 'Match Strictness',
    prompt: 'How focused should we be when showing you jobs?',
    options: [
      { id: 'strict', label: "Only roles I'm clearly qualified for" },
      { id: 'mostly-strong', label: 'Mostly strong matches, with a few stretch roles' },
      { id: 'wide', label: "Cast a wider net — I'll decide" },
      { id: 'unsure', label: 'Not sure yet' },
    ],
  },
  {
    id: 'workStrengths',
    title: 'Work Style',
    prompt: 'In your best roles, what kind of work did you spend most of your time on?',
    options: [
      { id: 'building', label: 'Hands‑on building or execution' },
      { id: 'problem-solving', label: 'Solving unclear or messy problems' },
      { id: 'coordinating', label: 'Coordinating people, teams, or decisions' },
      { id: 'improving', label: 'Improving quality, systems, or process' },
    ],
    multiSelect: true,
    maxSelections: 2,
  },
  {
    id: 'guardrails',
    title: 'Guardrails',
    prompt: 'Are there roles you want us to avoid showing?',
    options: [
      { id: 'seniority-mismatch', label: 'Roles that feel too junior or too senior' },
      { id: 'high-stress', label: 'Roles with high stress or poor work‑life balance' },
      { id: 'company-fit', label: "Roles at companies that aren't a good fit for me" },
      { id: 'open', label: "Nothing in particular — I'm open" },
    ],
    multiSelect: true,
  },
]

const guardrailsFollowUpOptions = [
  { id: 'startups', label: 'Early-stage startups' },
  { id: 'enterprise', label: 'Large enterprise companies' },
  { id: 'contract', label: 'Contract or freelance work' },
  { id: 'finance', label: 'Finance / Banking' },
  { id: 'healthcare', label: 'Healthcare' },
  { id: 'crypto', label: 'Crypto / Web3' },
]

export function OnboardingQuestions({ onComplete }: OnboardingQuestionsProps) {
  const [currentQuestion, setCurrentQuestion] = useState(0)
  const [answers, setAnswers] = useState<{
    direction?: string
    matchStrictness?: string
    workStrengths: string[]
    guardrails: string[]
    guardrailsFollowUp: string[]
  }>({
    workStrengths: [],
    guardrails: [],
    guardrailsFollowUp: [],
  })
  const [showFollowUp, setShowFollowUp] = useState(false)

  const question = questions[currentQuestion]
  const isLastQuestion = currentQuestion === questions.length - 1

  const handleSelect = (optionId: string) => {
    if (question.multiSelect) {
      const currentSelections = (answers[question.id as keyof typeof answers] as string[]) || []
      const maxSelections = question.maxSelections || Infinity
      
      if (currentSelections.includes(optionId)) {
        setAnswers(prev => ({
          ...prev,
          [question.id]: currentSelections.filter(id => id !== optionId),
        }))
      } else if (currentSelections.length < maxSelections) {
        setAnswers(prev => ({
          ...prev,
          [question.id]: [...currentSelections, optionId],
        }))
      }
    } else {
      setAnswers(prev => ({
        ...prev,
        [question.id]: optionId,
      }))
    }
  }

  const handleFollowUpSelect = (optionId: string) => {
    const currentSelections = answers.guardrailsFollowUp
    if (currentSelections.includes(optionId)) {
      setAnswers(prev => ({
        ...prev,
        guardrailsFollowUp: currentSelections.filter(id => id !== optionId),
      }))
    } else {
      setAnswers(prev => ({
        ...prev,
        guardrailsFollowUp: [...currentSelections, optionId],
      }))
    }
  }

  const canContinue = () => {
    if (question.multiSelect) {
      const selections = (answers[question.id as keyof typeof answers] as string[]) || []
      return selections.length > 0
    }
    return !!answers[question.id as keyof typeof answers]
  }

  const handleContinue = () => {
    // Check if we need to show follow-up for guardrails
    if (question.id === 'guardrails' && answers.guardrails.includes('company-fit') && !showFollowUp) {
      setShowFollowUp(true)
      return
    }

    if (isLastQuestion || (question.id === 'guardrails' && showFollowUp)) {
      onComplete({
        direction: answers.direction || '',
        matchStrictness: answers.matchStrictness || '',
        workStrengths: answers.workStrengths,
        guardrails: answers.guardrails,
        guardrailsFollowUp: answers.guardrailsFollowUp,
      })
    } else {
      setCurrentQuestion(prev => prev + 1)
    }
  }

  const handleBack = () => {
    if (showFollowUp) {
      setShowFollowUp(false)
    } else if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1)
    }
  }

  // Render follow-up question for company fit
  if (showFollowUp) {
    return (
      <div className="animate-in fade-in slide-in-from-right-4 duration-300">
        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-medium text-primary mb-2">Follow-up</p>
          <h2 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-3">
            What types of companies should we avoid?
          </h2>
          <p className="text-gray-600">
            Select any that apply — you can change this anytime.
          </p>
        </div>

        {/* Options */}
        <div className="space-y-3 mb-8">
          {guardrailsFollowUpOptions.map(option => {
            const isSelected = answers.guardrailsFollowUp.includes(option.id)
            return (
              <button
                key={option.id}
                onClick={() => handleFollowUpSelect(option.id)}
                className={`w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left ${
                  isSelected
                    ? 'border-primary bg-orange-50'
                    : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-md border-2 flex items-center justify-center shrink-0 transition-all ${
                    isSelected
                      ? 'border-primary bg-primary'
                      : 'border-gray-300'
                  }`}
                >
                  {isSelected && <Check className="w-4 h-4 text-white" strokeWidth={3} />}
                </div>
                <span className={`font-medium ${isSelected ? 'text-gray-900' : 'text-gray-700'}`}>
                  {option.label}
                </span>
              </button>
            )
          })}
        </div>

        {/* Navigation */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleBack}
            className="flex items-center gap-2 px-5 py-3 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <button
            onClick={handleContinue}
            className="flex-1 px-6 py-3.5 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 flex items-center justify-center gap-2"
          >
            Continue
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-in fade-in slide-in-from-right-4 duration-300" key={currentQuestion}>
      {/* Framing (only on first question) */}
      {currentQuestion === 0 && (
        <div className="mb-8 p-6 bg-gray-50 rounded-2xl border border-gray-100">
          <h2 className="font-hunt text-xl font-bold text-black mb-2">
            A few quick questions
          </h2>
          <p className="text-gray-600">
            Your resume shows where you've been.
            <br />
            These help us understand what you want next and how picky to be.
          </p>
        </div>
      )}

      {/* Question Header */}
      <div className="mb-8">
        <p className="text-sm font-medium text-primary mb-2">
          Question {currentQuestion + 1} of {questions.length}
        </p>
        <h2 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-3">
          {question.prompt}
        </h2>
        {question.multiSelect && (
          <p className="text-gray-500 text-sm">
            {question.maxSelections
              ? `Select up to ${question.maxSelections}`
              : 'Select all that apply'}
          </p>
        )}
      </div>

      {/* Options */}
      <div className="space-y-3 mb-8">
        {question.options.map(option => {
          const isSelected = question.multiSelect
            ? ((answers[question.id as keyof typeof answers] as string[]) || []).includes(option.id)
            : answers[question.id as keyof typeof answers] === option.id

          return (
            <button
              key={option.id}
              onClick={() => handleSelect(option.id)}
              className={`w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left ${
                isSelected
                  ? 'border-primary bg-orange-50'
                  : 'border-gray-200 hover:border-gray-300 bg-white'
              }`}
            >
              {question.multiSelect ? (
                <div
                  className={`w-6 h-6 rounded-md border-2 flex items-center justify-center shrink-0 transition-all ${
                    isSelected
                      ? 'border-primary bg-primary'
                      : 'border-gray-300'
                  }`}
                >
                  {isSelected && <Check className="w-4 h-4 text-white" strokeWidth={3} />}
                </div>
              ) : (
                <div
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 transition-all ${
                    isSelected
                      ? 'border-primary'
                      : 'border-gray-300'
                  }`}
                >
                  {isSelected && <div className="w-3 h-3 rounded-full bg-primary" />}
                </div>
              )}
              <span className={`font-medium ${isSelected ? 'text-gray-900' : 'text-gray-700'}`}>
                {option.label}
              </span>
            </button>
          )
        })}
      </div>

      {/* Navigation */}
      <div className="flex items-center gap-4">
        {currentQuestion > 0 && (
          <button
            onClick={handleBack}
            className="flex items-center gap-2 px-5 py-3 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        )}
        <button
          onClick={handleContinue}
          disabled={!canContinue()}
          className={`flex-1 px-6 py-3.5 rounded-full font-semibold transition-colors flex items-center justify-center gap-2 ${
            canContinue()
              ? 'bg-primary text-white hover:bg-orange-600 shadow-lg shadow-orange-500/25'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          {isLastQuestion ? 'See My Profile' : 'Continue'}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
