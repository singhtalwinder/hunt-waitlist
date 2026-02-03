import Link from 'next/link'
import { LoginForm } from './login-form'

export const metadata = {
  title: 'Login - Hunt',
  description: 'Sign in to your Hunt account',
}

export default function LoginPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight mb-2">
        Welcome back
      </h1>
      <p className="text-muted-foreground mb-8">
        Enter your email to sign in to your account
      </p>

      <LoginForm />

      <div className="mt-6 text-center text-sm">
        <span className="text-muted-foreground">Don&apos;t have an account? </span>
        <Link href="/signup" className="text-primary hover:underline font-medium">
          Sign up
        </Link>
      </div>
    </div>
  )
}
