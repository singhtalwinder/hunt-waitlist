import Link from 'next/link'
import { SignupForm } from './signup-form'

export const metadata = {
  title: 'Sign Up - Hunt',
  description: 'Create your Hunt account',
}

export default function SignupPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">
        Create an account
      </h1>
      <p className="text-muted-foreground mb-8">
        Enter your details to get started
      </p>

      <SignupForm />

      <div className="mt-6 text-center text-sm">
        <span className="text-muted-foreground">Already have an account? </span>
        <Link href="/login" className="text-primary hover:underline font-medium">
          Sign in
        </Link>
      </div>
    </div>
  )
}
