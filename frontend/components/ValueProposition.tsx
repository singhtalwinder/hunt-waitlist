'use client'

import { Check } from 'lucide-react'

export function ValueProposition() {
  return (
    <div className="space-y-6 md:space-y-5 lg:space-y-6">
      <div>
        <h1 className="text-3xl md:text-xl lg:text-3xl font-bold text-black font-hunt leading-tight tracking-tight">
          Job matching that actually understands you
        </h1>
        <p className="text-base md:text-sm lg:text-base text-gray-600 mt-3 md:mt-2 lg:mt-3">
          LinkedIn sees "operations" and shows you insurance back-office roles when you've spent a decade in tech. Hunt reads your resume the way a great recruiter would.
        </p>
      </div>

      <div className="space-y-5 md:space-y-4 lg:space-y-5">
        <div className="space-y-2 md:space-y-1.5 lg:space-y-2">
          <div className="flex items-start gap-3 md:gap-3 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-primary flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Context, not keywords.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-8 lg:pl-9 leading-relaxed">
            "Operations at DoorDash" means logistics, gig economy, and scaling under pressure — not the same as operations at a bank. Hunt understands the difference.
          </p>
        </div>

        <div className="space-y-2 md:space-y-1.5 lg:space-y-2">
          <div className="flex items-start gap-3 md:gap-3 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-primary flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Infers what you don't say.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-8 lg:pl-9 leading-relaxed">
            Your resume doesn't list every skill you have. Hunt infers the expertise that naturally comes with your experience — then matches on what actually matters.
          </p>
        </div>

        <div className="space-y-2 md:space-y-1.5 lg:space-y-2">
          <div className="flex items-start gap-3 md:gap-3 lg:gap-3">
            <div className="flex-shrink-0 w-6 h-6 md:w-5 md:h-5 lg:w-6 lg:h-6 rounded-full bg-primary flex items-center justify-center mt-0.5">
              <Check className="w-4 h-4 md:w-3 md:h-3 lg:w-4 lg:h-4 text-white" strokeWidth={3} />
            </div>
            <h2 className="text-lg md:text-sm md:leading-tight lg:text-lg font-semibold text-black">
              Shows you why you matched.
            </h2>
          </div>
          <p className="text-base md:text-xs md:leading-relaxed lg:text-base text-gray-600 pl-9 md:pl-8 lg:pl-9 leading-relaxed">
            No black box. See exactly which dimensions aligned — domain expertise, seniority, skills, culture, and career trajectory — so you know a match is real.
          </p>
        </div>
      </div>
    </div>
  )
}
