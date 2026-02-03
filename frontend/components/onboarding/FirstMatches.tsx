'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Check, EyeOff, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

interface Match {
  id: string
  title: string
  company: string
  logo: string
  matchScore: number
  matchReasons: string[]
  location: string
  posted: string
}

const sampleMatches: Match[] = [
  {
    id: '1',
    title: 'Senior Product Manager',
    company: 'Stripe',
    logo: '/stripelogo.png',
    matchScore: 96,
    matchReasons: [
      'Direct B2B payments experience',
      'Seniority level match',
      'Cross-functional leadership skills',
    ],
    location: 'San Francisco, CA',
    posted: '2 days ago',
  },
  {
    id: '2',
    title: 'Product Lead, Growth',
    company: 'Spotify',
    logo: '/spotify.png',
    matchScore: 94,
    matchReasons: [
      'Growth & activation expertise',
      'Consumer marketplace experience',
      'Data-driven decision making',
    ],
    location: 'New York, NY (Hybrid)',
    posted: '3 days ago',
  },
  {
    id: '3',
    title: 'Principal Product Manager',
    company: 'Dropbox',
    logo: '/dropboxlogo.png',
    matchScore: 91,
    matchReasons: [
      'Product strategy experience',
      'Scaling products background',
      'Strong technical collaboration',
    ],
    location: 'Remote (US)',
    posted: '1 day ago',
  },
  {
    id: '4',
    title: 'Group PM, Platform',
    company: 'Databricks',
    logo: '/databrickslogo.png',
    matchScore: 88,
    matchReasons: [
      'Platform product experience',
      'B2B SaaS background',
      'Enterprise customer focus',
    ],
    location: 'San Francisco, CA',
    posted: '5 days ago',
  },
]

function MatchCard({ match }: { match: Match }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden transition-all hover:border-gray-300 hover:shadow-md">
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          {/* Company & Role */}
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center overflow-hidden shrink-0">
              <Image
                src={match.logo}
                alt={match.company}
                width={32}
                height={32}
                className="object-contain"
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 mb-1">{match.title}</h3>
              <p className="text-gray-600">{match.company}</p>
              <p className="text-sm text-gray-500 mt-1">{match.location} · {match.posted}</p>
            </div>
          </div>

          {/* Match Score */}
          <div className="flex flex-col items-end shrink-0">
            <div className="flex items-center gap-1.5 mb-1">
              <Check className="w-4 h-4 text-green-600" strokeWidth={3} />
              <span className="text-green-700 font-bold text-lg">{match.matchScore}%</span>
            </div>
            <span className="text-xs text-gray-500">Match</span>
          </div>
        </div>

        {/* Expand Toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-4 flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-4 h-4" />
              Hide match details
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4" />
              Why you matched
            </>
          )}
        </button>

        {/* Match Reasons (Expanded) */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-sm font-medium text-gray-700 mb-3">Why this is a strong match:</p>
            <ul className="space-y-2">
              {match.matchReasons.map((reason, index) => (
                <li key={index} className="flex items-center gap-2 text-sm text-gray-600">
                  <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <Check className="w-3 h-3 text-green-600" strokeWidth={3} />
                  </div>
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Action */}
      <div className="px-5 py-3 bg-gray-50 border-t border-gray-100">
        <button className="w-full flex items-center justify-center gap-2 text-sm font-medium text-primary hover:text-orange-600 transition-colors">
          View Job
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

export function FirstMatches() {
  const hiddenCount = 1247

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
          Your Top Matches
        </h1>
        <p className="text-gray-600">
          {sampleMatches.length} strong matches based on your profile
        </p>
      </div>

      {/* Matches List */}
      <div className="space-y-4 mb-6">
        {sampleMatches.map(match => (
          <MatchCard key={match.id} match={match} />
        ))}
      </div>

      {/* Hidden Roles Indicator */}
      <div className="flex items-center justify-center gap-2 py-4 mb-6">
        <div className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-full">
          <EyeOff className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-600">
            {hiddenCount.toLocaleString()} irrelevant roles hidden
          </span>
        </div>
      </div>

      {/* Micro-copy */}
      <div className="text-center mb-8 p-4 bg-gray-50 rounded-xl">
        <p className="text-sm text-gray-600">
          You're seeing <span className="font-medium text-gray-900">fewer jobs by design</span> — this is your filtered view of the market.
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Link
          href="/dashboard"
          className="flex-1 px-6 py-3.5 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 text-center"
        >
          Go to Dashboard
        </Link>
        <Link
          href="/settings"
          className="flex-1 px-6 py-3.5 border border-gray-200 text-gray-700 rounded-full font-medium hover:bg-gray-50 hover:border-gray-300 transition-colors text-center"
        >
          Adjust Preferences
        </Link>
      </div>
    </div>
  )
}
