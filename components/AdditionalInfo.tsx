'use client'

import { useState, useEffect } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
import confetti from 'canvas-confetti'
import { supabase } from '@/lib/supabase'
import { TECH_FIELDS, SENIORITY_LEVELS, COUNTRIES, WORK_TYPES, ROLE_TYPES } from '@/lib/data'

type AdditionalInfoProps = {
  waitlistId: string
  onComplete: () => void
}

export function AdditionalInfo({ waitlistId, onComplete }: AdditionalInfoProps) {
  const [field, setField] = useState('')
  const [seniority, setSeniority] = useState('')
  const [expectedPay, setExpectedPay] = useState('')
  const [country, setCountry] = useState('')
  const [workType, setWorkType] = useState<string[]>([])
  const [roleType, setRoleType] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    // Fire confetti on mount
    const duration = 3000
    const end = Date.now() + duration

    const colors = ['#FF4500', '#000000', '#FFFFFF']

    const frame = () => {
      confetti({
        particleCount: 3,
        angle: 60,
        spread: 55,
        origin: { x: 0, y: 0.8 },
        colors,
      })
      confetti({
        particleCount: 3,
        angle: 120,
        spread: 55,
        origin: { x: 1, y: 0.8 },
        colors,
      })

      if (Date.now() < end) {
        requestAnimationFrame(frame)
      }
    }

    frame()
  }, [])

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await supabase.from('waitlist_details').insert({
        waitlist_id: waitlistId,
        field,
        seniority,
        expected_pay: expectedPay ? parseInt(expectedPay) : null,
        country,
        work_type: workType,
        role_type: roleType,
      })

      onComplete()
    } catch {
      // Still complete even if details fail to save
      onComplete()
    }
  }

  const handleSkip = () => {
    onComplete()
  }

  return (
    <div className="bg-gray-50 rounded-2xl p-8 md:p-10">
      <div className="text-center mb-8">
        <div className="text-5xl mb-4">🎉</div>
        <h2 className="text-2xl md:text-3xl font-bold text-black mb-3">
          You're on the list!
        </h2>
        <p className="text-gray-600">
          Help us match you better by sharing a few more details. This is optional but helps us prioritize your profile.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-black mb-2">
            What field are you working in?
          </label>
          <select
            value={field}
            onChange={(e) => setField(e.target.value)}
            className="w-full px-4 py-3 rounded-lg border border-gray-200 bg-white text-black focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all"
          >
            <option value="">Select your field...</option>
            {TECH_FIELDS.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-black mb-2">
            What level of seniority?
          </label>
          <select
            value={seniority}
            onChange={(e) => setSeniority(e.target.value)}
            className="w-full px-4 py-3 rounded-lg border border-gray-200 bg-white text-black focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all"
          >
            <option value="">Select your level...</option>
            {SENIORITY_LEVELS.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-black mb-2">
            What's your expected annual pay (pre-tax)?
          </label>
          <div className="relative">
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

        <div>
          <label className="block text-sm font-medium text-black mb-2">
            Where are you located?
          </label>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="w-full px-4 py-3 rounded-lg border border-gray-200 bg-white text-black focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all"
          >
            <option value="">Select your country...</option>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-black mb-2">
            Are you looking for remote or onsite?
          </label>
          <div className="flex flex-wrap gap-3">
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

        <div>
          <label className="block text-sm font-medium text-black mb-2">
            Are you looking for permanent or temporary roles?
          </label>
          <div className="flex flex-wrap gap-3">
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

        <div className="flex flex-col gap-3 pt-4">
          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-[#FF4500] hover:bg-[#E63E00] text-white font-semibold py-3 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                Continue
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleSkip}
            className="w-full text-gray-500 hover:text-black font-medium py-2 transition-colors"
          >
            Skip for now
          </button>
        </div>
      </form>
    </div>
  )
}
