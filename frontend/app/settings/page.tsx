'use client'

import { useState, useEffect } from 'react'
import { Loader2, Briefcase, Bell, Settings, LogOut, Save } from 'lucide-react'
import { Logo } from '@/components/Logo'
import { api, CandidateProfile } from '@/lib/api'
import { ROLE_FAMILY_LABELS, SENIORITY_LABELS, LOCATION_TYPE_LABELS } from '@/lib/types'

export default function SettingsPage() {
  const [candidate, setCandidate] = useState<CandidateProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [candidateId, setCandidateId] = useState<string | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [roleFamilies, setRoleFamilies] = useState<string[]>([])
  const [seniority, setSeniority] = useState('')
  const [minSalary, setMinSalary] = useState('')
  const [locationTypes, setLocationTypes] = useState<string[]>([])
  const [skills, setSkills] = useState('')

  useEffect(() => {
    const storedId = localStorage.getItem('hunt_candidate_id')
    if (storedId) {
      setCandidateId(storedId)
      loadCandidate(storedId)
    } else {
      setLoading(false)
    }
  }, [])

  const loadCandidate = async (id: string) => {
    try {
      const profile = await api.getCandidateProfile(id)
      setCandidate(profile)
      
      // Populate form
      setName(profile.name || '')
      setRoleFamilies(profile.role_families || [])
      setSeniority(profile.seniority || '')
      setMinSalary(profile.min_salary?.toString() || '')
      setLocationTypes(profile.location_types || [])
      setSkills(profile.skills?.join(', ') || '')
    } catch (err) {
      console.error('Failed to load profile:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!candidateId) return

    setSaving(true)
    setMessage(null)

    try {
      await api.updateCandidateProfile(candidateId, {
        name: name || null,
        role_families: roleFamilies.length > 0 ? roleFamilies : null,
        seniority: seniority || null,
        min_salary: minSalary ? parseInt(minSalary) : null,
        location_types: locationTypes.length > 0 ? locationTypes : null,
        skills: skills ? skills.split(',').map(s => s.trim()).filter(Boolean) : null,
      })

      setMessage({ type: 'success', text: 'Profile updated successfully!' })
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to update profile',
      })
    } finally {
      setSaving(false)
    }
  }

  const toggleRoleFamily = (role: string) => {
    setRoleFamilies(prev =>
      prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]
    )
  }

  const toggleLocationType = (type: string) => {
    setLocationTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#FF4500]" />
      </div>
    )
  }

  if (!candidateId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-sm p-8 max-w-md text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Sign In Required</h1>
          <p className="text-gray-600 mb-6">
            Please sign in to access your settings.
          </p>
          <a
            href="/"
            className="inline-block bg-[#FF4500] hover:bg-[#E63E00] text-white font-medium px-6 py-3 rounded-lg transition-colors"
          >
            Get Started
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Logo size={28} />
            <span
              className="text-xl font-bold text-black"
              style={{ fontFamily: "'Zalando Sans Expanded', sans-serif" }}
            >
              hunt<span className="text-[#FF4500]">.</span>
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
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Bell className="w-4 h-4" />
              <span>All Jobs</span>
            </a>
            <a
              href="/settings"
              className="flex items-center gap-2 text-[#FF4500] font-medium"
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </a>
          </nav>

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
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-2xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Profile Settings
          </h1>
          <p className="text-gray-600">
            Update your preferences to get better job matches.
          </p>
        </div>

        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent"
              placeholder="Your name"
            />
          </div>

          {/* Role Families */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Preferred Roles
            </label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(ROLE_FAMILY_LABELS).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => toggleRoleFamily(key)}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    roleFamilies.includes(key)
                      ? 'bg-[#FF4500] text-white border-[#FF4500]'
                      : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Seniority */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Experience Level
            </label>
            <select
              value={seniority}
              onChange={(e) => setSeniority(e.target.value)}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent"
            >
              <option value="">Select level</option>
              {Object.entries(SENIORITY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Minimum Salary */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Minimum Salary (USD)
            </label>
            <input
              type="number"
              value={minSalary}
              onChange={(e) => setMinSalary(e.target.value)}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent"
              placeholder="e.g., 150000"
            />
          </div>

          {/* Location Types */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Work Arrangement
            </label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(LOCATION_TYPE_LABELS).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => toggleLocationType(key)}
                  className={`px-4 py-2 rounded-lg text-sm border transition-colors ${
                    locationTypes.includes(key)
                      ? 'bg-[#FF4500] text-white border-[#FF4500]'
                      : 'bg-white text-gray-700 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Skills */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Skills (comma-separated)
            </label>
            <input
              type="text"
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#FF4500] focus:border-transparent"
              placeholder="e.g., React, TypeScript, Node.js"
            />
            <p className="text-sm text-gray-500 mt-1">
              Add skills to improve matching accuracy
            </p>
          </div>

          {/* Save button */}
          <div className="pt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full bg-[#FF4500] hover:bg-[#E63E00] text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
