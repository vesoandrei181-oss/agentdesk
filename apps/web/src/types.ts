/** 与后端 Pydantic 结构一一对应的前端类型。字段名刻意保持后端的 snake_case，减少一层映射代码。 */

export type Tier = 'quality' | 'balanced' | 'cheap' | 'local';

export interface User {
  id: number;
  email: string;
  name: string;
  title: string;
  avatar_hue: number;
  workspaces: { id: number; name: string; slug: string; role: string }[];
}

export interface LoginResp {
  token: string;
  user: User;
}

export interface Evidence {
  segment_id?: number;
  start_ms?: number;
  end_ms?: number;
  quote: string;
  speaker?: string;
  verified?: boolean;
  recovered?: boolean;
}

export type DecisionKind = 'decision' | 'risk' | 'open_question';

export interface Decision {
  id: number;
  text: string;
  kind: DecisionKind;
  evidence: Evidence[];
  confidence: number;
  grounded: boolean;
  status: string;
}

export interface ActionItem {
  id: number;
  text: string;
  owner_name: string;
  due_date: string;
  priority: 'high' | 'medium' | 'low';
  evidence: Evidence[];
  confidence: number;
  task_id?: number | null;
}

export interface Segment {
  idx: number;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence?: number;
}

export interface Topic {
  title: string;
  summary?: string;
  segments: number[];
  start_ms?: number;
  end_ms?: number;
}

export interface MeetingSummary {
  id: number;
  title: string;
  status: 'draft' | 'processing' | 'ready' | 'failed';
  source_type: string;
  meeting_date: string;
  created_at: string;
  duration_ms: number;
  attendees: string[];
  summary: string;
  counts: { decisions: number; actions: number; segments: number };
  trace_id?: number | null;
}

export interface MeetingDetail extends MeetingSummary {
  segments: Segment[];
  decisions: Decision[];
  action_items: ActionItem[];
  topics: Topic[];
  highlights?: string[];
}

export interface RunStep {
  idx: number;
  agent: string;
  label?: string;
  status: string;
  input: string;
  output: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cache_hit: boolean;
  evidence_count: number;
  payload?: Record<string, unknown>;
}

export interface RunInfo {
  id: number;
  kind: string;
  title: string;
  status: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
  cache_hits: number;
  created_at: string;
  meta?: Record<string, unknown>;
}

export interface TraceResp {
  run: RunInfo;
  steps: RunStep[];
}

export interface DocSummary {
  id: number;
  title: string;
  word_count: number;
  version: number;
  updated_at: string;
  preview: string;
}

export interface DocDetail {
  id: number;
  title: string;
  content: string;
  version: number;
  word_count: number;
  updated_at: string;
  trace_id?: number | null;
}

export interface DocTemplate {
  id: string;
  name: string;
  desc: string;
  content: string;
}

export interface DiffBlock {
  type: 'equal' | 'replace' | 'insert' | 'delete' | 'skip';
  /** 被替换/删除掉的原始行 */
  old?: string[];
  /** 替换后/新增的行 */
  new?: string[];
  /** equal / skip 块里的原样行 */
  lines?: string[];
  /** skip 块折叠掉的行数 */
  count?: number;
}

export interface WriteStats {
  lines_changed: number;
  added: number;
  removed: number;
  edit_ratio: number;
  avg_sentence_delta: number;
  issue_delta: number;
}

export interface WriteResult {
  revised: string;
  blocks: DiffBlock[];
  notes: string[];
  patches?: { op: string; target: string; new_text?: string; reason?: string; ok?: boolean }[];
  style_note?: string;
  risks: string[] | Record<string, unknown>[];
  style_before: StyleProfile;
  style_after: StyleProfile;
  stats: WriteStats;
  trace_id?: number;
  current_content: string;
}

export interface StyleProfile {
  chars: number;
  zh_chars: number;
  sentences: number;
  avg_sentence: number;
  max_sentence: number;
  fillers: number;
  issues: string[];
}

export interface KbDoc {
  id: number;
  title: string;
  filename: string;
  ext: string;
  pages: number;
  chunk_count: number;
  status: string;
  created_at: string;
}

export interface Chunk {
  idx: number;
  page: number;
  section: string;
  text: string;
}

export interface Citation {
  n: number;
  doc: string;
  page: number;
  section: string;
  score: number;
  support: 'strong' | 'weak';
  text: string;
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface Task {
  id: number;
  title: string;
  description: string;
  status: 'todo' | 'doing' | 'review' | 'done';
  priority: 'high' | 'medium' | 'low';
  owner_name: string;
  due_date: string;
  p50_days: number;
  p90_days: number;
  risk_score: number;
  tags: string[];
  source_meeting_id?: number | null;
  ai_generated?: boolean;
}

export interface BoardColumn {
  key: Task['status'];
  name: string;
  items: Task[];
}

export interface BoardResp {
  columns: BoardColumn[];
  owners: string[];
  total: number;
}

export interface Kpi {
  meetings: number;
  meetings_ready: number;
  decisions: number;
  grounded_rate: number;
  avg_decisions: number;
  tasks: number;
  tasks_done: number;
  completion_rate: number;
  at_risk: number;
  saved_minutes: number;
  tokens: number;
  cost_usd: number;
  runs: number;
  cache_hits: number;
}

export interface AgentStat {
  agent: string;
  label: string;
  calls: number;
  tokens: number;
  latency: number;
  errors: number;
  cache: number;
  avg_latency: number;
}

export interface RuntimeTableRow {
  model: string;
  temperature: number;
  thinking?: 'on' | 'off';
}

export interface RuntimeInfo {
  tier: Tier;
  tiers: Tier[];
  models: { fast: string; quality: string };
  table: Record<string, RuntimeTableRow>;
  provider: string;
  base_url: string;
  mock: boolean;
  pii_mask: boolean;
  semantic_cache: boolean;
  fast_thinking?: boolean;
  budget: number;
  cache_threshold: number;
}

export interface Overview {
  kpi: Kpi;
  timeline: { date: string; runs: number; tokens?: number }[];
  agents: AgentStat[];
  runtime: Omit<RuntimeInfo, 'provider' | 'base_url' | 'mock' | 'pii_mask' | 'semantic_cache' | 'budget' | 'cache_threshold'>;
  cache: { entries: number; hits: number; misses: number; hit_rate: number; threshold: number };
}

export interface WeeklyDigest {
  digest: {
    owners: { owner: string; total: number; done: number; doing: number; todo: number; risk: number; hours_left: number }[];
    meetings: { id: number; title: string; date: string }[];
    coverage: number;
    totals: { tasks: number; done: number; risk: number };
  };
  text: string;
  report?: { headline: string; sections: { title: string; content: string }[]; fallback?: boolean } | null;
  trace_id?: number | null;
}

export interface EstimateResp {
  p50_hours: number;
  p90_hours: number;
  p50_days: number;
  p90_days: number;
  sigma: number;
  confidence: number;
  factors: string[];
  slack_days: number | null;
  risk: string;
}
