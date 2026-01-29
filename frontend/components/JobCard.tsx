'use client'

import { ExternalLink, MapPin, Building2, Clock, Briefcase } from 'lucide-react'
import { Job, MatchedJob } from '@/lib/api'
import {
  ROLE_FAMILY_LABELS,
  SENIORITY_LABELS,
  LOCATION_TYPE_LABELS,
  formatSalary,
  formatTimeAgo,
  getScoreBadge,
  RoleFamily,
  Seniority,
  LocationType,
} from '@/lib/types'

interface JobCardProps {
  job: Job
  match?: MatchedJob
  onJobClick?: (jobId: string) => void
}

export function JobCard({ job, match, onJobClick }: JobCardProps) {
  const handleClick = () => {
    if (onJobClick) {
      onJobClick(job.id)
    }
    window.open(job.source_url, '_blank')
  }

  const scoreBadge = match ? getScoreBadge(match.score) : null

  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:border-[#FF4500] hover:shadow-sm transition-all bg-white">
      {/* Header */}
      <div className="flex justify-between items-start gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 text-lg truncate">
            {job.title}
          </h3>
          <div className="flex items-center gap-2 text-gray-600 mt-1">
            <Building2 className="w-4 h-4 shrink-0" />
            <span className="truncate">{job.company.name}</span>
          </div>
        </div>

        {scoreBadge && (
          <span className={`${scoreBadge.color} text-white text-xs px-2 py-1 rounded-full shrink-0`}>
            {scoreBadge.label}
          </span>
        )}
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-3">
        {job.seniority && (
          <span className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded">
            {SENIORITY_LABELS[job.seniority as Seniority] || job.seniority}
          </span>
        )}
        {job.role_family && (
          <span className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded">
            {ROLE_FAMILY_LABELS[job.role_family as RoleFamily] || job.role_family}
          </span>
        )}
        {job.location_type && (
          <span className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded">
            {LOCATION_TYPE_LABELS[job.location_type as LocationType] || job.location_type}
          </span>
        )}
        {formatSalary(job.min_salary, job.max_salary) && (
          <span className="bg-green-50 text-green-700 text-xs px-2 py-1 rounded">
            {formatSalary(job.min_salary, job.max_salary)}
          </span>
        )}
      </div>

      {/* Location */}
      {job.locations && job.locations.length > 0 && (
        <div className="flex items-center gap-2 text-gray-500 text-sm mb-3">
          <MapPin className="w-4 h-4 shrink-0" />
          <span className="truncate">{job.locations.join(', ')}</span>
        </div>
      )}

      {/* Skills */}
      {job.skills && job.skills.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {job.skills.slice(0, 5).map((skill) => (
            <span
              key={skill}
              className="bg-orange-50 text-orange-700 text-xs px-2 py-0.5 rounded"
            >
              {skill}
            </span>
          ))}
          {job.skills.length > 5 && (
            <span className="text-gray-400 text-xs px-2 py-0.5">
              +{job.skills.length - 5} more
            </span>
          )}
        </div>
      )}

      {/* Match reasons */}
      {match?.match_reasons && Object.keys(match.match_reasons).length > 0 && (
        <div className="border-t border-gray-100 pt-3 mb-3">
          <p className="text-xs text-gray-500 mb-1">Why this match:</p>
          <ul className="text-sm text-gray-600 space-y-0.5">
            {Object.values(match.match_reasons).slice(0, 3).map((reason, i) => (
              <li key={i} className="flex items-start gap-1">
                <span className="text-green-500 shrink-0">✓</span>
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <div className="flex items-center gap-1 text-gray-400 text-sm">
          <Clock className="w-3 h-3" />
          <span>{formatTimeAgo(job.posted_at)}</span>
        </div>

        <button
          onClick={handleClick}
          className="flex items-center gap-1 bg-[#FF4500] hover:bg-[#E63E00] text-white text-sm px-3 py-1.5 rounded-md transition-colors"
        >
          View Job
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}
