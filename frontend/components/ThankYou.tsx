'use client'

import { useState } from 'react'
import { Share2, Check } from 'lucide-react'
import { Logo } from './Logo'

export function ThankYou() {
  const [copied, setCopied] = useState(false)

  const handleShare = async () => {
    const url = window.location.origin
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = url
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="p-8 md:p-10 text-center">
      {/* Badge - above logo */}
      <div className="flex justify-center mb-6">
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-black text-white rounded-full text-sm font-medium">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
          On the waitlist
        </div>
      </div>

      <div className="flex justify-center mb-6">
        <Logo size={80} />
      </div>
      
      <h2 className="text-2xl md:text-3xl font-bold text-black mb-4">
        You're all set!
      </h2>
      
      <p className="text-gray-600 mb-8 max-w-md mx-auto">
        Thanks for joining the hunt. We'll reach out shortly when we're ready to launch. Keep an eye on your inbox!
      </p>

      <button
        onClick={handleShare}
        className="inline-flex items-center gap-2 px-6 py-3 bg-primary hover:bg-orange-600 text-white font-semibold rounded-lg transition-colors"
      >
        {copied ? (
          <>
            <Check className="w-5 h-5" />
            Link copied!
          </>
        ) : (
          <>
            <Share2 className="w-5 h-5" />
            Share with friends
          </>
        )}
      </button>
    </div>
  )
}
