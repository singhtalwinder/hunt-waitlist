/**
 * Shared types for Hunt frontend
 */

export type RoleFamily =
  | 'software_engineering'
  | 'infrastructure'
  | 'data'
  | 'product'
  | 'design'
  | 'engineering_management'
  | 'sales'
  | 'marketing'
  | 'customer_success'
  | 'operations'
  | 'people'
  | 'finance'
  | 'legal'
  | 'other';

export type Seniority =
  | 'intern'
  | 'junior'
  | 'mid'
  | 'senior'
  | 'staff'
  | 'principal'
  | 'director'
  | 'vp'
  | 'c_level';

export type LocationType = 'remote' | 'hybrid' | 'onsite';

export type RoleType = 'permanent' | 'contract' | 'freelance';

export const ROLE_FAMILY_LABELS: Record<RoleFamily, string> = {
  software_engineering: 'Software Engineering',
  infrastructure: 'Infrastructure & DevOps',
  data: 'Data & ML',
  product: 'Product Management',
  design: 'Design',
  engineering_management: 'Engineering Management',
  sales: 'Sales',
  marketing: 'Marketing',
  customer_success: 'Customer Success',
  operations: 'Operations',
  people: 'People & HR',
  finance: 'Finance',
  legal: 'Legal',
  other: 'Other',
};

export const SENIORITY_LABELS: Record<Seniority, string> = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid-Level',
  senior: 'Senior',
  staff: 'Staff',
  principal: 'Principal',
  director: 'Director',
  vp: 'VP',
  c_level: 'C-Level',
};

export const LOCATION_TYPE_LABELS: Record<LocationType, string> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'On-site',
};

export function formatSalary(min?: number | null, max?: number | null): string | null {
  if (!min && !max) return null;

  const format = (n: number) => {
    if (n >= 1000000) return `$${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `$${Math.round(n / 1000)}K`;
    return `$${n}`;
  };

  if (min && max && min !== max) {
    return `${format(min)} - ${format(max)}`;
  }
  return format(min || max || 0);
}

export function formatTimeAgo(dateString: string | null): string {
  if (!dateString) return 'Recently';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

export function getScoreBadge(score: number): { label: string; color: string } {
  if (score >= 0.8) return { label: 'Excellent match', color: 'bg-green-500' };
  if (score >= 0.7) return { label: 'Strong match', color: 'bg-green-400' };
  if (score >= 0.6) return { label: 'Good match', color: 'bg-blue-500' };
  if (score >= 0.5) return { label: 'Moderate match', color: 'bg-blue-400' };
  return { label: 'Potential match', color: 'bg-gray-400' };
}
