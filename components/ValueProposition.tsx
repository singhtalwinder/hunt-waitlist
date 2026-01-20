'use client'

import { Check } from 'lucide-react'

export function ValueProposition() {
  return (
    <div className="space-y-4 lg:space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-black leading-tight tracking-tight">
          Stop applying blind.
        </h1>
        <p className="text-lg sm:text-xl md:text-2xl lg:text-3xl text-gray-600 mt-1 lg:mt-2 leading-tight">
          Find tech jobs you're actually likely to get.
        </p>
      </div>

      <div className="space-y-3 lg:space-y-4">
        <div className="space-y-1">
          <div className="flex items-start gap-2 lg:gap-3">
            <div className="flex-shrink-0 w-5 h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-3 h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-sm sm:text-base lg:text-lg font-semibold text-black">
              See real opportunities — not job board noise.
            </h2>
          </div>
          <p className="text-xs sm:text-sm lg:text-base text-gray-600 pl-7 lg:pl-9 leading-relaxed">
            We crawl real company career pages and ATS systems to surface active tech roles — no reposted junk, no expired listings.
          </p>
        </div>

        <div className="space-y-1">
          <div className="flex items-start gap-2 lg:gap-3">
            <div className="flex-shrink-0 w-5 h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-3 h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-sm sm:text-base lg:text-lg font-semibold text-black">
              Built for business and developers in tech.
            </h2>
          </div>
          <p className="text-xs sm:text-sm lg:text-base text-gray-600 pl-7 lg:pl-9 leading-relaxed">
            We match you using role‑specific signals — not one‑size‑fits‑all keyword matching.
          </p>
        </div>

        <div className="space-y-1">
          <div className="flex items-start gap-2 lg:gap-3">
            <div className="flex-shrink-0 w-5 h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-3 h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-sm sm:text-base lg:text-lg font-semibold text-black">
              Honest matches — even when there are none.
            </h2>
          </div>
          <p className="text-xs sm:text-sm lg:text-base text-gray-600 pl-7 lg:pl-9 leading-relaxed">
            No fake recommendations, no pressure to apply — just clarity and timing you can trust.
          </p>
        </div>
      </div>
    </div>
  )
}
