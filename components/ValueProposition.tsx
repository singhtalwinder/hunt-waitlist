'use client'

import { Check } from 'lucide-react'

export function ValueProposition() {
  return (
    <div className="space-y-6 lg:space-y-8">
      <div>
        <h1 className="text-3xl sm:text-4xl md:text-4xl lg:text-5xl font-bold text-black leading-tight tracking-tight">
          Stop applying blind.
        </h1>
        <p className="text-xl sm:text-2xl md:text-2xl lg:text-3xl text-gray-600 mt-2 lg:mt-3 leading-snug">
          Find tech jobs you're actually likely to get.
        </p>
      </div>

      <div className="space-y-5 lg:space-y-6">
        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-base sm:text-lg lg:text-xl font-semibold text-black">
              See real opportunities — not job board noise.
            </h2>
          </div>
          <p className="text-sm sm:text-base lg:text-lg text-gray-600 pl-9 leading-relaxed">
            We crawl real company career pages and ATS systems to surface active tech roles — no reposted junk, no expired listings.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-base sm:text-lg lg:text-xl font-semibold text-black">
              Built for business and developers in tech.
            </h2>
          </div>
          <p className="text-sm sm:text-base lg:text-lg text-gray-600 pl-9 leading-relaxed">
            We match you using role‑specific signals — not one‑size‑fits‑all keyword matching.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-base sm:text-lg lg:text-xl font-semibold text-black">
              Honest matches — even when there are none.
            </h2>
          </div>
          <p className="text-sm sm:text-base lg:text-lg text-gray-600 pl-9 leading-relaxed">
            No fake recommendations, no pressure to apply — just clarity and timing you can trust.
          </p>
        </div>
      </div>
    </div>
  )
}
