'use client'

import { Check } from 'lucide-react'

export function ValueProposition() {
  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-black leading-tight tracking-tight">
          Stop applying blind.
        </h1>
        <p className="text-2xl md:text-3xl lg:text-4xl text-gray-600 mt-2 leading-tight">
          Find tech jobs you're actually likely to get.
        </p>
      </div>

      <div className="space-y-8">
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-black flex items-center justify-center mt-1">
              <Check className="w-4 h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-xl font-semibold text-black">
              See real opportunities — not job board noise.
            </h2>
          </div>
          <p className="text-gray-600 pl-9 leading-relaxed">
            We crawl real company career pages and ATS systems to surface active tech roles across engineering, product, sales, ops, and more — no reposted junk, no expired listings.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-black flex items-center justify-center mt-1">
              <Check className="w-4 h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-xl font-semibold text-black">
              Built for business and developers in tech.
            </h2>
          </div>
          <p className="text-gray-600 pl-9 leading-relaxed">
            Whether you're a software engineer, product manager, marketer, or operator, we match you using role‑specific signals — not one‑size‑fits‑all keyword matching.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-black flex items-center justify-center mt-1">
              <Check className="w-4 h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-xl font-semibold text-black">
              Honest matches — even when there are none.
            </h2>
          </div>
          <p className="text-gray-600 pl-9 leading-relaxed">
            If there aren't good fits for your profile right now, we tell you. No fake recommendations, no pressure to apply — just clarity and timing you can trust.
          </p>
        </div>
      </div>
    </div>
  )
}
