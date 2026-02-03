'use client'

import { useState } from 'react'
import { Check, Pencil, Plus, Minus, ArrowRight, Shield } from 'lucide-react'
import type { OnboardingData } from '@/app/onboarding/page'

interface ProfileReviewProps {
  data: OnboardingData
  onConfirm: (updatedData: Partial<OnboardingData>) => void
}

export function ProfileReview({ data, onConfirm }: ProfileReviewProps) {
  const [editingSection, setEditingSection] = useState<string | null>(null)
  const [confirmedSections, setConfirmedSections] = useState<string[]>([])
  
  // Use parsed profile or defaults
  const profile = data.parsedProfile || {
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
  }

  const [domains, setDomains] = useState(profile.domains)
  const [strengths, setStrengths] = useState(profile.strengths)

  const toggleConfirm = (section: string) => {
    if (confirmedSections.includes(section)) {
      setConfirmedSections(prev => prev.filter(s => s !== section))
    } else {
      setConfirmedSections(prev => [...prev, section])
      setEditingSection(null)
    }
  }

  const removeDomain = (domain: string) => {
    setDomains(prev => prev.filter(d => d !== domain))
  }

  const addDomain = (domain: string) => {
    if (domain && !domains.includes(domain)) {
      setDomains(prev => [...prev, domain])
    }
  }

  const handleContinue = () => {
    onConfirm({
      parsedProfile: {
        ...profile,
        domains,
        strengths,
      },
    })
  }

  // Get readable preferences based on answers
  const getPreferenceSummary = () => {
    const parts = []
    
    if (data.direction === 'similar') {
      parts.push('Roles similar to your current path')
    } else if (data.direction === 'more-scope') {
      parts.push('More scope and responsibility')
    } else if (data.direction === 'different') {
      parts.push('Something meaningfully different')
    } else {
      parts.push('Open to various opportunities')
    }

    if (data.matchStrictness === 'strict') {
      parts.push('Strong matches only')
    } else if (data.matchStrictness === 'mostly-strong') {
      parts.push('Strong matches, with limited stretch')
    } else if (data.matchStrictness === 'wide') {
      parts.push('Wide net approach')
    }

    if (data.workStrengths?.includes('problem-solving')) {
      parts.push('Work that emphasizes problem‑solving')
    }
    if (data.workStrengths?.includes('building')) {
      parts.push('Hands-on execution')
    }

    return parts
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Title */}
      <div className="text-center mb-8">
        <h1 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
          Here's how we understand your background
        </h1>
        <p className="text-gray-600 text-lg">
          Based on your resume and answers, here's what we think describes you.
          <br />
          <span className="font-medium text-gray-700">Please correct anything that feels off</span> — this directly affects your matches.
        </p>
      </div>

      {/* Sections */}
      <div className="space-y-4">
        {/* Section 1: Experience */}
        <div className="p-5 bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Your Experience So Far</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => toggleConfirm('experience')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                  confirmedSections.includes('experience')
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <Check className="w-3.5 h-3.5" strokeWidth={3} />
                {confirmedSections.includes('experience') ? 'Confirmed' : 'Confirm'}
              </button>
              <button
                onClick={() => setEditingSection(editingSection === 'experience' ? null : 'experience')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all"
              >
                <Pencil className="w-3.5 h-3.5" />
                Edit
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-3">We think:</p>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Primary role(s)</span>
              <span className="font-medium text-gray-900">{profile.primaryRoles.join(', ')}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Experience level</span>
              <span className="font-medium text-gray-900">{profile.experienceLevel}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-gray-600">Seniority</span>
              <span className="font-medium text-gray-900">{profile.seniority}</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-600">Career pattern</span>
              <span className="font-medium text-gray-900 text-right">{profile.careerPattern}</span>
            </div>
          </div>
        </div>

        {/* Section 2: Domain & Context */}
        <div className="p-5 bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Domain & Context</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setEditingSection(editingSection === 'domain' ? null : 'domain')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all"
              >
                <Pencil className="w-3.5 h-3.5" />
                Edit
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-3">We inferred experience in:</p>
          <div className="flex flex-wrap gap-2">
            {domains.map(domain => (
              <span
                key={domain}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 rounded-full text-sm font-medium text-gray-700"
              >
                {domain}
                {editingSection === 'domain' && (
                  <button
                    onClick={() => removeDomain(domain)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                )}
              </span>
            ))}
            {editingSection === 'domain' && (
              <button
                onClick={() => {
                  const newDomain = prompt('Add a domain or area of experience:')
                  if (newDomain) addDomain(newDomain)
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-gray-300 rounded-full text-sm font-medium text-gray-500 hover:border-primary hover:text-primary transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-3">
            You don't need to list every skill on your resume for it to count.
          </p>
        </div>

        {/* Section 3: Strengths */}
        <div className="p-5 bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Strengths We Picked Up On</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => toggleConfirm('strengths')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                  confirmedSections.includes('strengths')
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <Check className="w-3.5 h-3.5" strokeWidth={3} />
                {confirmedSections.includes('strengths') ? 'Looks right' : 'Confirm'}
              </button>
              <button
                onClick={() => setEditingSection(editingSection === 'strengths' ? null : 'strengths')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all"
              >
                <Pencil className="w-3.5 h-3.5" />
                Adjust
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-500 mb-3">You're likely strongest at:</p>
          <ul className="space-y-2">
            {strengths.map((strength, index) => (
              <li key={index} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                  <Check className="w-3.5 h-3.5 text-green-600" strokeWidth={3} />
                </div>
                <span className="text-gray-700">{strength}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Section 4: Preferences */}
        <div className="p-5 bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">What You're Looking For Next</h3>
            <button
              onClick={() => setEditingSection(editingSection === 'preferences' ? null : 'preferences')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all"
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit preferences
            </button>
          </div>
          <p className="text-sm text-gray-500 mb-3">Based on your answers, you're aiming for:</p>
          <ul className="space-y-2">
            {getPreferenceSummary().map((pref, index) => (
              <li key={index} className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                <span className="text-gray-700">{pref}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Trust Copy */}
      <div className="mt-6 flex items-start gap-3 p-4 bg-gray-50 rounded-xl">
        <Shield className="w-5 h-5 text-primary shrink-0 mt-0.5" />
        <div className="text-sm text-gray-600">
          <p className="font-medium text-gray-700">We'll be conservative by default.</p>
          <p>If we're unsure about a role, we won't show it.</p>
        </div>
      </div>

      {/* Continue Button */}
      <button
        onClick={handleContinue}
        className="w-full mt-6 px-8 py-4 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 flex items-center justify-center gap-2"
      >
        Looks Good — Continue
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  )
}
