'use client'

import { Check } from 'lucide-react'

export function ValueProposition() {
  return (
    <div className="space-y-6 md:space-y-5 lg:space-y-6">
      <div>
        <h1 className="text-3xl md:text-xl lg:text-3xl font-bold text-black leading-tight tracking-tight">
          Find tech jobs before they hit job boards.
        </h1>
      </div>

      <div className="space-y-5 md:space-y-4 lg:space-y-5">
        <div className="space-y-2 md:space-y-1.5 lg:space-y-2">
          <div className="flex items-start gap-3 md:gap-3 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Discover roles other candidates haven't seen yet.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-8 lg:pl-9 leading-relaxed">
            We monitor thousands of company career pages and ATS systems to surface new roles as soon as they're posted — often days before they appear on job boards.
          </p>
        </div>

        <div className="space-y-2 md:space-y-1.5 lg:space-y-2">
          <div className="flex items-start gap-3 md:gap-3 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Get matched to the best jobs for your background.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-8 lg:pl-9 leading-relaxed">
            We analyze your experience and role preferences, then match you to jobs where your skills, seniority, and profile actually align — across engineering, product, sales, and operations.
          </p>
        </div>

        <div className="space-y-2 md:space-y-1.5 lg:space-y-2">
          <div className="flex items-start gap-3 md:gap-3 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-black flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Access jobs that never appear on job boards.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-8 lg:pl-9 leading-relaxed">
            Many companies only post roles on their own websites. We find and track those opportunities so you don't miss roles you'd never see on LinkedIn or Indeed.
          </p>
        </div>
      </div>
    </div>
  )
}
