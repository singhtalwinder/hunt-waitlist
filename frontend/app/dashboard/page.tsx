'use client'

import { useState, useEffect } from 'react'
import { Loader2, TrendingUp, TrendingDown, Building2, Briefcase, RefreshCw, MinusCircle, Database } from 'lucide-react'
import { Logo } from '@/components/Logo'
import { api, AnalyticsData, TimeSeriesPoint } from '@/lib/api'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

// Colors for charts
const COLORS = ['#FF4500', '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#6366F1', '#14B8A6']
const CHART_ORANGE = '#FF4500'
const CHART_BLUE = '#3B82F6'
const CHART_GREEN = '#10B981'
const CHART_RED = '#EF4444'
const CHART_PURPLE = '#8B5CF6'

// Format date for display
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// Prepare time series data with formatted dates
function prepareTimeSeriesData(data: TimeSeriesPoint[]) {
  return data.map(point => ({
    ...point,
    dateFormatted: formatDate(point.date),
  }))
}

// Stat card component
function StatCard({ 
  title, 
  value, 
  subtitle, 
  icon: Icon, 
  trend,
  color = 'orange' 
}: { 
  title: string
  value: number | string
  subtitle?: string
  icon: React.ComponentType<{ className?: string }>
  trend?: 'up' | 'down' | 'neutral'
  color?: 'orange' | 'blue' | 'green' | 'red' | 'purple'
}) {
  const colorClasses = {
    orange: 'bg-orange-50 text-primary',
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 lg:p-6">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs lg:text-sm font-medium text-gray-500">{title}</p>
          <p className="text-2xl lg:text-3xl font-bold text-gray-900 mt-1">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
              {trend === 'up' && <TrendingUp className="w-3 h-3 text-green-500" />}
              {trend === 'down' && <TrendingDown className="w-3 h-3 text-red-500" />}
              {subtitle}
            </p>
          )}
        </div>
        <div className={`w-10 h-10 lg:w-12 lg:h-12 ${colorClasses[color]} rounded-lg flex items-center justify-center flex-shrink-0`}>
          <Icon className="w-5 h-5 lg:w-6 lg:h-6" />
        </div>
      </div>
    </div>
  )
}

// Chart container with title
function ChartCard({ 
  title, 
  subtitle,
  children 
}: { 
  title: string
  subtitle?: string
  children: React.ReactNode 
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 lg:p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      <div className="h-64 lg:h-80">
        {children}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)

  useEffect(() => {
    loadAnalytics()
  }, [days])

  const loadAnalytics = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await api.getAnalytics(days)
      setAnalytics(data)
    } catch (err) {
      console.error('Failed to load analytics:', err)
      setError(err instanceof Error ? err.message : 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }

  if (loading && !analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-gray-600">Loading analytics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-lg shadow-sm p-8 max-w-md text-center">
          <div className="flex justify-center mb-4">
            <Logo size={48} />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Dashboard</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={loadAnalytics}
            className="inline-block bg-primary hover:bg-orange-600 text-white font-medium px-6 py-3 rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  if (!analytics) return null

  // Prepare chart data
  const crawlsData = prepareTimeSeriesData(analytics.crawls_per_day)
  const newCompaniesData = prepareTimeSeriesData(analytics.new_companies_per_day)
  const newJobsData = prepareTimeSeriesData(analytics.new_jobs_per_day)
  const delistedJobsData = prepareTimeSeriesData(analytics.delisted_jobs_per_day)
  const companiesWithNewJobsData = prepareTimeSeriesData(analytics.companies_with_new_jobs_per_day)

  // Combined chart for jobs (new + existing companies with new jobs)
  const combinedJobsData = newJobsData.map((point, i) => ({
    ...point,
    newJobs: point.value,
    existingCompanyJobs: companiesWithNewJobsData[i]?.value || 0,
  }))

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Logo size={28} />
            <span
              className="text-xl font-bold text-black font-hunt"
            >
              hunt<span className="text-primary">.</span>
            </span>
            <span className="ml-3 text-sm font-medium text-gray-500">Analytics</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Time range selector */}
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
            </select>

            <button
              onClick={loadAnalytics}
              disabled={loading}
              className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Summary stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <StatCard
            title="Total Companies"
            value={analytics.totals.total_companies}
            subtitle={`+${analytics.totals.companies_added_period} this period`}
            icon={Building2}
            trend="up"
            color="orange"
          />
          <StatCard
            title="Total Jobs"
            value={analytics.totals.total_jobs}
            subtitle={`+${analytics.totals.jobs_added_period} this period`}
            icon={Briefcase}
            trend="up"
            color="blue"
          />
          <StatCard
            title="Crawls"
            value={analytics.totals.total_crawls_period}
            subtitle={`Last ${days} days`}
            icon={RefreshCw}
            color="green"
          />
          <StatCard
            title="New Companies"
            value={analytics.totals.companies_added_period}
            subtitle={`Last ${days} days`}
            icon={TrendingUp}
            trend="up"
            color="purple"
          />
          <StatCard
            title="New Jobs"
            value={analytics.totals.jobs_added_period}
            subtitle={`Last ${days} days`}
            icon={TrendingUp}
            trend="up"
            color="blue"
          />
          <StatCard
            title="Jobs Delisted"
            value={analytics.totals.jobs_delisted_period}
            subtitle={`Last ${days} days`}
            icon={MinusCircle}
            trend="down"
            color="red"
          />
        </div>

        {/* Charts grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Crawls over time */}
          <ChartCard title="Crawls Over Time" subtitle={`Daily crawl activity for last ${days} days`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={crawlsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="dateFormatted" 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke={CHART_GREEN}
                  fill={CHART_GREEN}
                  fillOpacity={0.2}
                  name="Crawls"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* New Companies over time */}
          <ChartCard title="New Companies Discovered" subtitle={`Companies added to the system per day`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={newCompaniesData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="dateFormatted" 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                />
                <Bar 
                  dataKey="value" 
                  fill={CHART_ORANGE}
                  radius={[4, 4, 0, 0]}
                  name="New Companies"
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* New Jobs over time */}
          <ChartCard title="New Jobs Added" subtitle={`Jobs extracted from crawls per day`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={newJobsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="dateFormatted" 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke={CHART_BLUE}
                  fill={CHART_BLUE}
                  fillOpacity={0.2}
                  name="New Jobs"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Existing Companies with New Jobs */}
          <ChartCard title="Existing Companies with New Jobs" subtitle={`Previously known companies that posted new jobs`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={companiesWithNewJobsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="dateFormatted" 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                />
                <Bar 
                  dataKey="value" 
                  fill={CHART_PURPLE}
                  radius={[4, 4, 0, 0]}
                  name="Companies"
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Jobs Delisted */}
          <ChartCard title="Jobs Delisted" subtitle={`Jobs that were marked as inactive/filled`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={delistedJobsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="dateFormatted" 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                />
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke={CHART_RED}
                  fill={CHART_RED}
                  fillOpacity={0.2}
                  name="Delisted Jobs"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Sources Breakdown */}
          <ChartCard title="Companies by Source" subtitle={`Discovery source distribution`}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics.sources}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                  labelLine={{ stroke: '#999', strokeWidth: 1 }}
                >
                  {analytics.sources.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                  formatter={(value) => [(value ?? 0).toLocaleString(), 'Companies']}
                />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Combined view: New Jobs vs Existing Companies Adding Jobs */}
        <div className="mb-8">
          <ChartCard 
            title="Job Growth Analysis" 
            subtitle={`Comparison of total new jobs vs jobs from existing companies`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={combinedJobsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="dateFormatted" 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickLine={false}
                  axisLine={{ stroke: '#e5e5e5' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'white', 
                    border: '1px solid #e5e5e5',
                    borderRadius: '8px',
                    fontSize: '14px'
                  }}
                />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="newJobs" 
                  stroke={CHART_BLUE}
                  strokeWidth={2}
                  dot={false}
                  name="Total New Jobs"
                />
                <Line 
                  type="monotone" 
                  dataKey="existingCompanyJobs" 
                  stroke={CHART_PURPLE}
                  strokeWidth={2}
                  dot={false}
                  name="Existing Companies Adding Jobs"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Sources table */}
        {analytics.sources.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 lg:p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Discovery Sources</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-500">Source</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-500">Companies</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-gray-500">Share</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-500">Distribution</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.sources.map((source, i) => {
                    const total = analytics.sources.reduce((sum, s) => sum + s.value, 0)
                    const percentage = total > 0 ? (source.value / total) * 100 : 0
                    
                    return (
                      <tr key={source.name} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-3 h-3 rounded-full" 
                              style={{ backgroundColor: COLORS[i % COLORS.length] }}
                            />
                            <span className="font-medium text-gray-900">{source.name}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right text-gray-600">
                          {source.value.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-gray-600">
                          {percentage.toFixed(1)}%
                        </td>
                        <td className="py-3 px-4">
                          <div className="w-full bg-gray-100 rounded-full h-2">
                            <div 
                              className="h-2 rounded-full transition-all"
                              style={{ 
                                width: `${percentage}%`,
                                backgroundColor: COLORS[i % COLORS.length]
                              }}
                            />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
