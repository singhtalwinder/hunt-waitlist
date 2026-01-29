'use client'

import { useState, useEffect, useCallback } from 'react'
import { 
  Loader2, 
  Play, 
  Search, 
  Download, 
  Sparkles, 
  Database,
  RefreshCw,
  CheckCircle2,
  Clock,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Pause,
  Settings,
  ArrowRight,
  Activity
} from 'lucide-react'
import { Logo } from '@/components/Logo'
import { api, PipelineStatusResponse, RunningPipelineRun, OperationStatus } from '@/lib/api'

type StageType = 'discovery' | 'crawl' | 'enrich' | 'embeddings'

// Helper to check if an operation is running for a given stage
function isStageRunning(
  stageId: StageType,
  runningOps: Record<string, OperationStatus>,
  runningRuns: RunningPipelineRun[]
): boolean {
  // Check registry operations (e.g., "discovery", "crawl_greenhouse", "crawl_all", "embeddings")
  for (const opType of Object.keys(runningOps)) {
    if (opType === stageId) return true
    if (opType.startsWith(`${stageId}_`)) return true
    if (opType === 'full_pipeline') return true
  }
  
  // Check database pipeline runs
  for (const run of runningRuns) {
    if (run.status !== 'running') continue
    if (run.stage === stageId) return true
    if (run.stage.startsWith(`${stageId}_`)) return true
    if (run.stage === 'detect_ats' && stageId === 'discovery') return true
    if (run.stage === 'custom_crawl' && stageId === 'crawl') return true
  }
  
  return false
}

// Get all running operations for a stage
function getStageOperations(
  stageId: StageType,
  runningOps: Record<string, OperationStatus>,
  runningRuns: RunningPipelineRun[]
): { ops: OperationStatus[], runs: RunningPipelineRun[] } {
  const ops: OperationStatus[] = []
  const runs: RunningPipelineRun[] = []
  
  // Check registry operations
  for (const [opType, op] of Object.entries(runningOps)) {
    if (opType === stageId || opType.startsWith(`${stageId}_`)) {
      ops.push(op)
    }
  }
  
  // Check database pipeline runs
  for (const run of runningRuns) {
    if (run.status !== 'running') continue
    if (run.stage === stageId || run.stage.startsWith(`${stageId}_`)) {
      runs.push(run)
    } else if (run.stage === 'detect_ats' && stageId === 'discovery') {
      runs.push(run)
    } else if (run.stage === 'custom_crawl' && stageId === 'crawl') {
      runs.push(run)
    }
  }
  
  return { ops, runs }
}

interface StageConfig {
  id: StageType
  name: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  bgColor: string
}

const STAGES: StageConfig[] = [
  {
    id: 'discovery',
    name: 'Discovery',
    description: 'Find new companies from various sources',
    icon: Search,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  {
    id: 'crawl',
    name: 'Crawl',
    description: 'Extract jobs from company career pages',
    icon: Download,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  {
    id: 'enrich',
    name: 'Enrich',
    description: 'Extract details from job descriptions',
    icon: Sparkles,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  {
    id: 'embeddings',
    name: 'Embeddings',
    description: 'Generate AI embeddings for matching',
    icon: Database,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
]

function formatDuration(startedAt: string): string {
  const start = new Date(startedAt)
  const now = new Date()
  const seconds = Math.floor((now.getTime() - start.getTime()) / 1000)
  
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

function formatNumber(num: number): string {
  return num.toLocaleString()
}

function StageCard({ 
  stage, 
  status, 
  isExpanded,
  onToggle,
  onRun,
  isRunning,
}: { 
  stage: StageConfig
  status: PipelineStatusResponse | null
  isExpanded: boolean
  onToggle: () => void
  onRun: () => void
  isRunning: boolean
}) {
  const Icon = stage.icon
  
  // Get running operations for this stage (supports concurrent operations)
  const runningOps = status?.running_operations?.running_operations || {}
  const runningRuns = status?.running_runs || []
  const isCurrentStage = isStageRunning(stage.id, runningOps, runningRuns)
  const { ops: stageOps, runs: stageRuns } = getStageOperations(stage.id, runningOps, runningRuns)
  
  // Count concurrent operations for this stage
  const concurrentCount = stageOps.length + stageRuns.length
  
  const progress = status?.pipeline?.progress?.[stage.id] as Record<string, unknown> | undefined
  
  // Get stats for this stage
  const getStageStats = () => {
    if (!status?.stats) return null
    
    switch (stage.id) {
      case 'discovery':
        return {
          main: status.stats.companies?.total || 0,
          mainLabel: 'Companies',
          sub: status.stats.discovery_queue?.completed || 0,
          subLabel: 'Queue Processed',
          pending: (status.stats.discovery_queue?.pending || 0) + (status.stats.discovery_queue?.processing || 0),
          pendingLabel: 'In Queue',
        }
      case 'crawl':
        return {
          main: status.stats.jobs?.total || 0,
          mainLabel: 'Total Jobs',
          sub: status.stats.companies?.crawled_today || 0,
          subLabel: 'Crawled Today',
          pending: status.stats.companies?.with_ats || 0,
          pendingLabel: 'With ATS',
        }
      case 'enrich':
        return {
          main: status.stats.jobs?.with_description || 0,
          mainLabel: 'Enriched',
          sub: status.stats.jobs?.total || 0,
          subLabel: 'Total Jobs',
          pending: (status.stats.jobs?.total || 0) - (status.stats.jobs?.with_description || 0),
          pendingLabel: 'Needs Enrichment',
        }
      case 'embeddings':
        return {
          main: status.stats.jobs?.with_embeddings || 0,
          mainLabel: 'With Embeddings',
          sub: status.stats.jobs?.total || 0,
          subLabel: 'Total Jobs',
          pending: (status.stats.jobs?.total || 0) - (status.stats.jobs?.with_embeddings || 0),
          pendingLabel: 'Without Embeddings',
        }
      default:
        return null
    }
  }
  
  const stats = getStageStats()
  const percentage = stats && stats.sub > 0 
    ? Math.round((stats.main / stats.sub) * 100) 
    : 0
  
  return (
    <div className={`bg-white rounded-xl border transition-all ${
      isCurrentStage 
        ? 'border-[#FF4500] ring-2 ring-[#FF4500]/20' 
        : 'border-gray-200 hover:border-gray-300'
    }`}>
      {/* Header */}
      <div 
        className="p-4 cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 ${stage.bgColor} ${stage.color} rounded-lg flex items-center justify-center`}>
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-gray-900">{stage.name}</h3>
                {isCurrentStage && (
                  <span className="flex items-center gap-1 text-xs font-medium text-[#FF4500] bg-orange-50 px-2 py-0.5 rounded-full">
                    <Activity className="w-3 h-3 animate-pulse" />
                    Running{concurrentCount > 1 ? ` (${concurrentCount})` : ''}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500">{stage.description}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {stats && (
              <div className="text-right mr-4">
                <div className="text-xl font-bold text-gray-900">{formatNumber(stats.main)}</div>
                <div className="text-xs text-gray-500">{stats.mainLabel}</div>
              </div>
            )}
            
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRun()
              }}
              disabled={isRunning || isCurrentStage}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isRunning || isCurrentStage
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-[#FF4500] hover:bg-[#E63E00] text-white'
              }`}
            >
              {isRunning || isCurrentStage ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Run
            </button>
            
            {isExpanded ? (
              <ChevronUp className="w-5 h-5 text-gray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-gray-400" />
            )}
          </div>
        </div>
        
        {/* Progress bar */}
        {stats && stats.sub > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>{percentage}% complete</span>
              <span>{formatNumber(stats.pending)} {stats.pendingLabel?.toLowerCase()}</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div 
                className={`h-2 rounded-full transition-all ${
                  isCurrentStage ? 'bg-[#FF4500] animate-pulse' : stage.bgColor.replace('bg-', 'bg-').replace('-50', '-500')
                }`}
                style={{ width: `${Math.min(percentage, 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>
      
      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-gray-100 p-4 bg-gray-50/50">
          {/* Current progress if running - show ALL concurrent operations */}
          {isCurrentStage && (stageOps.length > 0 || stageRuns.length > 0) && (
            <div className="mb-4 space-y-3">
              {/* Show registry operations (from OperationRegistry) */}
              {stageOps.map((op, i) => (
                <div key={`op-${i}`} className="p-3 bg-orange-50 border border-orange-100 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-[#FF4500]">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="font-semibold">{op.operation_type}</span>
                      {op.current_step && <span className="text-orange-600">- {op.current_step}</span>}
                    </div>
                    {op.started_at && (
                      <div className="text-xs text-orange-600">
                        {formatDuration(op.started_at)}
                      </div>
                    )}
                  </div>
                  
                  {/* Progress from operation */}
                  {op.progress && Object.keys(op.progress).length > 0 && (
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {Object.entries(op.progress).map(([key, value]) => (
                        <div key={key} className="bg-white rounded-lg p-2 border border-orange-100">
                          <div className="text-lg font-bold text-gray-900">
                            {typeof value === 'number' ? formatNumber(value) : String(value)}
                          </div>
                          <div className="text-xs text-gray-500 capitalize">
                            {key.replace(/_/g, ' ')}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              
              {/* Show database pipeline runs */}
              {stageRuns.map((run, i) => (
                <div key={`run-${i}`} className="p-3 bg-orange-50 border border-orange-100 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-medium text-[#FF4500]">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="font-semibold">{run.stage}</span>
                      {run.current_step && <span className="text-orange-600">- {run.current_step}</span>}
                    </div>
                    {run.started_at && (
                      <div className="text-xs text-orange-600">
                        {formatDuration(run.started_at)}
                      </div>
                    )}
                  </div>
                  
                  {/* Progress from database run */}
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-white rounded-lg p-2 border border-orange-100">
                      <div className="text-lg font-bold text-green-600">
                        {formatNumber(run.processed)}
                      </div>
                      <div className="text-xs text-gray-500">Processed</div>
                    </div>
                    <div className="bg-white rounded-lg p-2 border border-orange-100">
                      <div className="text-lg font-bold text-gray-600">
                        {formatNumber(run.failed)}
                      </div>
                      <div className="text-xs text-gray-500">Failed</div>
                    </div>
                  </div>
                  
                  {/* Recent logs from running run */}
                  {run.logs && run.logs.length > 0 && (
                    <div className="mt-3 max-h-32 overflow-y-auto">
                      <div className="text-xs font-medium text-gray-500 mb-2">Recent Activity</div>
                      <div className="space-y-1">
                        {run.logs.slice(-5).reverse().map((log, j) => (
                          <div 
                            key={j} 
                            className={`text-xs px-2 py-1 rounded ${
                              log.level === 'warn' || log.level === 'error' 
                                ? 'bg-red-50 text-red-700' 
                                : 'bg-white text-gray-600'
                            }`}
                          >
                            {log.msg}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {/* Fallback to old orchestrator progress if no specific ops/runs */}
              {stageOps.length === 0 && stageRuns.length === 0 && progress && (
                <div className="p-3 bg-orange-50 border border-orange-100 rounded-lg">
                  <div className="flex items-center gap-2 text-sm font-medium text-[#FF4500]">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {status?.pipeline?.current_step || 'Running...'}
                  </div>
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {Object.entries(progress).map(([key, value]) => (
                      <div key={key} className="bg-white rounded-lg p-2 border border-orange-100">
                        <div className="text-lg font-bold text-gray-900">
                          {typeof value === 'number' ? formatNumber(value) : String(value)}
                        </div>
                        <div className="text-xs text-gray-500 capitalize">
                          {key.replace(/_/g, ' ')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Stats grid */}
          {stats && (
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-2xl font-bold text-gray-900">{formatNumber(stats.main)}</div>
                <div className="text-sm text-gray-500">{stats.mainLabel}</div>
              </div>
              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-2xl font-bold text-gray-900">{formatNumber(stats.sub)}</div>
                <div className="text-sm text-gray-500">{stats.subLabel}</div>
              </div>
              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className={`text-2xl font-bold ${stats.pending > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                  {formatNumber(stats.pending)}
                </div>
                <div className="text-sm text-gray-500">{stats.pendingLabel}</div>
              </div>
            </div>
          )}
          
          {/* Errors if any */}
          {status?.pipeline?.errors && status.pipeline.errors.length > 0 && isCurrentStage && (
            <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg">
              <div className="flex items-center gap-2 text-sm font-medium text-red-700 mb-2">
                <AlertCircle className="w-4 h-4" />
                Errors
              </div>
              <ul className="text-sm text-red-600 space-y-1">
                {status.pipeline.errors.slice(0, 5).map((err, i) => (
                  <li key={i} className="truncate">{err}</li>
                ))}
                {status.pipeline.errors.length > 5 && (
                  <li className="text-red-500">...and {status.pipeline.errors.length - 5} more</li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function PipelinePage() {
  const [status, setStatus] = useState<PipelineStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedStage, setExpandedStage] = useState<StageType | null>(null)
  const [runningStage, setRunningStage] = useState<StageType | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  
  const loadStatus = useCallback(async () => {
    try {
      const data = await api.getPipelineStatus()
      setStatus(data)
      setError(null)
      
      // Auto-expand if a stage is running
      if (!expandedStage) {
        const runningOps = data.running_operations?.running_operations || {}
        const runningRuns = data.running_runs || []
        
        // Find first running stage
        for (const stageId of ['discovery', 'crawl', 'enrich', 'embeddings'] as StageType[]) {
          if (isStageRunning(stageId, runningOps, runningRuns)) {
            setExpandedStage(stageId)
            break
          }
        }
      }
    } catch (err) {
      console.error('Failed to load pipeline status:', err)
      setError(err instanceof Error ? err.message : 'Failed to load status')
    } finally {
      setLoading(false)
    }
  }, [expandedStage])
  
  useEffect(() => {
    loadStatus()
  }, [loadStatus])
  
  // Auto-refresh when pipeline is running or auto-refresh is enabled
  useEffect(() => {
    if (!autoRefresh) return
    
    const runningOps = status?.running_operations?.running_operations || {}
    const runningRuns = status?.running_runs || []
    const hasRunningOps = Object.keys(runningOps).length > 0 || runningRuns.some(r => r.status === 'running')
    const interval = hasRunningOps ? 2000 : 10000 // 2s when running, 10s otherwise
    
    const timer = setInterval(loadStatus, interval)
    return () => clearInterval(timer)
  }, [autoRefresh, status?.running_operations, status?.running_runs, loadStatus])
  
  const handleRunStage = async (stage: StageType) => {
    setRunningStage(stage)
    try {
      switch (stage) {
        case 'discovery':
          await api.runDiscovery()
          break
        case 'crawl':
          await api.runCrawl({ limit: 100 })
          break
        case 'enrich':
          await api.runEnrich({ limit: 500 })
          break
        case 'embeddings':
          await api.runEmbeddings(200)
          break
      }
      setExpandedStage(stage)
      // Reload status immediately
      await loadStatus()
    } catch (err) {
      console.error(`Failed to run ${stage}:`, err)
      setError(err instanceof Error ? err.message : `Failed to run ${stage}`)
    } finally {
      setRunningStage(null)
    }
  }
  
  const handleRunFullPipeline = async () => {
    setRunningStage('discovery')
    try {
      await api.runFullPipeline()
      await loadStatus()
    } catch (err) {
      console.error('Failed to run pipeline:', err)
      setError(err instanceof Error ? err.message : 'Failed to run pipeline')
    } finally {
      setRunningStage(null)
    }
  }
  
  // Check if any operations are running
  const runningOps = status?.running_operations?.running_operations || {}
  const runningRuns = status?.running_runs || []
  const runningOpCount = Object.keys(runningOps).length
  const runningRunCount = runningRuns.filter(r => r.status === 'running').length
  const isRunning = runningOpCount > 0 || runningRunCount > 0
  const totalRunningCount = runningOpCount + runningRunCount
  
  if (loading && !status) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#FF4500] mx-auto mb-4" />
          <p className="text-gray-600">Loading pipeline status...</p>
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
            <span className="ml-3 text-sm font-medium text-gray-500">Pipeline</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg transition-colors ${
                autoRefresh 
                  ? 'bg-green-50 text-green-700 border border-green-200' 
                  : 'bg-gray-100 text-gray-600 border border-gray-200'
              }`}
            >
              {autoRefresh ? (
                <>
                  <Activity className="w-4 h-4" />
                  Live
                </>
              ) : (
                <>
                  <Pause className="w-4 h-4" />
                  Paused
                </>
              )}
            </button>
            
            <button
              onClick={loadStatus}
              disabled={loading}
              className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            
            <a
              href="/dashboard"
              className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              Dashboard
            </a>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
            <button 
              onClick={() => setError(null)} 
              className="ml-auto text-red-500 hover:text-red-700"
            >
              Dismiss
            </button>
          </div>
        )}
        
        {/* Pipeline overview */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Data Pipeline</h1>
              <p className="text-gray-600">
                {isRunning 
                  ? `Running: ${status?.pipeline?.current_step || status?.pipeline?.stage}`
                  : 'Manage and monitor the job data pipeline'
                }
              </p>
            </div>
            
            <button
              onClick={handleRunFullPipeline}
              disabled={runningOps['full_pipeline'] !== undefined || runningStage !== null}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-colors ${
                runningOps['full_pipeline'] !== undefined || runningStage !== null
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-[#FF4500] hover:bg-[#E63E00] text-white'
              }`}
            >
              {runningStage || runningOps['full_pipeline'] ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Play className="w-5 h-5" />
              )}
              Run Full Pipeline
            </button>
          </div>
          
          {/* Status banner when running - shows all concurrent operations */}
          {isRunning && (
            <div className="bg-gradient-to-r from-orange-500 to-[#FF4500] text-white rounded-xl p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <Loader2 className="w-6 h-6 animate-spin" />
                  </div>
                  <div>
                    <div className="font-semibold">
                      {totalRunningCount > 1 
                        ? `${totalRunningCount} operations running concurrently`
                        : Object.values(runningOps)[0]?.current_step || 
                          runningRuns.find(r => r.status === 'running')?.current_step ||
                          'Running...'
                      }
                    </div>
                    <div className="text-sm text-orange-100">
                      {Object.keys(runningOps).length > 0 && (
                        <span>Operations: {Object.keys(runningOps).join(', ')}</span>
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Show aggregated progress */}
                <div className="flex gap-6">
                  {/* Sum up processed/failed from all running runs */}
                  {runningRuns.filter(r => r.status === 'running').length > 0 && (
                    <>
                      <div className="text-right">
                        <div className="text-2xl font-bold">
                          {formatNumber(runningRuns.reduce((sum, r) => sum + (r.processed || 0), 0))}
                        </div>
                        <div className="text-xs text-orange-100">Processed</div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold">
                          {formatNumber(runningRuns.reduce((sum, r) => sum + (r.failed || 0), 0))}
                        </div>
                        <div className="text-xs text-orange-100">Failed</div>
                      </div>
                    </>
                  )}
                  
                  {/* Show count of concurrent ops */}
                  {totalRunningCount > 1 && (
                    <div className="text-right">
                      <div className="text-2xl font-bold">{totalRunningCount}</div>
                      <div className="text-xs text-orange-100">Concurrent Ops</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
          
          {/* Pipeline flow visualization */}
          <div className="hidden sm:flex items-center justify-center mb-8 py-4">
            {STAGES.map((stage, index) => {
              const isActive = isStageRunning(stage.id, runningOps, runningRuns)
              const { ops, runs } = getStageOperations(stage.id, runningOps, runningRuns)
              const concurrentCount = ops.length + runs.length
              const Icon = stage.icon
              return (
                <div key={stage.id} className="flex items-center">
                  <div 
                    className={`flex items-center gap-2 px-4 py-2 rounded-full transition-all ${
                      isActive 
                        ? 'bg-[#FF4500] text-white' 
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm font-medium">{stage.name}</span>
                    {isActive && (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        {concurrentCount > 1 && (
                          <span className="text-xs bg-white/20 px-1.5 py-0.5 rounded-full">
                            {concurrentCount}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                  {index < STAGES.length - 1 && (
                    <ArrowRight className="w-5 h-5 mx-2 text-gray-300" />
                  )}
                </div>
              )
            })}
          </div>
        </div>
        
        {/* Stage cards */}
        <div className="space-y-4">
          {STAGES.map((stage) => (
            <StageCard
              key={stage.id}
              stage={stage}
              status={status}
              isExpanded={expandedStage === stage.id}
              onToggle={() => setExpandedStage(expandedStage === stage.id ? null : stage.id)}
              onRun={() => handleRunStage(stage.id)}
              isRunning={runningStage === stage.id}
            />
          ))}
        </div>
        
        {/* Scheduler section */}
        {status?.scheduler && (
          <div className="mt-8 bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                  <Clock className="w-5 h-5 text-gray-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Scheduler</h3>
                  <p className="text-sm text-gray-500">
                    {status.scheduler.running 
                      ? `Running every ${status.scheduler.interval_hours}h`
                      : 'Automatic pipeline scheduling'
                    }
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                {status.scheduler.next_run && (
                  <div className="text-sm text-gray-500">
                    Next run: {new Date(status.scheduler.next_run).toLocaleString()}
                  </div>
                )}
                
                <button
                  onClick={async () => {
                    try {
                      if (status.scheduler.running) {
                        await api.stopScheduler()
                      } else {
                        await api.startScheduler(6)
                      }
                      await loadStatus()
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Scheduler action failed')
                    }
                  }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    status.scheduler.running
                      ? 'bg-red-50 text-red-700 hover:bg-red-100'
                      : 'bg-green-50 text-green-700 hover:bg-green-100'
                  }`}
                >
                  {status.scheduler.running ? (
                    <>
                      <Pause className="w-4 h-4" />
                      Stop
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Start
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
