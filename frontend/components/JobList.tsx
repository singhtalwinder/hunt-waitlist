'use client'

import { useState, useEffect } from 'react'
import { Loader2, Filter, ChevronDown } from 'lucide-react'
import { api, Job, MatchedJob, JobListResponse, MatchListResponse } from '@/lib/api'
import { JobCard } from './JobCard'
import { ROLE_FAMILY_LABELS, SENIORITY_LABELS, LOCATION_TYPE_LABELS } from '@/lib/types'

interface JobListProps {
  candidateId?: string
  showMatches?: boolean
  onJobClick?: (jobId: string) => void
}

export function JobList({ candidateId, showMatches = false, onJobClick }: JobListProps) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [matches, setMatches] = useState<MatchedJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [noMatchesReason, setNoMatchesReason] = useState<string | null>(null)

  // Filters
  const [showFilters, setShowFilters] = useState(false)
  const [roleFamily, setRoleFamily] = useState<string>('')
  const [seniority, setSeniority] = useState<string>('')
  const [locationType, setLocationType] = useState<string>('')

  useEffect(() => {
    loadJobs()
  }, [candidateId, showMatches, page, roleFamily, seniority, locationType])

  const loadJobs = async () => {
    setLoading(true)
    setError(null)

    try {
      if (showMatches && candidateId) {
        const response = await api.getCandidateMatches(candidateId, {
          page,
          page_size: 20,
        })
        setMatches(response.matches)
        setTotal(response.total)
        setHasMore(response.has_more)
        setNoMatchesReason(response.no_matches_reason)

        // Also fetch full job details for matches
        const jobIds = response.matches.map((m) => m.job_id)
        const jobDetails = await Promise.all(
          jobIds.map((id) => api.getJob(id).catch(() => null))
        )
        setJobs(jobDetails.filter((j): j is Job => j !== null))
      } else {
        const response = await api.getJobs({
          page,
          page_size: 20,
          role_family: roleFamily || undefined,
          seniority: seniority || undefined,
          location_type: locationType || undefined,
        })
        setJobs(response.jobs)
        setTotal(response.total)
        setHasMore(response.has_more)
        setMatches([])
        setNoMatchesReason(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }

  const handleJobClick = async (jobId: string) => {
    if (candidateId) {
      try {
        await api.trackJobClick(jobId, candidateId)
      } catch {
        // Ignore tracking errors
      }
    }
    onJobClick?.(jobId)
  }

  const clearFilters = () => {
    setRoleFamily('')
    setSeniority('')
    setLocationType('')
    setPage(1)
  }

  const hasFilters = roleFamily || seniority || locationType

  return (
    <div>
      {/* Filters */}
      {!showMatches && (
        <div className="mb-4">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <Filter className="w-4 h-4" />
            <span>Filters</span>
            {hasFilters && (
              <span className="bg-[#FF4500] text-white text-xs px-1.5 py-0.5 rounded-full">
                {[roleFamily, seniority, locationType].filter(Boolean).length}
              </span>
            )}
            <ChevronDown
              className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`}
            />
          </button>

          {showFilters && (
            <div className="mt-3 p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Role</label>
                  <select
                    value={roleFamily}
                    onChange={(e) => {
                      setRoleFamily(e.target.value)
                      setPage(1)
                    }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-md text-sm"
                  >
                    <option value="">All roles</option>
                    {Object.entries(ROLE_FAMILY_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">Level</label>
                  <select
                    value={seniority}
                    onChange={(e) => {
                      setSeniority(e.target.value)
                      setPage(1)
                    }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-md text-sm"
                  >
                    <option value="">All levels</option>
                    {Object.entries(SENIORITY_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">Location</label>
                  <select
                    value={locationType}
                    onChange={(e) => {
                      setLocationType(e.target.value)
                      setPage(1)
                    }}
                    className="w-full px-3 py-2 border border-gray-200 rounded-md text-sm"
                  >
                    <option value="">All locations</option>
                    {Object.entries(LOCATION_TYPE_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {hasFilters && (
                <button
                  onClick={clearFilters}
                  className="text-sm text-[#FF4500] hover:underline"
                >
                  Clear filters
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Results header */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-gray-600">
          {loading ? (
            'Loading...'
          ) : total === 0 ? (
            'No jobs found'
          ) : (
            <>
              Showing {jobs.length} of {total} jobs
            </>
          )}
        </p>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-4">
          {error}
        </div>
      )}

      {/* No matches explanation */}
      {noMatchesReason && jobs.length === 0 && !loading && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 mb-4 text-center">
          <p className="text-amber-800 font-medium mb-2">No matches yet</p>
          <p className="text-amber-700 text-sm">{noMatchesReason}</p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-[#FF4500]" />
        </div>
      )}

      {/* Job list */}
      {!loading && jobs.length > 0 && (
        <div className="space-y-4">
          {jobs.map((job) => {
            const match = matches.find((m) => m.job_id === job.id)
            return (
              <JobCard
                key={job.id}
                job={job}
                match={match}
                onJobClick={handleJobClick}
              />
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {!loading && total > 0 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 border border-gray-200 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Previous
          </button>
          <span className="text-gray-600 text-sm">
            Page {page}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasMore}
            className="px-4 py-2 border border-gray-200 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
