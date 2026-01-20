'use client'

import { useState } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
import { getSupabase } from '@/lib/supabase'

type WaitlistFormProps = {
  onSuccess: (waitlistId: string) => void
}

export function WaitlistForm({ onSuccess }: WaitlistFormProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const { data, error: insertError } = await getSupabase()
        .from('waitlist')
        .insert({ name, email })
        .select('id')
        .single()

      if (insertError) {
        if (insertError.code === '23505') {
          setError('This email is already on the waitlist!')
        } else {
          setError('Something went wrong. Please try again.')
        }
        return
      }

      onSuccess(data.id)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="p-6 md:p-5 lg:p-8">
      <div className="text-center mb-6 md:mb-4 lg:mb-6">
        <h2 className="text-3xl md:text-xl lg:text-3xl font-bold text-black mb-3 md:mb-2">
          Join the waitlist for smarter job matching
        </h2>
        <p className="text-base md:text-xs lg:text-sm text-gray-600">
          Be among the first to access a job search that prioritizes fit, signal, and honesty.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 md:space-y-3">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Tell us your name..."
          required
          className="w-full px-4 py-3.5 md:py-2.5 lg:py-3 rounded-lg border border-gray-200 bg-white text-black text-base md:text-sm lg:text-base placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all"
        />
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your email address..."
          required
          className="w-full px-4 py-3.5 md:py-2.5 lg:py-3 rounded-lg border border-gray-200 bg-white text-black text-base md:text-sm lg:text-base placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent transition-all"
        />

        {error && (
          <p className="text-red-500 text-sm text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-[#FF4500] hover:bg-[#E63E00] text-white font-semibold py-3.5 md:py-2.5 lg:py-3 px-6 rounded-lg flex items-center justify-center gap-2 text-base md:text-sm lg:text-base transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <>
              Get early access
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </form>

      <p className="text-center text-sm md:text-xs lg:text-sm text-gray-500 mt-5 md:mt-4">
        By clicking "Get early access," you agree to our{' '}
        <a href="#" className="text-[#FF4500] hover:underline">Privacy Policy</a>
        {' '}and{' '}
        <a href="#" className="text-[#FF4500] hover:underline">Terms of Use</a>
      </p>
    </div>
  )
}
