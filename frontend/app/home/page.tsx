'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Check, X, Search, FileText, BarChart3, Zap, Brain, Target, Sparkles, ArrowRight, Globe, Filter, ChevronDown, Loader2 } from 'lucide-react'
import { ComparisonTable } from '@/components/ComparisonTable'
import { useState, useCallback } from 'react'
import { getSupabase } from '@/lib/supabase'
import { AdditionalInfo } from '@/components/AdditionalInfo'
import { ThankYou } from '@/components/ThankYou'

type Step = 'landing' | 'additional' | 'complete'

export default function HomePage() {
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
            <Link href="/home" className="flex items-center gap-2">
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
    <div className="min-h-screen bg-white relative overflow-hidden">
      <div className="relative z-20">
        {/* Background Grid - 6 boxes layout */}
        <div className="absolute inset-0 pointer-events-none z-0">
          {/* Vertical lines at 10% and 90% */}
          <div className="absolute top-0 bottom-0 left-[10%] w-px bg-gray-200" />
          <div className="absolute top-0 bottom-0 right-[10%] w-px bg-gray-200" />
          
          {/* Horizontal line at 50% */}
          <div className="absolute left-0 right-0 top-1/2 h-px bg-gray-200" />
          
          {/* Horizontal line at bottom */}
          <div className="absolute left-0 right-0 bottom-0 h-px bg-gray-200" />
          
          {/* Intersection Boxes - Middle */}
          <div className="absolute left-[10%] top-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-white border border-gray-300" />
          <div className="absolute right-[10%] top-1/2 translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-white border border-gray-300" />

          {/* Intersection Boxes - Bottom */}
          <div className="absolute left-[10%] bottom-0 -translate-x-1/2 translate-y-1/2 w-1.5 h-1.5 bg-white border border-gray-300" />
          <div className="absolute right-[10%] bottom-0 translate-x-1/2 translate-y-1/2 w-1.5 h-1.5 bg-white border border-gray-300" />
        </div>
        
        {/* Top Gradient Fade - White top fading to transparent/bottom */}
        <div className="absolute top-0 left-0 right-0 h-[500px] bg-gradient-to-b from-white via-white/80 to-transparent pointer-events-none z-0" />

        {/* Arch Effect */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[140%] h-[500px] border-b border-gray-100 rounded-[100%] bg-gradient-to-b from-orange-50/20 to-transparent -translate-y-[45%] pointer-events-none z-0" />

        {/* Header */}
        <header className="w-full py-5 px-6 md:px-12 lg:px-20 relative z-50">
        <nav className="max-w-7xl mx-auto flex items-center justify-between relative">
          {/* Logo */}
          <Link href="/home" className="flex items-center gap-2 flex-shrink-0">
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
            <Link href="#features" className="text-sm font-medium text-gray-600 hover:text-black transition-colors">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm font-medium text-gray-600 hover:text-black transition-colors">
              How It Works
            </Link>
            <Link href="#compare" className="text-sm font-medium text-gray-600 hover:text-black transition-colors">
              Compare
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
      <section className="relative pt-12 pb-24 md:pt-20 md:pb-32 z-20">
        <div className="relative max-w-7xl mx-auto px-6 md:px-12 lg:px-20">
          {/* Sparkle icon */}
          <div className="flex justify-center mb-6">
            <div className="w-12 h-12 rounded-xl bg-white shadow-sm border border-gray-100 flex items-center justify-center">
              <Image 
                src="/paper.png" 
                alt="Hunt Logo" 
                width={28} 
                height={28} 
                className="object-contain"
              />
            </div>
          </div>

          {/* Hero Text */}
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="font-hunt text-4xl md:text-5xl lg:text-7xl font-bold text-black leading-tight tracking-tight">
              The Job Platform That
              <br />
              Works for Candidates
            </h1>
            
            <p className="mt-6 md:mt-8 text-lg text-gray-600 max-w-2xl mx-auto leading-relaxed">
              Unlike traditional boards, we don't sell placement. Every job is shown because it fits you, not because someone paid.
            </p>

            {/* Waitlist Form */}
            <form id="waitlist-form" onSubmit={handleSubmit} className="mt-8 md:mt-10 max-w-md mx-auto space-y-3">
              <div className="flex flex-col sm:flex-row gap-3">
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
                className="w-full sm:w-auto px-8 py-3.5 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mx-auto"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Join Waitlist
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

          {/* Hero Visual - Phone Mockup with floating cards */}
          <div className="mt-20 relative h-[600px] flex justify-center perspective-1000">
            
            {/* Phone Container */}
            <div className="relative z-40 transform scale-90 md:scale-100 transition-transform duration-500">
              <div className="bg-gray-900 rounded-[3.2rem] p-1.5 shadow-2xl relative">
                {/* Screen Container */}
                <div className="bg-gray-50 rounded-[2.9rem] w-[300px] h-[620px] relative">
                  
                  {/* Pop-out Profile Card - Positioned absolute to break out of bounds */}
                  <div className="absolute top-[110px] left-1/2 -translate-x-1/2 w-[115%] z-50">
                    <div className="bg-white rounded-2xl p-4 shadow-xl border-2 border-primary">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-white shadow-sm shrink-0">
                          <Image src="/useravatar.jpg" width={48} height={48} alt="Profile" className="bg-gray-100 object-cover" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-gray-900 text-base truncate">James Mitchell</p>
                          <p className="text-sm text-gray-500 flex items-center gap-1.5 truncate">
                            <span className="flex items-center justify-center w-4 h-4 rounded-full bg-primary text-white text-[10px] shrink-0">✓</span> Verified Profile
                          </p>
                        </div>
                      </div>
                      
                      <div className="mt-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-2xl font-bold text-gray-900">95%</span>
                          <span className="text-xs font-medium text-gray-500">Match Score</span>
                        </div>
                        <div className="flex gap-1 h-1.5 w-full">
                          {[...Array(6)].map((_, i) => (
                            <div key={i} className={`flex-1 rounded-full ${i < 5 ? 'bg-green-500' : 'bg-gray-200'}`} />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Inner Screen Content (Clipped) */}
                  <div className="h-full w-full overflow-hidden rounded-[2.9rem] relative z-10 bg-gray-50 flex flex-col">
                    
                    {/* Dynamic Island */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 h-7 w-28 bg-black rounded-b-2xl z-30"></div>
                    
                    {/* Status Bar */}
                    <div className="px-6 pt-3 pb-2 flex items-center justify-between">
                      <span className="text-[10px] font-semibold pl-2">9:41</span>
                      <div className="flex items-center gap-1 pr-2">
                        <div className="w-6 h-3 border-[1.5px] border-black rounded-[3px] relative flex items-center p-0.5">
                          <div className="w-3/4 h-full bg-black rounded-sm"></div>
                          <div className="absolute -right-[3px] top-1/2 -translate-y-1/2 w-[2px] h-1.5 bg-black rounded-r-sm"></div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Main Content */}
                    <div className="px-4 pt-2 pb-6 flex-1 flex flex-col">
                      <div className="flex items-center justify-center gap-2 mb-4">
                        <Image src="/paper.png" width={24} height={24} alt="Hunt Logo" />
                        <p className="text-center font-hunt font-bold text-lg">hunt<span className="text-primary">.</span></p>
                      </div>
                      
                      {/* Spacer for Pop-out Card */}
                      <div className="h-[140px] w-full shrink-0"></div>

                      {/* Job listings */}
                      <div className="space-y-3 mt-4 overflow-y-auto no-scrollbar mask-gradient-bottom pb-4">
                        {/* Job 1 */}
                        <div className="bg-white p-3.5 rounded-xl shadow-sm border border-gray-100/50">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full overflow-hidden shrink-0">
                                <Image src="/Pinterest.svg.png" width={36} height={36} alt="Pinterest" className="object-cover" />
                              </div>
                              <div>
                                <p className="font-bold text-xs text-gray-900">UI/UX Designer</p>
                                <p className="text-[10px] text-gray-500">Pinterest</p>
                              </div>
                            </div>
                            <span className="text-gray-300 text-xs">•••</span>
                          </div>
                        </div>

                        {/* Job 2 */}
                        <div className="bg-white p-3.5 rounded-xl shadow-sm border border-gray-100/50">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full overflow-hidden shrink-0">
                                <Image src="/spotify.png" width={36} height={36} alt="Spotify" className="object-cover" />
                              </div>
                              <div>
                                <p className="font-bold text-xs text-gray-900">Product Designer</p>
                                <p className="text-[10px] text-gray-500">Spotify</p>
                              </div>
                            </div>
                            <span className="text-gray-300 text-xs">•••</span>
                          </div>
                        </div>

                        {/* Job 3 */}
                        <div className="bg-white p-3.5 rounded-xl shadow-sm border border-gray-100/50">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full overflow-hidden shrink-0">
                                <Image src="/github.png" width={36} height={36} alt="Github" className="object-cover" />
                              </div>
                              <div>
                                <p className="font-bold text-xs text-gray-900">UI Designer</p>
                                <p className="text-[10px] text-gray-500">Github</p>
                              </div>
                            </div>
                            <span className="text-gray-300 text-xs">•••</span>
                          </div>
                        </div>

                        {/* Job 4 */}
                        <div className="bg-white p-3.5 rounded-xl shadow-sm border border-gray-100/50">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full overflow-hidden shrink-0">
                                <Image src="/dropboxlogo.png" width={36} height={36} alt="Dropbox" className="object-cover" />
                              </div>
                              <div>
                                <p className="font-bold text-xs text-gray-900">Frontend Engineer</p>
                                <p className="text-[10px] text-gray-500">Dropbox</p>
                              </div>
                            </div>
                            <span className="text-gray-300 text-xs">•••</span>
                          </div>
                        </div>

                        {/* View More Button */}
                        <button className="w-full py-2.5 text-primary text-xs font-medium bg-primary/5 rounded-xl hover:bg-primary/10 transition-colors">
                           View more jobs
                        </button>
                      </div>
                    </div>
                    
                    {/* Home Indicator */}
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-32 h-1 bg-black/90 rounded-full z-30"></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Floating Cards Container - Two Columns Layout */}
            
            {/* Left Column - Top Card (Designer) */}
            <div className="hidden lg:block absolute top-[20%] left-[calc(50%-450px)] z-20">
              <div className="bg-white rounded-2xl shadow-xl p-4 w-[280px] border border-gray-100 backdrop-blur-sm">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg overflow-hidden shrink-0">
                    <Image src="/dropboxlogo.png" width={40} height={40} alt="Dropbox" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-bold text-gray-900 text-sm font-hunt truncate">Designer</p>
                    <p className="text-[10px] text-gray-500">Dropbox <span className="text-blue-500">✓</span></p>
                  </div>
                </div>
                <p className="text-[10px] text-gray-500 leading-relaxed mb-4">
                  Creative team as a UI/UX, in this role you'll design user-centric...
                </p>
                <button className="w-full py-2.5 bg-black text-white text-[10px] font-bold rounded-lg hover:bg-gray-800 transition-colors">
                  Apply now
                </button>
              </div>
            </div>

            {/* Left Column - Bottom Card (Content Writer) */}
            <div className="hidden lg:block absolute top-[55%] left-[calc(50%-450px)] z-20">
              <div className="bg-white rounded-2xl shadow-xl p-5 w-[280px] border border-gray-100">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl overflow-hidden shrink-0">
                    <Image src="/databrickslogo.png" width={40} height={40} alt="Databricks" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-bold text-gray-900 text-sm font-hunt">Content Writer</p>
                    <p className="text-[10px] text-gray-500">Databricks <span className="text-primary">✓</span></p>
                  </div>
                </div>
                <p className="text-[10px] text-gray-500 leading-relaxed mb-4">
                  We are looking for a talented Content Writer to join our dynamic team...
                </p>
                <button className="w-full py-2.5 bg-black text-white text-xs font-bold rounded-lg shadow-lg shadow-black/10">
                  Apply now
                </button>
              </div>
            </div>

            {/* Right Column - Top Card (Full Stack) */}
            <div className="hidden lg:block absolute top-[20%] right-[calc(50%-450px)] z-20">
              <div className="bg-white rounded-2xl shadow-xl p-5 w-[280px] border border-gray-100">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full overflow-hidden shrink-0">
                    <Image src="/mailchimplogo.png" width={40} height={40} alt="Mailchimp" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-bold text-gray-900 text-sm font-hunt">Full Stack Dev</p>
                    <p className="text-[10px] text-gray-500">Mailchimp <span className="text-blue-500">✓</span></p>
                  </div>
                </div>
                <p className="text-[10px] text-gray-500 leading-relaxed mb-4">
                  As a Fullstack Developer, you will be instrumental in crafting...
                </p>
                <button className="w-full py-2.5 bg-black text-white text-xs font-bold rounded-lg hover:bg-gray-800 transition-colors">
                  Apply now
                </button>
              </div>
            </div>

            {/* Right Column - Bottom Card (Customer Support) */}
            <div className="hidden lg:block absolute top-[55%] right-[calc(50%-450px)] z-20">
              <div className="bg-white rounded-2xl shadow-xl p-4 w-[280px] border border-gray-100 opacity-95">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-lg overflow-hidden shrink-0">
                    <Image src="/stripelogo.png" width={40} height={40} alt="Stripe" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-bold text-gray-900 text-sm font-hunt">Support</p>
                    <p className="text-[10px] text-gray-500">Stripe <span className="text-[#635BFF]">✓</span></p>
                  </div>
                </div>
                <p className="text-[10px] text-gray-500 leading-relaxed mb-4">
                  Join our team as a Customer Support specialist to help millions...
                </p>
                <button className="w-full py-2.5 bg-black text-white text-[10px] font-bold rounded-lg hover:bg-gray-800 transition-colors">
                  Apply now
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
      </div>

      {/* Stats Section */}
      <section className="relative z-10 py-16 border-b border-gray-100 bg-white">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-20">
          <div className="flex flex-col md:flex-row items-center justify-between gap-12">
            <div className="max-w-xl">
              <h2 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
                Fresh Jobs Added Daily,
                <br />
                Beyond LinkedIn & Indeed
              </h2>
              <p className="text-gray-600 text-lg">
                We discover opportunities directly from company career pages, surfacing jobs you won't find on traditional platforms.
              </p>
            </div>
            
            <div className="flex gap-12 md:gap-20">
              <div className="text-center">
                <div className="relative inline-block">
                  <span className="font-hunt text-4xl md:text-5xl font-bold text-black">4k+</span>
                  <div className="absolute -bottom-2 left-0 w-full h-1 bg-primary/20 rounded-full">
                    <div className="w-1/2 h-full bg-primary rounded-full"></div>
                  </div>
                </div>
                <p className="mt-4 text-sm text-gray-600 font-medium">Jobs Listed Every Day</p>
              </div>
              
              <div className="text-center">
                <div className="relative inline-block">
                  <span className="font-hunt text-4xl md:text-5xl font-bold text-black">2k+</span>
                  <div className="absolute -bottom-2 left-0 w-full h-1 bg-primary/20 rounded-full">
                    <div className="w-1/2 h-full bg-primary rounded-full"></div>
                  </div>
                </div>
                <p className="mt-4 text-sm text-gray-600 font-medium">Companies Added Every Day</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Headline Section */}
      <section id="features" className="py-24 bg-white">
        <div className="max-w-5xl mx-auto px-6 md:px-12">
          
          <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold text-black leading-tight mb-6 text-center">
            Job Matching That
            <br />
            Actually Understands You
          </h2>
          
          <p className="text-lg text-gray-600 max-w-2xl mx-auto text-center mb-16">
            LinkedIn sees "operations" on your resume and shows you insurance back-office roles when you've spent a decade in tech. Hunt reads resumes the way a great recruiter would.
          </p>

          {/* Three Differentiators Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
            {/* Card 1: Context */}
            <div className="group bg-gray-50 rounded-3xl p-6 md:p-8 hover:shadow-xl hover:shadow-gray-200/50 transition-all duration-500 border border-gray-100 overflow-hidden relative">
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-50/50 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-150 duration-700" />
              
              <div className="h-48 mb-6 relative flex items-center justify-center">
                <div className="flex gap-3 w-full max-w-[280px] justify-center items-end">
                  {/* DoorDash Column - Highlighted */}
                  <div className="flex-1 bg-white rounded-xl border-2 border-primary/20 shadow-md p-3 flex flex-col items-center gap-2 relative overflow-hidden transform group-hover:-translate-y-2 transition-transform duration-500 z-10 w-32">
                    {/* Highlight indicator */}
                    <div className="absolute top-0 inset-x-0 h-1 bg-[#FF3008]"></div>
                    
                    {/* Company */}
                    <div className="flex items-center gap-1.5 font-bold text-gray-900 text-xs mt-1">
                      <div className="w-2 h-2 rounded-full bg-[#FF3008]"></div> DoorDash
                    </div>
                    
                    {/* Role */}
                    <div className="w-full bg-gray-50 py-1.5 rounded text-center text-[10px] text-gray-500 font-medium">
                      Operations
                    </div>

                    <ArrowRight className="w-3 h-3 text-gray-300 rotate-90 my-0.5" />

                    {/* Meaning/Inference */}
                    <div className="w-full bg-green-50 py-2 rounded border border-green-100 text-center text-[10px] text-green-700 font-bold flex items-center justify-center gap-1">
                      <Check className="w-2.5 h-2.5" /> Logistics
                    </div>
                  </div>

                  {/* JP Morgan Column - Faded/Background */}
                  <div className="flex-1 bg-white rounded-xl border border-gray-100 p-3 flex flex-col items-center gap-2 opacity-70 scale-95 origin-bottom">
                    {/* Company */}
                    <div className="flex items-center gap-1.5 font-bold text-gray-900 text-xs mt-1">
                      <div className="w-2 h-2 rounded-full bg-[#0F4797]"></div> JP Morgan
                    </div>
                    
                    {/* Role */}
                    <div className="w-full bg-gray-50 py-1.5 rounded text-center text-[10px] text-gray-500 font-medium">
                      Operations
                    </div>

                    <ArrowRight className="w-3 h-3 text-gray-300 rotate-90 my-0.5" />

                    {/* Meaning/Inference */}
                    <div className="w-full bg-gray-50 py-2 rounded border border-gray-200 text-center text-[10px] text-gray-500 font-medium">
                      Back Office
                    </div>
                  </div>
                </div>
              </div>

              <h3 className="font-hunt text-xl font-bold text-black mb-3 group-hover:text-primary transition-colors">Context, Not Keywords</h3>
              <p className="text-gray-600 text-sm leading-relaxed">
                "Operations at DoorDash" means logistics and scaling — not the same as operations at a bank. Hunt understands the difference.
              </p>
            </div>

            {/* Card 2: Inference */}
            <div className="group bg-gray-50 rounded-3xl p-6 md:p-8 hover:shadow-xl hover:shadow-gray-200/50 transition-all duration-500 border border-gray-100 overflow-hidden relative">
              <div className="absolute top-0 right-0 w-32 h-32 bg-purple-50/50 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-150 duration-700" />
              
              <div className="h-48 mb-6 relative flex items-center justify-center">
                <div className="relative">
                  {/* Resume Icon */}
                  <div className="w-16 h-20 bg-white rounded-xl border border-gray-200 shadow-sm flex items-center justify-center relative z-10 group-hover:scale-105 transition-transform duration-300">
                    <div className="w-8 h-1 bg-gray-100 rounded-full absolute top-4 left-4" />
                    <div className="w-6 h-1 bg-gray-100 rounded-full absolute top-7 left-4" />
                    <div className="w-8 h-1 bg-gray-100 rounded-full absolute top-10 left-4" />
                  </div>

                  {/* Floating inferred skills */}
                  <div className="absolute -top-4 -right-12 bg-white px-2 py-1 rounded-md shadow-sm border border-purple-100 text-[10px] font-bold text-purple-600 flex items-center gap-1 transform translate-y-0 opacity-100 transition-all duration-500 z-20">
                    <Sparkles className="w-2.5 h-2.5" /> Strategy
                  </div>
                  <div className="absolute -bottom-2 -left-10 bg-white px-2 py-1 rounded-md shadow-sm border border-blue-100 text-[10px] font-bold text-blue-600 flex items-center gap-1 transform translate-y-0 opacity-100 transition-all duration-500 z-20">
                    <Brain className="w-2.5 h-2.5" /> Scaling
                  </div>
                  <div className="absolute top-8 -right-16 bg-white px-2 py-1 rounded-md shadow-sm border border-orange-100 text-[10px] font-bold text-orange-600 flex items-center gap-1 transform translate-x-0 opacity-100 transition-all duration-500 z-20">
                    <Target className="w-2.5 h-2.5" /> Leadership
                  </div>
                </div>
              </div>

              <h3 className="font-hunt text-xl font-bold text-black mb-3 group-hover:text-primary transition-colors">Infers What You Don't Say</h3>
              <p className="text-gray-600 text-sm leading-relaxed">
                Your resume doesn't list every skill. Hunt infers the expertise that naturally comes with your experience — then matches on what actually matters.
              </p>
            </div>

            {/* Card 3: Explainability */}
            <div className="group bg-gray-50 rounded-3xl p-6 md:p-8 hover:shadow-xl hover:shadow-gray-200/50 transition-all duration-500 border border-gray-100 overflow-hidden relative">
              <div className="absolute top-0 right-0 w-32 h-32 bg-green-50/50 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-150 duration-700" />
              
              <div className="h-48 mb-6 relative flex items-center justify-center">
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 w-48 transform group-hover:-translate-y-1 transition-transform duration-500">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-xs font-semibold text-gray-500">Match Score</span>
                    <span className="text-lg font-bold text-green-600">94%</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5 text-green-600" />
                      </div>
                      <span className="text-[10px] font-medium text-gray-700">Domain Expertise</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5 text-green-600" />
                      </div>
                      <span className="text-[10px] font-medium text-gray-700">Seniority Match</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5 text-green-600" />
                      </div>
                      <span className="text-[10px] font-medium text-gray-700">Culture Fit</span>
                    </div>
                    <div className="h-1 w-full bg-gray-100 rounded-full mt-2 overflow-hidden">
                      <div className="h-full bg-green-500 w-[94%] transition-all duration-1000 ease-out"></div>
                    </div>
                  </div>
                </div>
              </div>

              <h3 className="font-hunt text-xl font-bold text-black mb-3 group-hover:text-primary transition-colors">Shows You Why You Matched</h3>
              <p className="text-gray-600 text-sm leading-relaxed">
                No black box. See exactly which dimensions aligned — domain expertise, seniority, skills, culture — so you know a match is real.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How Hunt Works Section */}
      <section id="how-it-works" className="py-24 bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <div className="text-center max-w-3xl mx-auto mb-20">
            <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold text-black mb-6">
              How Hunt Works
            </h2>
            <p className="text-lg text-gray-600">
              Stop relying on keyword searches. We built a pipeline that finds jobs first, understands them deeply, and only shows you what actually fits.
            </p>
          </div>

          <div className="space-y-24">
            {/* Step 1: Crawling */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-24 items-center">
              <div className="order-2 md:order-1 relative h-[360px] w-full flex items-center justify-center overflow-hidden bg-gray-50 rounded-3xl border border-gray-100">
                {/* Central Hunt Logo */}
                <div className="relative z-20 w-24 h-24 bg-white rounded-3xl shadow-xl border border-gray-100 flex items-center justify-center transform hover:scale-105 transition-transform duration-300">
                  <Image src="/paper.png" width={48} height={48} alt="Hunt Logo" className="object-contain" />
                </div>

                {/* Animated Background Grid of Logos */}
                <div className="absolute inset-0 opacity-50">
                  {/* Row 1 - Moving Right */}
                  <div className="absolute top-[5%] flex gap-8 animate-[marquee_30s_linear_infinite] w-[200%]">
                    {[...Array(2)].map((_, i) => (
                      <div key={`r1-${i}`} className="flex gap-8 shrink-0">
                        {['/dropboxlogo.png', '/databrickslogo.png', '/mailchimplogo.png', '/stripelogo.png', '/spotify.png', '/github.png', '/Pinterest.svg.png'].map((logo, j) => (
                          <div key={j} className="w-16 h-16 bg-white/80 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center p-3 opacity-60">
                            <Image src={logo} width={32} height={32} alt="Company" className="object-contain grayscale hover:grayscale-0 transition-all" />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Row 2 - Moving Left */}
                  <div className="absolute top-[25%] flex gap-8 animate-[marquee-reverse_35s_linear_infinite] w-[200%]">
                    {[...Array(2)].map((_, i) => (
                      <div key={`r2-${i}`} className="flex gap-8 shrink-0">
                         {['/spotify.png', '/github.png', '/Pinterest.svg.png', '/dropboxlogo.png', '/databrickslogo.png', '/mailchimplogo.png', '/stripelogo.png'].map((logo, j) => (
                          <div key={j} className="w-16 h-16 bg-white/80 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center p-3 opacity-40">
                            <Image src={logo} width={32} height={32} alt="Company" className="object-contain grayscale hover:grayscale-0 transition-all" />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Row 3 - Moving Right */}
                  <div className="absolute top-[45%] flex gap-8 animate-[marquee_40s_linear_infinite] w-[200%]">
                    {/* Center gap for logo */}
                     {[...Array(2)].map((_, i) => (
                      <div key={`r3-${i}`} className="flex gap-8 shrink-0">
                         {['/stripelogo.png', '/spotify.png', '/github.png', '/Pinterest.svg.png', '/dropboxlogo.png', '/databrickslogo.png', '/mailchimplogo.png'].map((logo, j) => (
                          <div key={j} className={`w-16 h-16 bg-white/80 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center p-3 opacity-30 ${j === 3 ? 'invisible' : ''}`}>
                            <Image src={logo} width={32} height={32} alt="Company" className="object-contain grayscale hover:grayscale-0 transition-all" />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Row 4 - Moving Left */}
                  <div className="absolute top-[65%] flex gap-8 animate-[marquee-reverse_32s_linear_infinite] w-[200%]">
                    {[...Array(2)].map((_, i) => (
                      <div key={`r4-${i}`} className="flex gap-8 shrink-0">
                         {['/mailchimplogo.png', '/stripelogo.png', '/spotify.png', '/github.png', '/Pinterest.svg.png', '/dropboxlogo.png', '/databrickslogo.png'].map((logo, j) => (
                          <div key={j} className="w-16 h-16 bg-white/80 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center p-3 opacity-40">
                            <Image src={logo} width={32} height={32} alt="Company" className="object-contain grayscale hover:grayscale-0 transition-all" />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Row 5 - Moving Right */}
                  <div className="absolute top-[85%] flex gap-8 animate-[marquee_38s_linear_infinite] w-[200%]">
                    {[...Array(2)].map((_, i) => (
                      <div key={`r5-${i}`} className="flex gap-8 shrink-0">
                         {['/databrickslogo.png', '/mailchimplogo.png', '/stripelogo.png', '/spotify.png', '/github.png', '/Pinterest.svg.png', '/dropboxlogo.png'].map((logo, j) => (
                          <div key={j} className="w-16 h-16 bg-white/80 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center p-3 opacity-60">
                            <Image src={logo} width={32} height={32} alt="Company" className="object-contain grayscale hover:grayscale-0 transition-all" />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Fade Gradients to mask edges */}
                <div className="absolute left-0 top-0 bottom-0 w-24 bg-gradient-to-r from-gray-50/50 to-transparent z-10" />
                <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-gray-50/50 to-transparent z-10" />
                
                {/* Center Radial Fade to make text readable/focus on logo */}
                <div className="absolute inset-0 bg-radial-at-c from-transparent via-transparent to-gray-50/30 pointer-events-none" />
              </div>
              
              <div className="order-1 md:order-2">
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mb-6">1</div>
                <h3 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-4">
                  We Crawl Company Sites Directly
                </h3>
                <p className="text-base text-gray-600 leading-relaxed">
                  We don't scrape LinkedIn or Indeed. We go straight to the source — monitoring thousands of company career pages and ATS systems every single day. This means we find roles days before they hit the aggregators, giving you a first-mover advantage.
                </p>
              </div>
            </div>

            {/* Step 2: AI Matching */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-24 items-center">
              <div>
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mb-6">2</div>
                <h3 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-4">
                  You Upload, AI Matches
                </h3>
                <p className="text-base text-gray-600 leading-relaxed">
                  Upload your resume and let our AI do the heavy lifting. We analyze your experience, skills, and career trajectory to build a comprehensive profile. No more manual filters — we match you based on who you actually are.
                </p>
              </div>
              
              <div className="relative h-[400px] w-full flex flex-col items-center justify-center bg-gray-50 rounded-3xl border border-gray-100 overflow-hidden p-8">
                {/* Connection Line */}
                <div className="absolute left-1/2 top-[56%] -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full border border-gray-200 flex items-center justify-center shadow-sm z-10">
                  <ArrowRight className="w-4 h-4 text-primary rotate-90" />
                </div>

                {/* Top: Resume Source */}
                <div className="relative w-full max-w-[320px] bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-8 transform hover:-translate-y-1 transition-transform duration-300">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="font-bold text-gray-900 text-sm">Senior Product Manager</div>
                      <div className="text-xs text-gray-500 font-medium">Uber • 2020 - Present</div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <div className="w-1 min-w-[4px] h-1 rounded-full bg-gray-300 mt-1.5"></div>
                      <p className="text-[10px] text-gray-600 leading-relaxed">
                        Led the <span className="bg-blue-50 text-blue-700 px-0.5 rounded font-medium">Driver Growth</span> team, increasing activation by 15% through optimized onboarding flows.
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <div className="w-1 min-w-[4px] h-1 rounded-full bg-gray-300 mt-1.5"></div>
                      <p className="text-[10px] text-gray-600 leading-relaxed">
                        Managed a cross-functional team of 10 engineers and designers to launch the new <span className="bg-purple-50 text-purple-700 px-0.5 rounded font-medium">Driver Rewards</span> program.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Bottom: AI Understanding (Badges) */}
                <div className="w-full max-w-[380px] grid grid-cols-2 gap-3 mt-4">
                  {/* Skill Badge 1 */}
                  <div className="bg-white p-2.5 rounded-lg border border-primary/20 shadow-sm flex items-center gap-2 animate-[fadeIn_0.5s_ease-out_forwards]">
                    <div className="w-5 h-5 rounded-full bg-green-50 flex items-center justify-center shrink-0">
                      <Check className="w-3 h-3 text-green-600" strokeWidth={3} />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-gray-900">Growth Product</div>
                      <div className="text-[9px] text-gray-500">Inferred from "Activation"</div>
                    </div>
                  </div>

                  {/* Skill Badge 2 */}
                  <div className="bg-white p-2.5 rounded-lg border border-primary/20 shadow-sm flex items-center gap-2 animate-[fadeIn_0.7s_ease-out_forwards]">
                    <div className="w-5 h-5 rounded-full bg-green-50 flex items-center justify-center shrink-0">
                      <Check className="w-3 h-3 text-green-600" strokeWidth={3} />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-gray-900">B2C Marketplaces</div>
                      <div className="text-[9px] text-gray-500">Context: Uber</div>
                    </div>
                  </div>

                  {/* Skill Badge 3 */}
                  <div className="bg-white p-2.5 rounded-lg border border-primary/20 shadow-sm flex items-center gap-2 animate-[fadeIn_0.9s_ease-out_forwards]">
                    <div className="w-5 h-5 rounded-full bg-green-50 flex items-center justify-center shrink-0">
                      <Check className="w-3 h-3 text-green-600" strokeWidth={3} />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-gray-900">Cross-functional</div>
                      <div className="text-[9px] text-gray-500">Managed 10+ team</div>
                    </div>
                  </div>

                  {/* Skill Badge 4 */}
                  <div className="bg-white p-2.5 rounded-lg border border-primary/20 shadow-sm flex items-center gap-2 animate-[fadeIn_1.1s_ease-out_forwards]">
                    <div className="w-5 h-5 rounded-full bg-green-50 flex items-center justify-center shrink-0">
                      <Check className="w-3 h-3 text-green-600" strokeWidth={3} />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-gray-900">Retention Strategy</div>
                      <div className="text-[9px] text-gray-500">Inferred from "Rewards"</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Step 3: Curated List */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-24 items-center">
              <div className="order-2 md:order-1 relative h-[400px] w-full flex items-center justify-center bg-gray-50 rounded-3xl border border-gray-100">
                <div className="w-full max-w-sm space-y-3 p-6">
                   {/* High Match Card */}
                   <div className="bg-white p-4 rounded-xl border border-orange-200 shadow-sm flex items-center justify-between transform hover:scale-105 transition-transform duration-300 relative overflow-hidden">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center">
                        <Image src="/stripelogo.png" width={24} height={24} alt="Stripe" className="object-contain" />
                      </div>
                      <div>
                        <div className="font-bold text-sm text-gray-900">Senior Engineer</div>
                        <div className="text-xs text-gray-500">Stripe</div>
                      </div>
                    </div>
                    <div className="px-2 py-1 bg-orange-50 text-orange-700 text-xs font-bold rounded-lg border border-orange-100">
                      98% Match
                    </div>
                   </div>

                   {/* Good Match Card */}
                   <div className="bg-white p-4 rounded-xl border border-orange-100 shadow-sm flex items-center justify-between opacity-80">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-gray-50 flex items-center justify-center">
                        <Image src="/mailchimplogo.png" width={24} height={24} alt="Airbnb" className="object-contain" />
                      </div>
                      <div>
                        <div className="font-bold text-sm text-gray-900">Product Lead</div>
                        <div className="text-xs text-gray-500">Airbnb</div>
                      </div>
                    </div>
                    <div className="px-2 py-1 bg-orange-50 text-orange-600 text-xs font-bold rounded-lg border border-orange-100">
                      92% Match
                    </div>
                   </div>

                   {/* Zero Results State (Hidden/Faded to imply filtering) */}
                   <div className="mt-6 text-center">
                     <div className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-full text-xs font-medium text-gray-500">
                       <Filter className="w-3 h-3" />
                       Hiding 1,402 irrelevant roles
                     </div>
                   </div>
                </div>
              </div>
              
              <div className="order-1 md:order-2">
                <div className="w-10 h-10 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mb-6">3</div>
                <h3 className="font-hunt text-2xl md:text-3xl font-bold text-black mb-4">
                  Curated Matches, Zero Noise
                </h3>
                <p className="text-base text-gray-600 leading-relaxed">
                  We only show you jobs that are a strong match. No random listings, no "spray and pray." You get a shortlist of roles where you're likely to get an interview. If we find nothing, we tell you — saving you hours of doom-scrolling.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Comparison Table Section */}
      <section id="compare" className="bg-white border-t border-gray-100">
        <ComparisonTable />
      </section>

      {/* FAQ Section */}
      <FAQSection />

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-16">
        <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-20">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12 md:gap-8">
            {/* Brand Column */}
            <div className="md:col-span-1">
              <Link href="/home" className="flex items-center gap-2 mb-4">
                <Image
                  src="/paper.png"
                  alt="Hunt"
                  width={28}
                  height={28}
                />
                <span className="text-xl font-bold text-black font-hunt">
                  hunt<span className="text-primary">.</span>
                </span>
              </Link>
              <p className="text-sm text-gray-600 leading-relaxed">
                Finally, a job search on your side. We put candidates first with AI-powered matching that actually understands you.
              </p>
            </div>

            {/* Product Column */}
            <div>
              <h4 className="font-semibold text-gray-900 mb-4">Product</h4>
              <ul className="space-y-3">
                <li>
                  <Link href="#features" className="text-sm text-gray-600 hover:text-primary transition-colors">
                    Features
                  </Link>
                </li>
                <li>
                  <Link href="#how-it-works" className="text-sm text-gray-600 hover:text-primary transition-colors">
                    How It Works
                  </Link>
                </li>
                <li>
                  <Link href="#compare" className="text-sm text-gray-600 hover:text-primary transition-colors">
                    Compare
                  </Link>
                </li>
              </ul>
            </div>

            {/* Legal Column */}
            <div>
              <h4 className="font-semibold text-gray-900 mb-4">Legal</h4>
              <ul className="space-y-3">
                <li>
                  <Link href="/privacy" className="text-sm text-gray-600 hover:text-primary transition-colors">
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link href="/terms" className="text-sm text-gray-600 hover:text-primary transition-colors">
                    Terms of Service
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="mt-12 pt-8 border-t border-gray-100 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-gray-500">
              © {new Date().getFullYear()} Hunt. All rights reserved.
            </p>
            <Link href="https://x.com/talwinderbuilds" target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-primary transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

const faqs = [
  {
    question: "How is Hunt different from LinkedIn or Indeed?",
    answer: "We crawl company career pages directly, surfacing jobs that never appear on traditional aggregators. Unlike platforms that prioritize employers who pay for visibility, Hunt prioritizes candidates. Our AI understands context — 'operations at DoorDash' means logistics, not back-office work at a bank."
  },
  {
    question: "Is Hunt free to use?",
    answer: "Yes! Hunt is completely free for job seekers right now. Our mission is to level the playing field for job seekers, not add another barrier."
  },
  {
    question: "How does the AI matching work?",
    answer: "Upload your resume and our AI builds a comprehensive profile of your experience, skills, and career trajectory. We go beyond keyword matching — we infer skills from context, understand industry-specific terminology, and match you to roles where you're genuinely qualified."
  },
  {
    question: "What types of jobs does Hunt list?",
    answer: "We focus on tech and startup roles across engineering, product, design, data, operations, and more. We monitor thousands of company career pages daily, from early-stage startups to established tech giants, surfacing fresh opportunities you won't find elsewhere."
  },
  {
    question: "How often are new jobs added?",
    answer: "We add thousands of new jobs every single day. Our crawlers run continuously, monitoring company career pages in real-time. This means you often see roles on Hunt days before they appear on LinkedIn or Indeed."
  },
  {
    question: "Can I use Hunt if I'm not actively job searching?",
    answer: "Absolutely. Many users set up profiles to passively monitor the market. We'll notify you when highly relevant opportunities appear — perfect for staying aware of what's out there without the pressure of an active search."
  },
  {
    question: "How do you ensure job listings are real and not spam?",
    answer: "We only crawl verified company career pages and official ATS systems — never third-party job boards or scraped listings. This means every job you see is a real, active opening posted directly by the employer."
  },
  {
    question: "What makes your match scores accurate?",
    answer: "Our matching considers multiple dimensions: domain expertise, seniority level, technical skills, industry context, and company stage preferences. We show you exactly why you matched, so there's no black box — you know a match is real before you apply."
  }
]

function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <section className="py-24 bg-gray-50 border-t border-gray-100">
      <div className="max-w-4xl mx-auto px-6 md:px-12">
        <div className="text-center mb-16">
          <h2 className="font-hunt text-3xl md:text-4xl lg:text-5xl font-bold text-black mb-4">
            Frequently Asked Questions
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Everything you need to know about Hunt and how we're changing job search for the better.
          </p>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <div 
              key={index}
              className="bg-white rounded-2xl border border-gray-200 overflow-hidden transition-all duration-300 hover:border-gray-300"
            >
              <button
                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                className="w-full px-6 py-5 flex items-center justify-between text-left"
              >
                <span className="font-semibold text-gray-900 pr-4">{faq.question}</span>
                <ChevronDown 
                  className={`w-5 h-5 text-gray-500 shrink-0 transition-transform duration-300 ${
                    openIndex === index ? 'rotate-180' : ''
                  }`} 
                />
              </button>
              <div 
                className={`px-6 overflow-hidden transition-all duration-300 ${
                  openIndex === index ? 'pb-5 max-h-96' : 'max-h-0'
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
