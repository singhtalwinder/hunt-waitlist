'use client'

import { Check, ArrowRight, Eye, EyeOff, RefreshCw } from 'lucide-react'

interface AllSetProps {
  onShowMatches: () => void
}

export function AllSet({ onShowMatches }: AllSetProps) {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 text-center">
      {/* Success Icon */}
      <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-8">
        <Check className="w-10 h-10 text-green-600" strokeWidth={3} />
      </div>

      {/* Title */}
      <h1 className="font-hunt text-3xl md:text-4xl font-bold text-black mb-4">
        All set
      </h1>

      {/* Body Copy */}
      <p className="text-gray-600 text-lg mb-10 max-w-md mx-auto">
        We'll now start showing you a short list of roles that genuinely fit your background and goals.
      </p>

      {/* Value Points */}
      <div className="space-y-4 mb-10 max-w-sm mx-auto">
        <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <Eye className="w-5 h-5 text-green-600" />
          </div>
          <span className="text-left text-gray-700">
            You'll see <span className="font-medium text-gray-900">why each job matches</span>
          </span>
        </div>

        <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <EyeOff className="w-5 h-5 text-green-600" />
          </div>
          <span className="text-left text-gray-700">
            We'll <span className="font-medium text-gray-900">hide roles that don't make sense</span>
          </span>
        </div>

        <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <RefreshCw className="w-5 h-5 text-green-600" />
          </div>
          <span className="text-left text-gray-700">
            You can <span className="font-medium text-gray-900">update your profile anytime</span>
          </span>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={onShowMatches}
        className="px-10 py-4 bg-primary text-white rounded-full font-semibold hover:bg-orange-600 transition-colors shadow-lg shadow-orange-500/25 flex items-center justify-center gap-2 mx-auto"
      >
        Show My Matches
        <ArrowRight className="w-5 h-5" />
      </button>
    </div>
  )
}
