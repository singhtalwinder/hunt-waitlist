'use client'

import { useState, useEffect } from 'react'
import { Briefcase, Bell, Settings, LogOut } from 'lucide-react'
import { Logo } from '@/components/Logo'
import { JobList } from '@/components/JobList'

export default function JobsPage() {
  const [candidateId, setCandidateId] = useState<string | null>(null)

  useEffect(() => {
    const storedId = localStorage.getItem('hunt_candidate_id')
    if (storedId) {
      setCandidateId(storedId)
    }
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Logo size={28} />
            <span
              className="text-xl font-bold text-black font-hunt"
            >
              hunt<span className="text-primary">.</span>
            </span>
          </div>

          <nav className="flex items-center gap-6">
            <a
              href="/dashboard"
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Briefcase className="w-4 h-4" />
              <span>Matches</span>
            </a>
            <a
              href="/jobs"
              className="flex items-center gap-2 text-primary font-medium"
            >
              <Bell className="w-4 h-4" />
              <span>All Jobs</span>
            </a>
            <a
              href="/settings"
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </a>
          </nav>

          <div className="flex items-center gap-4">
            {candidateId ? (
              <button
                onClick={() => {
                  localStorage.removeItem('hunt_candidate_id')
                  window.location.href = '/'
                }}
                className="text-gray-500 hover:text-gray-700"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            ) : (
              <a
                href="/"
                className="text-primary hover:underline text-sm font-medium"
              >
                Sign up
              </a>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            All Tech Jobs
          </h1>
          <p className="text-gray-600">
            Fresh jobs from top tech companies, updated multiple times daily.
          </p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <JobList candidateId={candidateId || undefined} />
        </div>
      </main>
    </div>
  )
}
