import Link from 'next/link'
import { ForgotPasswordForm } from './forgot-password-form'

export const metadata = {
  title: 'Forgot Password - Hunt',
  description: 'Reset your Hunt account password',
}

export default function ForgotPasswordPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">
        Forgot your password?
      </h1>
      <p className="text-muted-foreground mb-8">
        Enter your email and we&apos;ll send you a link to reset your password
      </p>

      <ForgotPasswordForm />

      <div className="mt-6 text-center text-sm">
        <Link href="/login" className="text-muted-foreground hover:text-primary">
          Back to login
        </Link>
      </div>
    </div>
  )
}
