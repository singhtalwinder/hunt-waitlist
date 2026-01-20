'use client'

import Image from 'next/image'

export function Logo({ className = '', size = 32 }: { className?: string; size?: number }) {
  return (
    <Image
      src="/paper.png"
      alt="Hunt"
      width={size}
      height={size}
      className={className}
      priority
    />
  )
}
