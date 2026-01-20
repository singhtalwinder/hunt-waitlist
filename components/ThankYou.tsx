'use client'

import { Logo } from './Logo'

export function ThankYou() {
  return (
    <div className="bg-gray-50 rounded-2xl p-8 md:p-10 text-center">
      <div className="flex justify-center mb-6">
        <Logo size={80} />
      </div>
      
      <h2 className="text-2xl md:text-3xl font-bold text-black mb-4">
        You're all set!
      </h2>
      
      <p className="text-gray-600 mb-6 max-w-md mx-auto">
        Thanks for joining the hunt. We'll reach out shortly when we're ready to launch. Keep an eye on your inbox!
      </p>

      <div className="inline-flex items-center gap-2 px-4 py-2 bg-black text-white rounded-full text-sm font-medium">
        <span className="w-2 h-2 bg-[#FF4500] rounded-full animate-pulse"></span>
        On the waitlist
      </div>
    </div>
  )
}
