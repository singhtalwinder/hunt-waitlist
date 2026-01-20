'use client'

import { Check } from 'lucide-react'

export function ValueProposition() {
  return (
    <div className="space-y-6 md:space-y-4 lg:space-y-6">
      <div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-black leading-tight tracking-tight">
          Stop applying blind.
        </h1>
        <p className="text-xl md:text-2xl lg:text-3xl text-gray-600 mt-2 md:mt-1 lg:mt-2 leading-snug">
          Find tech jobs you're actually likely to get.
        </p>
      </div>

      <div className="space-y-5 md:space-y-3 lg:space-y-4">
        <div className="space-y-2 md:space-y-1">
          <div className="flex items-start gap-3 md:gap-2 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              See real opportunities — not job board noise.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-7 lg:pl-9 leading-relaxed">
            We crawl real company career pages and ATS systems to surface active tech roles — no reposted junk, no expired listings.
          </p>
        </div>

        <div className="space-y-2 md:space-y-1">
          <div className="flex items-start gap-3 md:gap-2 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Built for business and developers in tech.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-7 lg:pl-9 leading-relaxed">
            We match you using role‑specific signals — not one‑size‑fits‑all keyword matching.
          </p>
        </div>

        <div className="space-y-2 md:space-y-1">
          <div className="flex items-start gap-3 md:gap-2 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Honest matches — even when there are none.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-7 lg:pl-9 leading-relaxed">
            No fake recommendations, no pressure to apply — just clarity and timing you can trust.
          </p>
        </div>
      </div>
    </div>
  )
}
