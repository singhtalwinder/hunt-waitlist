'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Check, X, ArrowRight, ChevronDown, Loader2, EyeOff } from 'lucide-react'
import { useState, useCallback } from 'react'
import { getSupabase } from '@/lib/supabase'
import { AdditionalInfo } from '@/components/AdditionalInfo'
import { ThankYou } from '@/components/ThankYou'

type Step = 'landing' | 'additional' | 'complete'

export default function Home() {
  const [step, setStep] = useState<Step>('landing')
  const [waitlistId, setWaitlistId] = useState<string>('')
  const [progress, setProgress] = useState({ current: 0, total: 6 })
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleProgress = useCallback((current: number, total: number) => {
    setProgress({ current, total })
  }, [])

  const handleAdditionalComplete = () => {
    setStep('complete')
  }

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
        console.error('Supabase error:', insertError)
        if (insertError.code === '23505') {
          setError('This email is already on the waitlist!')
        } else {
          setError(`Error: ${insertError.message || 'Something went wrong. Please try again.'}`)
        }
        return
      }

      setWaitlistId(data.id)
      setStep('additional')
    } catch (err) {
      console.error('Waitlist submission error:', err)
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  // Show the additional info or thank you flow
  if (step !== 'landing') {
    return (
      <div className="min-h-screen bg-white flex flex-col">
        {/* Header */}
        <header className="w-full py-5 px-6 md:px-12 lg:px-20 shrink-0 border-b border-gray-200">
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
        <div className="flex-1 max-w-7xl mx-auto px-6 md:px-10 lg:px-12 py-8 md:py-6 lg:py-8 w-full flex items-center justify-center">
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

        {/* Progress indicator - shown during questions */}
        {step === 'additional' && progress.current > 0 && (
          <div className="w-full px-6 md:px-8 lg:px-12 pb-4">
            <div className="max-w-md mx-auto">
              <div className="text-sm text-gray-500 text-center mb-2">
                Question {progress.current} of {progress.total}
              </div>
              <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-300"
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
              <Link href="/privacy" className="hover:text-black transition-colors">Privacy Policy</Link>
              <Link href="/terms" className="hover:text-black transition-colors">Terms of Use</Link>
            </div>
          </div>
        </footer>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="w-full py-5 px-6 md:px-12 lg:px-20 relative z-50 border-b border-gray-100">
        <nav className="max-w-7xl mx-auto flex items-center justify-between relative">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 flex-shrink-0">
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

          {/* Navigation Links - Centered */}
          <div className="hidden md:flex items-center gap-8 absolute left-1/2 -translate-x-1/2">
            <Link href="#how-it-works" className="text-sm font-medium text-gray-600 hover:text-black transition-colors">
              How It Works
            </Link>
            <Link href="#compare" className="text-sm font-medium text-gray-600 hover:text-black transition-colors">
              Compare
            </Link>
            <Link href="#faq" className="text-sm font-medium text-gray-600 hover:text-black transition-colors">
              FAQ
            </Link>
          </div>

          {/* Join Waitlist Button */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <a 
              href="#waitlist-form" 
              className="px-5 py-2.5 bg-black text-white text-sm font-medium rounded-full hover:bg-gray-800 transition-colors shadow-lg shadow-black/10"
            >
              Join Waitlist
            </a>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <section className="relative pt-16 pb-20 md:pt-24 md:pb-28 bg-gradient-to-b from-orange-50/30 to-white">
        <div className="max-w-4xl mx-auto px-6 md:px-12 text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary rounded-full shadow-sm mb-8">
            <span className="text-sm font-medium text-white">Stop Applying Blind</span>
          </div>

          {/* Hero Text */}
          <h1 className="font-hunt text-4xl md:text-5xl lg:text-6xl font-bold text-black leading-tight tracking-tight mb-6">
            Apply Only to Jobs You're Actually Likely to Get
          </h1>
          
          <p className="text-lg md:text-xl text-gray-600 max-w-2xl mx-auto leading-relaxed mb-8">
            Hunt tells you which jobs are worth your time — and which ones aren't.
            <br className="hidden md:block" />
            No keyword spam. No spray‑and‑pray. Just a short list of roles where you genuinely fit.
          </p>

          {/* Trust Points */}
          <div className="flex flex-wrap justify-center gap-4 md:gap-6 mb-10">
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span>Curated from real company sites</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span>Matched by context, not buzzwords</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-700">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span>Built to reduce rejection, not increase clicks</span>
            </div>
          </div>

          {/* Waitlist Form */}
          <form id="waitlist-form" onSubmit={handleSubmit} className="max-w-sm mx-auto space-y-3">
            <div className="flex flex-col gap-3">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
                className="flex-1 px-4 py-3 rounded-full border border-gray-200 bg-white text-black text-base placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Your email"
                required
                className="flex-1 px-4 py-3 rounded-full border border-gray-200 bg-white text-black text-base placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
            </div>
            
            {error && (
              <p className="text-red-500 text-sm text-center">{error}</p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full px-8 py-3.5 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  Join the Waitlist
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>

            <p className="text-center text-xs text-gray-500">
              By joining, you agree to our{' '}
              <Link href="/privacy" className="text-primary hover:underline">Privacy Policy</Link>
              {' '}and{' '}
              <Link href="/terms" className="text-primary hover:underline">Terms of Use</Link>
            </p>
          </form>
        </div>
      </section>

      {/* Sub-Hero Trust Reframe */}
      <section className="py-16 md:py-20 bg-white border-t border-gray-100">
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center">
          <p className="text-xl md:text-2xl text-gray-700 leading-relaxed mb-4">
            Most job seekers don't fail because they're unqualified.
            <br className="hidden md:block" />
            <span className="font-semibold text-black">They fail because they apply to the wrong jobs.</span>
          </p>
          <p className="text-lg text-primary font-medium">
            <span className="font-hunt">hunt<span className="text-primary">.</span></span> exists to fix that.
          </p>
        </div>
      </section>

      {/* Social Proof / Weekly Shortlist */}
      <section className="py-16 md:py-24 bg-gray-50 border-t border-gray-100">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <div className="text-center mb-12">
            <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
              Your Weekly Shortlist
            </h2>
          </div>

          <div className="max-w-lg mx-auto space-y-4 mb-8">
            {/* Match 1 */}
            <div className="bg-white p-4 rounded-xl border border-green-200 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center overflow-hidden">
                  <Image src="/spotify.png" width={28} height={28} alt="Spotify" className="object-contain" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Product Designer</div>
                  <div className="text-sm text-gray-500">Spotify</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                <span className="text-green-700 font-bold">95% Match</span>
              </div>
            </div>

            {/* Match 2 */}
            <div className="bg-white p-4 rounded-xl border border-green-200 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center overflow-hidden">
                  <Image src="/dropboxlogo.png" width={28} height={28} alt="Dropbox" className="object-contain" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Frontend Engineer</div>
                  <div className="text-sm text-gray-500">Dropbox</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                <span className="text-green-700 font-bold">92% Match</span>
              </div>
            </div>

            {/* Match 3 */}
            <div className="bg-white p-4 rounded-xl border border-green-200 shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center overflow-hidden">
                  <Image src="/databrickslogo.png" width={28} height={28} alt="Databricks" className="object-contain" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Content Writer</div>
                  <div className="text-sm text-gray-500">Databricks</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                <span className="text-green-700 font-bold">94% Match</span>
              </div>
            </div>

            {/* Hidden roles indicator */}
            <div className="flex items-center justify-center gap-2 pt-4">
              <div className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-full">
                <EyeOff className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium text-gray-600">1,402 irrelevant roles hidden</span>
              </div>
            </div>
          </div>

          <div className="text-center">
            <p className="text-lg text-gray-600">
              You don't need more jobs.
              <br />
              <span className="font-semibold text-black">You need fewer, better ones.</span>
            </p>
          </div>
        </div>
      </section>

      {/* Know Before You Apply */}
      <section className="py-16 md:py-24 bg-white border-t border-gray-100">
        <div className="max-w-5xl mx-auto px-6 md:px-12">
          <div className="text-center mb-12">
            <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold text-black mb-4">
              Know Before You Apply
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Every role on Hunt answers one question clearly:
              <br />
              <span className="font-semibold text-black">"Is this a good use of my application?"</span>
            </p>
          </div>

          <div className="max-w-3xl mx-auto">
            <p className="text-center text-gray-600 mb-8">For each job, we show:</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-50 p-5 rounded-xl border border-gray-100">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                  </div>
                  <span className="font-medium text-gray-900">Why you matched</span>
                </div>
              </div>
              
              <div className="bg-gray-50 p-5 rounded-xl border border-gray-100">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                  </div>
                  <span className="font-medium text-gray-900">Where you're strong</span>
                </div>
              </div>
              
              <div className="bg-gray-50 p-5 rounded-xl border border-gray-100">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                  </div>
                  <span className="font-medium text-gray-900">Where you might be stretching</span>
                </div>
              </div>
              
              <div className="bg-gray-50 p-5 rounded-xl border border-gray-100">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                  </div>
                  <span className="font-medium text-gray-900">How close this is to a real interview</span>
                </div>
              </div>
            </div>

            <p className="text-center text-gray-600 mt-8 font-medium">
              No black box. No guessing.
            </p>
          </div>
        </div>
      </section>

      {/* How Hunt Is Different - Comparison */}
      <section id="compare" className="py-16 md:py-24 bg-gray-50 border-t border-gray-100">
        <div className="max-w-5xl mx-auto px-6 md:px-12">
          <div className="text-center mb-12">
            <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold text-black mb-4">
              How Hunt Is Different
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8 max-w-4xl mx-auto">
            {/* Traditional Job Boards */}
            <div className="bg-white rounded-2xl p-6 md:p-8 border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-500 mb-6">Traditional Job Boards</h3>
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <X className="w-5 h-5 text-red-500 shrink-0" strokeWidth={2.5} />
                  <span className="text-gray-600">Maximize listings</span>
                </div>
                <div className="flex items-center gap-3">
                  <X className="w-5 h-5 text-red-500 shrink-0" strokeWidth={2.5} />
                  <span className="text-gray-600">Reward paid employers</span>
                </div>
                <div className="flex items-center gap-3">
                  <X className="w-5 h-5 text-red-500 shrink-0" strokeWidth={2.5} />
                  <span className="text-gray-600">Match on keywords</span>
                </div>
                <div className="flex items-center gap-3">
                  <X className="w-5 h-5 text-red-500 shrink-0" strokeWidth={2.5} />
                  <span className="text-gray-600">Push you to apply more</span>
                </div>
              </div>
            </div>

            {/* Hunt */}
            <div className="bg-white rounded-2xl p-6 md:p-8 border-2 border-primary shadow-lg shadow-orange-100">
              <h3 className="text-lg font-semibold text-primary mb-6">
                <span className="font-hunt">hunt<span className="text-primary">.</span></span>
              </h3>
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                  <span className="text-gray-900 font-medium">Minimize wasted applications</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                  <span className="text-gray-900 font-medium">Prioritize candidate fit</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                  <span className="text-gray-900 font-medium">Match on experience + context</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                  <span className="text-gray-900 font-medium">Tell you when not to apply</span>
                </div>
              </div>
            </div>
          </div>

          <p className="text-center text-gray-600 mt-10 text-lg">
            Our goal isn't engagement.
            <br />
            <span className="font-semibold text-black">Our goal is getting you hired.</span>
          </p>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-16 md:py-24 bg-white border-t border-gray-100">
        <div className="max-w-5xl mx-auto px-6 md:px-12">
          <div className="text-center mb-16">
            <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold text-black mb-4">
              How It Works
            </h2>
          </div>

          <div className="space-y-16 md:space-y-24">
            {/* Step 1 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">
              <div className="order-2 md:order-1">
                <div className="bg-gray-50 rounded-2xl p-6 md:p-8 border border-gray-100">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="flex items-center justify-center w-10 h-10">
                      <Image src="/paper.png" width={32} height={32} alt="Hunt" />
                    </div>
                    <ArrowRight className="w-5 h-5 text-gray-400" />
                    <div className="flex gap-2">
                      <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center p-1.5">
                        <Image src="/spotify.png" width={24} height={24} alt="Spotify" className="object-contain" />
                      </div>
                      <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center p-1.5">
                        <Image src="/dropboxlogo.png" width={24} height={24} alt="Dropbox" className="object-contain" />
                      </div>
                      <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center p-1.5">
                        <Image src="/stripelogo.png" width={24} height={24} alt="Stripe" className="object-contain" />
                      </div>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-green-700">
                      <Check className="w-4 h-4" strokeWidth={3} />
                      <span>Roles before they're widely posted</span>
                    </div>
                    <div className="flex items-center gap-2 text-green-700">
                      <Check className="w-4 h-4" strokeWidth={3} />
                      <span>Jobs many boards never see</span>
                    </div>
                    <div className="flex items-center gap-2 text-green-700">
                      <Check className="w-4 h-4" strokeWidth={3} />
                      <span>Zero fake or expired listings</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="order-1 md:order-2">
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mb-4">1</div>
                <h3 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-4">
                  We Find Jobs First
                </h3>
                <p className="text-gray-600 leading-relaxed">
                  We monitor thousands of company career pages and ATS systems every day — not LinkedIn or Indeed.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">
              <div>
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mb-4">2</div>
                <h3 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-4">
                  We Understand You
                </h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  Upload your resume and Hunt builds a profile like a great recruiter would.
                </p>
                <p className="text-gray-600 leading-relaxed mb-4">
                  We infer:
                </p>
                <ul className="space-y-2 text-gray-600">
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>Domain expertise</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>Seniority level</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>Industry context</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>Skills you implied, not just listed</span>
                  </li>
                </ul>
              </div>
              <div>
                <div className="bg-gray-50 rounded-2xl p-6 md:p-8 border border-gray-100">
                  <div className="bg-white rounded-xl p-4 border border-gray-200 mb-4">
                    <div className="text-xs text-gray-500 mb-1">Resume says:</div>
                    <div className="font-medium text-gray-900">"Operations at DoorDash"</div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-400 mx-auto rotate-90 my-2" />
                  <div className="bg-green-50 rounded-xl p-4 border border-green-200">
                    <div className="text-xs text-green-700 mb-1">Hunt understands:</div>
                    <div className="font-medium text-green-800">Logistics & Scaling — not "Operations at a bank"</div>
                  </div>
                  <p className="text-center text-sm text-gray-500 mt-4">
                    Hunt knows the difference.
                  </p>
                </div>
              </div>
            </div>

            {/* Step 3 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">
              <div className="order-2 md:order-1">
                <div className="bg-gray-50 rounded-2xl p-6 md:p-8 border border-gray-100">
                  <div className="space-y-3">
                    <div className="bg-white p-3 rounded-lg border border-green-200 flex items-center justify-between">
                      <span className="font-medium text-gray-900 text-sm">Senior Engineer at Stripe</span>
                      <span className="text-green-700 font-bold text-sm">98%</span>
                    </div>
                    <div className="bg-white p-3 rounded-lg border border-green-200 flex items-center justify-between">
                      <span className="font-medium text-gray-900 text-sm">Product Lead at Airbnb</span>
                      <span className="text-green-700 font-bold text-sm">92%</span>
                    </div>
                    <div className="bg-gray-100 p-3 rounded-lg flex items-center justify-center gap-2 text-gray-500 text-sm">
                      <EyeOff className="w-4 h-4" />
                      <span>Zero filler, zero noise</span>
                    </div>
                  </div>
                  <p className="text-center text-sm text-gray-600 mt-4 font-medium">
                    If there are no good fits, we tell you.
                    <br />
                    <span className="text-primary">That's a feature — not a bug.</span>
                  </p>
                </div>
              </div>
              <div className="order-1 md:order-2">
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mb-4">3</div>
                <h3 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-4">
                  We Show Only Strong Matches
                </h3>
                <p className="text-gray-600 leading-relaxed mb-4">
                  You'll see:
                </p>
                <ul className="space-y-2 text-gray-600">
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>A short list of roles you're qualified for</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>A match score with reasoning</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                    <span>Zero filler, zero noise</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Match Breakdown Visual */}
      <section className="py-16 md:py-24 bg-gray-50 border-t border-gray-100">
        <div className="max-w-3xl mx-auto px-6 md:px-12">
          <div className="text-center mb-12">
            <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
              See Exactly Why You Matched
            </h2>
            <p className="text-lg text-gray-600 max-w-xl mx-auto">
              No black box. Every match comes with a breakdown so you know it's real before you apply.
            </p>
          </div>

          <div className="bg-white rounded-2xl p-8 md:p-10 border border-gray-200 shadow-lg max-w-md mx-auto">
            <div className="flex items-center justify-between mb-6">
              <span className="text-lg font-semibold text-gray-900">Match Score</span>
              <span className="text-3xl font-bold text-green-600">94%</span>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                  <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                </div>
                <span className="text-gray-900 font-medium">Domain Expertise</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                  <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                </div>
                <span className="text-gray-900 font-medium">Seniority Match</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                  <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                </div>
                <span className="text-gray-900 font-medium">Industry Context</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                  <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
                </div>
                <span className="text-gray-900 font-medium">Team & Company Stage Fit</span>
              </div>
            </div>
            
            <div className="h-2 w-full bg-gray-100 rounded-full mt-6 overflow-hidden">
              <div className="h-full bg-green-500 w-[94%] rounded-full"></div>
            </div>
          </div>
          
          <p className="text-center text-gray-600 mt-8">
            You always know why a job is shown.
          </p>
        </div>
      </section>

      {/* Who Hunt Is For */}
      <section className="py-16 md:py-24 bg-white border-t border-gray-100">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <div className="text-center mb-12">
            <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
              Who Hunt Is For
            </h2>
          </div>

          <div className="max-w-2xl mx-auto">
            <p className="text-lg text-gray-600 mb-6">
              Hunt is built for:
            </p>
            <ul className="space-y-3 mb-8">
              <li className="flex items-center gap-3 text-lg">
                <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                <span className="text-gray-900 font-medium">Mid–senior tech professionals (3-10 years of experience)</span>
              </li>
              <li className="flex items-center gap-3 text-lg">
                <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                <span className="text-gray-900 font-medium">Engineers, designers, PMs, data, ops</span>
              </li>
              <li className="flex items-center gap-3 text-lg">
                <Check className="w-5 h-5 text-green-600 shrink-0" strokeWidth={3} />
                <span className="text-gray-900 font-medium">People tired of applying to 100+ jobs with no signal</span>
              </li>
            </ul>
            <p className="text-gray-600">
              If you're early‑career or just exploring, you can still use Hunt —
              <br />
              but our real strength is <span className="font-semibold text-black">precision over volume</span>.
            </p>
          </div>
        </div>
      </section>

      {/* Why We Built Hunt */}
      <section className="py-16 md:py-24 bg-gray-50 border-t border-gray-100">
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center">
          <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-6">
            Why We Built Hunt
          </h2>
          <p className="text-lg text-gray-600 mb-8 leading-relaxed">
            We built Hunt because job search became a numbers game —
            <br />
            and candidates are losing.
          </p>
          <p className="text-xl font-medium text-gray-900 mb-8">
            More applications ≠ better outcomes.
            <br />
            <span className="text-primary">Better decisions do.</span>
          </p>
          <p className="text-gray-600 mb-2">Hunt helps you:</p>
          <ul className="inline-block text-left space-y-2 text-gray-700">
            <li className="flex items-center gap-2">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span>Apply with confidence</span>
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span>Spend less time searching</span>
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span>Focus only on roles that make sense for your background</span>
            </li>
          </ul>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-16 md:py-24 bg-white border-t border-gray-100">
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center">
          <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
            Free for Job Seekers (For Now)
          </h2>
          <p className="text-lg text-gray-600 mb-8">
            Hunt is currently free while we scale and learn.
          </p>
          <div className="max-w-md mx-auto text-left mb-8">
            <p className="text-gray-600 mb-4">Long‑term, we believe:</p>
            <ul className="space-y-2 text-gray-700">
              <li className="flex items-start gap-2">
                <Check className="w-4 h-4 text-green-600 mt-1 shrink-0" strokeWidth={3} />
                <span>Job seekers shouldn't pay to see jobs</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="w-4 h-4 text-green-600 mt-1 shrink-0" strokeWidth={3} />
                <span>But they should have access to tools that help them choose wisely</span>
              </li>
            </ul>
          </div>
          <p className="text-gray-600 mb-8">
            Early users help shape what comes next.
          </p>
          <a 
            href="#waitlist-form" 
            className="inline-flex items-center gap-2 px-8 py-3.5 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25"
          >
            Join the Waitlist
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>

      {/* FAQ Section */}
      <FAQSection />

      {/* Final CTA */}
      <section className="py-16 md:py-24 bg-black text-white">
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center">
          <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold mb-4">
            Stop Guessing.
            <br />
            Start Applying With Confidence.
          </h2>
          <p className="text-lg text-gray-400 mb-8">
            Join Hunt and only apply where you actually stand a chance.
          </p>
          <a 
            href="#waitlist-form" 
            className="inline-flex items-center gap-2 px-8 py-4 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25"
          >
            Join the Waitlist
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-12">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-20">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <Link href="/" className="flex items-center gap-2">
              <Image
                src="/paper.png"
                alt="Hunt"
                width={24}
                height={24}
              />
              <span className="text-lg font-bold text-black font-hunt">
                hunt<span className="text-primary">.</span>
              </span>
            </Link>
            
            <div className="flex items-center gap-6 text-sm text-gray-600">
              <Link href="/privacy" className="hover:text-primary transition-colors">
                Privacy Policy
              </Link>
              <Link href="/terms" className="hover:text-primary transition-colors">
                Terms of Service
              </Link>
              <Link href="https://x.com/talwinderbuilds" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-primary transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </Link>
            </div>
            
            <p className="text-sm text-gray-500">
              © {new Date().getFullYear()} Hunt. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

const faqs = [
  {
    question: "Is Hunt just another job board?",
    answer: "No. Hunt is a decision engine. We hide more jobs than we show."
  },
  {
    question: "Why not just use LinkedIn?",
    answer: "LinkedIn shows what's popular and paid for. Hunt shows what fits you."
  },
  {
    question: "How accurate are the matches?",
    answer: "We're conservative by design. If confidence is low, we don't show the job."
  },
  {
    question: "Do you guarantee interviews?",
    answer: "No — but we dramatically reduce wasted applications and false hope."
  }
]

function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <section id="faq" className="py-16 md:py-24 bg-gray-50 border-t border-gray-100">
      <div className="max-w-3xl mx-auto px-6 md:px-12">
        <div className="text-center mb-12">
          <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
            Frequently Asked Questions
          </h2>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, index) => (
            <div 
              key={index}
              className="bg-white rounded-xl border border-gray-200 overflow-hidden transition-all duration-300 hover:border-gray-300"
            >
              <button
                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                className="w-full px-5 py-4 flex items-center justify-between text-left"
              >
                <span className="font-medium text-gray-900 pr-4">{faq.question}</span>
                <ChevronDown 
                  className={`w-5 h-5 text-gray-500 shrink-0 transition-transform duration-300 ${
                    openIndex === index ? 'rotate-180' : ''
                  }`} 
                />
              </button>
              <div 
                className={`px-5 overflow-hidden transition-all duration-300 ${
                  openIndex === index ? 'pb-4 max-h-96' : 'max-h-0'
                }`}
              >
                <p className="text-gray-600 leading-relaxed">{faq.answer}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
