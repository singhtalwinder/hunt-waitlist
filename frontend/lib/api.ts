/**
 * API client for Hunt backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Company {
  id: string;
  name: string;
  domain: string | null;
}

export interface Job {
  id: string;
  title: string;
  description: string | null;
  source_url: string;
  role_family: string;
  role_specialization: string | null;
  seniority: string | null;
  location_type: string | null;
  locations: string[] | null;
  skills: string[] | null;
  min_salary: number | null;
  max_salary: number | null;
  employment_type: string | null;
  posted_at: string | null;
  freshness_score: number | null;
  company: Company;
  created_at: string;
}

export interface MatchedJob {
  id: string;
  job_id: string;
  job_title: string;
  company_name: string;
  score: number;
  hard_match: boolean;
  match_reasons: Record<string, string> | null;
  source_url: string;
  posted_at: string | null;
  shown_at: string | null;
  clicked_at: string | null;
  created_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface MatchListResponse {
  matches: MatchedJob[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  no_matches_reason: string | null;
}

export interface CandidateProfile {
  id: string;
  email: string;
  name: string | null;
  role_families: string[] | null;
  seniority: string | null;
  min_salary: number | null;
  locations: string[] | null;
  location_types: string[] | null;
  role_types: string[] | null;
  skills: string[] | null;
  exclusions: string[] | null;
  last_matched_at: string | null;
  created_at: string;
  updated_at: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  protected async fetch<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Request failed' }));
      throw new Error(error.detail || error.message || 'Request failed');
    }

    return response.json();
  }

  // Jobs API
  async getJobs(params?: {
    page?: number;
    page_size?: number;
    role_family?: string;
    seniority?: string;
    location_type?: string;
  }): Promise<JobListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
    if (params?.role_family) searchParams.set('role_family', params.role_family);
    if (params?.seniority) searchParams.set('seniority', params.seniority);
    if (params?.location_type) searchParams.set('location_type', params.location_type);

    const query = searchParams.toString();
    return this.fetch<JobListResponse>(`/api/jobs${query ? `?${query}` : ''}`);
  }

  async getJob(jobId: string): Promise<Job> {
    return this.fetch<Job>(`/api/jobs/${jobId}`);
  }

  async trackJobClick(jobId: string, candidateId: string): Promise<void> {
    await this.fetch(`/api/jobs/${jobId}/click?candidate_id=${candidateId}`, {
      method: 'POST',
    });
  }

  // Candidate API
  async getCandidateMatches(
    candidateId: string,
    params?: { page?: number; page_size?: number; min_score?: number }
  ): Promise<MatchListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
    if (params?.min_score) searchParams.set('min_score', params.min_score.toString());

    const query = searchParams.toString();
    return this.fetch<MatchListResponse>(
      `/api/candidates/${candidateId}/matches${query ? `?${query}` : ''}`
    );
  }

  async getCandidateProfile(candidateId: string): Promise<CandidateProfile> {
    return this.fetch<CandidateProfile>(`/api/candidates/${candidateId}`);
  }

  async updateCandidateProfile(
    candidateId: string,
    updates: Partial<CandidateProfile>
  ): Promise<CandidateProfile> {
    return this.fetch<CandidateProfile>(`/api/candidates/${candidateId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async syncFromWaitlist(data: {
    waitlist_id: string;
    email: string;
    name: string;
    field?: string;
    seniority?: string;
    expected_pay?: number;
    country?: string;
    work_type?: string[];
    role_type?: string[];
  }): Promise<{ status: string; candidate_id: string }> {
    const params = new URLSearchParams();
    params.set('waitlist_id', data.waitlist_id);
    params.set('email', data.email);
    params.set('name', data.name);
    if (data.field) params.set('field', data.field);
    if (data.seniority) params.set('seniority', data.seniority);
    if (data.expected_pay) params.set('expected_pay', data.expected_pay.toString());
    if (data.country) params.set('country', data.country);
    if (data.work_type) data.work_type.forEach(t => params.append('work_type', t));
    if (data.role_type) data.role_type.forEach(t => params.append('role_type', t));

    return this.fetch(`/api/candidates/sync-from-waitlist?${params.toString()}`, {
      method: 'POST',
    });
  }

  // Analytics API
  async getAnalytics(days: number = 30): Promise<AnalyticsData> {
    return this.fetch<AnalyticsData>(`/api/admin/analytics?days=${days}`);
  }
}

// Analytics types
export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface SourceBreakdown {
  name: string;
  value: number;
}

export interface AnalyticsData {
  crawls_per_day: TimeSeriesPoint[];
  new_companies_per_day: TimeSeriesPoint[];
  new_jobs_per_day: TimeSeriesPoint[];
  delisted_jobs_per_day: TimeSeriesPoint[];
  companies_with_new_jobs_per_day: TimeSeriesPoint[];
  sources: SourceBreakdown[];
  totals: {
    total_companies: number;
    total_jobs: number;
    total_crawls_period: number;
    jobs_added_period: number;
    companies_added_period: number;
    jobs_delisted_period: number;
  };
}

// Pipeline types
export interface PipelineProgress {
  [key: string]: unknown;
}

export interface PipelineStatus {
  stage: string;
  started_at: string | null;
  current_step: string;
  progress: PipelineProgress;
  errors: string[];
}

export interface PipelineStats {
  companies: {
    total: number;
    active: number;
    with_ats: number;
    crawled_today: number;
  };
  jobs: {
    total: number;
    active: number;
    with_description: number;
    with_posted_at: number;
    with_embeddings: number;
  };
  discovery_queue: {
    [status: string]: number;
  };
  pipeline_status: PipelineStatus;
}

export interface PipelineRunLog {
  ts: string;
  level: string;
  msg: string;
  run_id?: string;
  data?: Record<string, unknown>;
}

export interface RunningPipelineRun {
  id: string;
  stage: string;
  status: string;
  started_at: string | null;
  processed: number;
  failed: number;
  error: string | null;
  current_step: string | null;
  logs: PipelineRunLog[];
}

export interface PipelineStatusResponse {
  pipeline: PipelineStatus;
  scheduler: {
    running: boolean;
    last_run: string | null;
    next_run: string | null;
    interval_hours: number;
  };
  stats: PipelineStats;
  running_run?: RunningPipelineRun;
}

export interface DiscoverySource {
  name: string;
  description: string;
  enabled: boolean;
}

export interface DiscoveryStats {
  total_runs: number;
  companies_discovered: number;
  last_run: string | null;
  queue_stats: {
    [status: string]: number;
  };
}

export interface CrawlStats {
  total_companies: number;
  with_ats: number;
  crawled_today: number;
  jobs_today: number;
  by_ats: { ats_type: string; count: number }[];
}

export interface EnrichStats {
  total_jobs: number;
  needs_enrichment: number;
  recently_enriched: number;
  by_ats: { ats_type: string; needs_enrichment: number }[];
}

export interface EmbeddingStats {
  total: number;
  with_embeddings: number;
  without_embeddings: number;
}

// Extended API client with pipeline methods
class PipelineApiClient extends ApiClient {
  // Pipeline status
  async getPipelineStatus(): Promise<PipelineStatusResponse> {
    return this.fetch<PipelineStatusResponse>('/api/admin/pipeline/status');
  }

  // Discovery
  async getDiscoverySources(): Promise<DiscoverySource[]> {
    return this.fetch<DiscoverySource[]>('/api/admin/discovery/sources');
  }

  async getDiscoveryStats(): Promise<DiscoveryStats> {
    return this.fetch<DiscoveryStats>('/api/admin/discovery/stats');
  }

  async runDiscovery(sourceNames?: string[]): Promise<{ status: string; message: string }> {
    const params = sourceNames?.length ? `?source_names=${sourceNames.join('&source_names=')}` : '';
    return this.fetch(`/api/admin/discovery/run${params}`, { method: 'POST' });
  }

  async processDiscoveryQueue(limit: number = 100): Promise<{ status: string; processed: number }> {
    return this.fetch(`/api/admin/discovery/process-queue?limit=${limit}`, { method: 'POST' });
  }

  // Crawl
  async getCrawlStats(): Promise<CrawlStats> {
    return this.fetch<CrawlStats>('/api/admin/crawl/stats');
  }

  async runCrawl(params?: { ats_type?: string; limit?: number }): Promise<{ status: string; message: string }> {
    const searchParams = new URLSearchParams();
    if (params?.ats_type) searchParams.set('ats_type', params.ats_type);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    const query = searchParams.toString();
    return this.fetch(`/api/admin/pipeline/crawl${query ? `?${query}` : ''}`, { method: 'POST' });
  }

  // Enrich
  async getEnrichStats(): Promise<EnrichStats> {
    return this.fetch<EnrichStats>('/api/admin/enrich/stats');
  }

  async runEnrich(params?: { ats_type?: string; limit?: number }): Promise<{ status: string; message: string }> {
    const searchParams = new URLSearchParams();
    if (params?.ats_type) searchParams.set('ats_type', params.ats_type);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    const query = searchParams.toString();
    return this.fetch(`/api/admin/pipeline/enrich${query ? `?${query}` : ''}`, { method: 'POST' });
  }

  // Embeddings
  async getEmbeddingStats(): Promise<EmbeddingStats> {
    return this.fetch<EmbeddingStats>('/api/admin/embeddings/stats');
  }

  async runEmbeddings(batchSize: number = 200): Promise<{ status: string; message: string }> {
    return this.fetch(`/api/admin/pipeline/embeddings?batch_size=${batchSize}`, { method: 'POST' });
  }

  // Full pipeline
  async runFullPipeline(params?: {
    skip_discovery?: boolean;
    skip_crawl?: boolean;
    skip_enrichment?: boolean;
    skip_embeddings?: boolean;
  }): Promise<{ status: string; message: string }> {
    const searchParams = new URLSearchParams();
    if (params?.skip_discovery) searchParams.set('skip_discovery', 'true');
    if (params?.skip_crawl) searchParams.set('skip_crawl', 'true');
    if (params?.skip_enrichment) searchParams.set('skip_enrichment', 'true');
    if (params?.skip_embeddings) searchParams.set('skip_embeddings', 'true');
    const query = searchParams.toString();
    return this.fetch(`/api/admin/pipeline/run${query ? `?${query}` : ''}`, { method: 'POST' });
  }

  // Scheduler
  async startScheduler(intervalHours: number = 6): Promise<{ status: string }> {
    return this.fetch(`/api/admin/scheduler/start?interval_hours=${intervalHours}`, { method: 'POST' });
  }

  async stopScheduler(): Promise<{ status: string }> {
    return this.fetch('/api/admin/scheduler/stop', { method: 'POST' });
  }
}

export const api = new PipelineApiClient();
