// Check item types
export type CheckStatus =
  | 'new'
  | 'in_review'
  | 'escalated'
  | 'pending_approval'
  | 'pending_dual_control'
  | 'approved'
  | 'rejected'
  | 'returned'
  | 'closed';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type AccountType = 'consumer' | 'business' | 'commercial' | 'non_profit';

export interface CheckImage {
  id: string;
  image_type: 'front' | 'back';
  content_type: string;
  file_size?: number;
  width?: number;
  height?: number;
  image_url?: string;
  thumbnail_url?: string;
}

export interface AccountContext {
  account_tenure_days?: number;
  current_balance?: number;
  average_balance_30d?: number;
  avg_check_amount_30d?: number;
  avg_check_amount_90d?: number;
  avg_check_amount_365d?: number;
  check_std_dev_30d?: number;
  max_check_amount_90d?: number;
  check_frequency_30d?: number;
  returned_item_count_90d?: number;
  exception_count_90d?: number;
  amount_vs_avg_ratio?: number;
}

export interface AIFlag {
  code: string;
  type?: string; // Alternative identifier
  description: string;
  category: string;
  severity: 'info' | 'warning' | 'alert';
  confidence?: number;
  explanation?: string;
}

export interface CheckItem {
  id: string;
  external_item_id: string;
  source_system: string;
  account_id: string;
  account_number_masked: string;
  account_type: AccountType;
  routing_number?: string;
  check_number?: string;
  amount: number;
  currency: string;
  payee_name?: string;
  memo?: string;
  micr_line?: string;
  presented_date: string;
  check_date?: string;
  process_date?: string;
  status: CheckStatus;
  risk_level: RiskLevel;
  priority: number;
  requires_dual_control: boolean;
  has_ai_flags: boolean;
  sla_due_at?: string;
  sla_breached: boolean;
  assigned_reviewer_id?: string;
  assigned_approver_id?: string;
  queue_id?: string;
  policy_version_id?: string;
  images: CheckImage[];
  account_context?: AccountContext;
  ai_flags: AIFlag[];
  created_at: string;
  updated_at: string;
}

export interface CheckItemListItem {
  id: string;
  external_item_id: string;
  account_number_masked: string;
  account_type: AccountType;
  amount: number;
  check_number?: string;
  payee_name?: string;
  presented_date: string;
  status: CheckStatus;
  risk_level: RiskLevel;
  priority: number;
  requires_dual_control: boolean;
  has_ai_flags: boolean;
  sla_due_at?: string;
  sla_breached: boolean;
  assigned_reviewer_id?: string;
  thumbnail_url?: string;
}

export interface CheckHistory {
  id: string;
  account_id: string;
  check_number?: string;
  amount: number;
  check_date: string;
  payee_name?: string;
  status: string;
  return_reason?: string;
  front_image_url?: string;
  back_image_url?: string;
}

// Decision types
export type DecisionType = 'review_recommendation' | 'approval_decision' | 'escalation';
export type DecisionAction = 'approve' | 'return' | 'reject' | 'hold' | 'escalate' | 'needs_more_info';

export interface ReasonCode {
  id: string;
  code: string;
  description: string;
  category: string;
  decision_type: string;
  requires_notes: boolean;
  is_active: boolean;
}

export interface Decision {
  id: string;
  check_item_id: string;
  user_id: string;
  username?: string;
  decision_type: DecisionType;
  action: DecisionAction;
  reason_codes: ReasonCode[];
  notes?: string;
  ai_assisted: boolean;
  is_dual_control_required: boolean;
  dual_control_approver_id?: string;
  dual_control_approved_at?: string;
  created_at: string;
}

// Queue types
export interface Queue {
  id: string;
  name: string;
  description?: string;
  queue_type: string;
  sla_hours: number;
  warning_threshold_minutes: number;
  is_active: boolean;
  display_order: number;
  current_item_count: number;
  items_processed_today: number;
}

export interface QueueStats {
  queue_id: string;
  queue_name: string;
  total_items: number;
  items_by_status: Record<string, number>;
  items_by_risk_level: Record<string, number>;
  sla_breached_count: number;
  avg_processing_time_minutes?: number;
  items_processed_today: number;
}

// User types
export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  department?: string;
  branch?: string;
  is_active: boolean;
  is_superuser: boolean;
  roles: Role[];
  permissions: string[];
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  is_system: boolean;
  permissions: Permission[];
}

export interface Permission {
  id: string;
  name: string;
  resource: string;
  action: string;
}

// API response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

// ROI (Region of Interest) types for overlays
export interface ROIRegion {
  id: string;
  name: string;
  type: 'amount_box' | 'legal_line' | 'signature' | 'micr' | 'payee' | 'date' | 'memo';
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
}

// Dashboard stats
export interface DashboardStats {
  summary: {
    pending_items: number;
    processed_today: number;
    sla_breached: number;
    dual_control_pending: number;
  };
  items_by_risk: Record<string, number>;
  items_by_status: Record<string, number>;
}

// Fraud Intelligence types
export type FraudType =
  | 'check_kiting'
  | 'counterfeit_check'
  | 'forged_signature'
  | 'altered_check'
  | 'account_takeover'
  | 'identity_theft'
  | 'first_party_fraud'
  | 'synthetic_identity'
  | 'duplicate_deposit'
  | 'unauthorized_endorsement'
  | 'payee_alteration'
  | 'amount_alteration'
  | 'fictitious_payee'
  | 'other';

export type FraudChannel = 'branch' | 'atm' | 'mobile' | 'rdc' | 'mail' | 'online' | 'other';

export type AmountBucket =
  | 'under_100'
  | '100_to_500'
  | '500_to_1000'
  | '1000_to_5000'
  | '5000_to_10000'
  | '10000_to_50000'
  | 'over_50000';

export type SharingLevel = 0 | 1 | 2;

export type FraudEventStatus = 'draft' | 'submitted' | 'withdrawn';

export type MatchSeverity = 'low' | 'medium' | 'high';

export interface FraudEvent {
  id: string;
  tenant_id: string;
  check_item_id?: string;
  case_id?: string;
  event_date: string;
  amount: number;
  amount_bucket: AmountBucket;
  fraud_type: FraudType;
  channel: FraudChannel;
  confidence: number;
  narrative_private?: string;
  narrative_shareable?: string;
  sharing_level: SharingLevel;
  status: FraudEventStatus;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
  submitted_by_user_id?: string;
  withdrawn_at?: string;
  withdrawn_by_user_id?: string;
  withdrawn_reason?: string;
  has_shared_artifact: boolean;
}

export interface FraudEventCreate {
  check_item_id?: string;
  case_id?: string;
  event_date: string;
  amount: number;
  fraud_type: FraudType;
  channel: FraudChannel;
  confidence: number;
  narrative_private?: string;
  narrative_shareable?: string;
  sharing_level: SharingLevel;
}

export interface MatchReasonDetail {
  indicator_type: string;
  match_count: number;
  first_seen: string;
  last_seen: string;
  fraud_types: string[];
  channels: string[];
}

export interface NetworkAlert {
  id: string;
  check_item_id?: string;
  case_id?: string;
  severity: MatchSeverity;
  total_matches: number;
  distinct_institutions: number;
  earliest_match_date?: string;
  latest_match_date?: string;
  match_reasons: MatchReasonDetail[];
  created_at: string;
  last_checked_at: string;
  is_dismissed: boolean;
  dismissed_at?: string;
  dismissed_reason?: string;
}

export interface NetworkAlertSummary {
  has_alerts: boolean;
  total_alerts: number;
  highest_severity?: MatchSeverity;
  alerts: NetworkAlert[];
}

export interface PIIDetectionResult {
  has_potential_pii: boolean;
  warnings: string[];
  detected_patterns: string[];
}

export interface TenantFraudConfig {
  tenant_id: string;
  default_sharing_level: SharingLevel;
  allow_narrative_sharing: boolean;
  allow_account_indicator_sharing: boolean;
  shared_artifact_retention_months: number;
  receive_network_alerts: boolean;
  minimum_alert_severity: MatchSeverity;
  updated_at: string;
}
