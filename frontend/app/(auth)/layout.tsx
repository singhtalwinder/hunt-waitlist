import Link from 'next/link'

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Forms */}
      <div className="flex-1 flex flex-col justify-center px-4 py-12 sm:px-6 lg:px-20 xl:px-24">
        <div className="mx-auto w-full max-w-sm">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 mb-8">
            <img src="/paper.png" alt="Hunt" className="h-8 w-8" />
            <span className="font-hunt text-2xl font-bold">Hunt</span>
          </Link>
          
          {children}
        </div>
      </div>

      {/* Right Panel - Art (hidden on mobile) */}
      <div className="hidden lg:flex lg:flex-1 bg-muted relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            src="/auth-illustration-vertical.png"
            alt="Hunt - Find your next job"
            className="w-full h-full object-cover"
          />
          {/* Overlay to ensure text readability if we add any, or just to tint it slightly */}
          <div className="absolute inset-0 bg-orange-50/10" />
        </div>
      </div>
    </div>
  )
}
