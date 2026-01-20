'use client'

export function RocketLogo({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Rocket body */}
      <path
        d="M32 4C32 4 20 16 20 36C20 44 24 52 32 56C40 52 44 44 44 36C44 16 32 4 32 4Z"
        fill="#000000"
        stroke="#000000"
        strokeWidth="2"
      />
      {/* Rocket window */}
      <circle cx="32" cy="28" r="6" fill="white" />
      {/* Left fin */}
      <path
        d="M20 40L12 52L20 48V40Z"
        fill="#FF4500"
      />
      {/* Right fin */}
      <path
        d="M44 40L52 52L44 48V40Z"
        fill="#FF4500"
      />
      {/* Rocket flame */}
      <path
        d="M28 56C28 56 30 64 32 64C34 64 36 56 36 56C36 56 34 60 32 60C30 60 28 56 28 56Z"
        fill="#FF4500"
      />
      <path
        d="M30 56C30 56 31 62 32 62C33 62 34 56 34 56C34 56 33 59 32 59C31 59 30 56 30 56Z"
        fill="#FF6B35"
      />
    </svg>
  )
}
