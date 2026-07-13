// ========== 用户与权限 ==========
export interface User {
  id: number;
  username: string;
  real_name: string;
  role: UserRole;
  department: string;
  phone: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export type UserRole = 'admin' | 'partner' | 'lawyer' | 'assistant' | 'intern';

// ========== 客户 ==========
export interface Client {
  id: number;
  name: string;
  contact_person: string;
  phone: string;
  wechat: string;
  email: string;
  address: string;
  cooperation_history: string;
  legal_contacts: string;
  notes: string;
  case_count: number;
  created_at: string;
  updated_at: string;
}

// ========== 案件 ==========
export interface CaseClient {
  id: number;
  name: string;
  contact_person: string;
}

export interface Case {
  id: number;
  case_number: string;
  case_reason: string;
  court: string;
  judge: string;
  clerk: string;
  plaintiff: string;
  defendant: string;
  third_party: string[];
  third_party_clients: CaseClient[];
  amount_in_dispute: number;
  case_stage: CaseStage;
  clients: CaseClient[];
  acceptance_date: string | null;
  filing_date: string | null;
  trial_date: string | null;
  judgment_date: string | null;
  closing_date: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export type CaseStage =
  | 'intake'        // 接案
  | 'filing'        // 立案
  | 'trial'         // 审理中
  | 'judgment'      // 判决
  | 'enforcement'   // 执行
  | 'closed';       // 结案

export const CASE_STAGE_LABELS: Record<CaseStage, string> = {
  intake: '接案',
  filing: '立案',
  trial: '审理中',
  judgment: '判决',
  enforcement: '执行',
  closed: '结案',
};

// ========== 文档 ==========
export interface Document {
  id: number;
  filename: string;
  original_name: string;
  file_path: string;
  file_size: number;
  size_display: string;
  file_type: string;
  doc_category: DocumentCategory;
  case_id: number | null;
  case_number: string | null;
  client_id: number | null;
  client_name: string | null;
  version: number;
  author: string;
  notes: string;
  uploaded_at: string;
}

export type DocumentCategory =
  | 'legal_opinion'   // 法律意见书
  | 'contract_draft'  // 合同草稿
  | 'complaint'       // 起诉状
  | 'defense'         // 答辩状
  | 'proxy_statement' // 代理词
  | 'evidence_list'   // 证据清单
  | 'other';          // 其他

export const DOC_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  legal_opinion: '法律意见书',
  contract_draft: '合同草案',
  complaint: '起诉状',
  defense: '答辩状',
  proxy_statement: '代理词',
  evidence_list: '证据清单',
  other: '其他',
};

// ========== 日程 ==========
export interface Schedule {
  id: number;
  title: string;
  schedule_type: ScheduleType;
  case_id: number | null;
  case_number: string | null;
  case_reason: string | null;
  start_time: string;
  end_time: string;
  location: string;
  judge: string;
  notes: string;
  is_parsed_from_sms: boolean;
  created_at: string;
}

export type ScheduleType = 'hearing' | 'meeting' | 'consultation' | 'deadline' | 'other';

export const SCHEDULE_TYPE_LABELS: Record<ScheduleType, string> = {
  hearing: '开庭',
  meeting: '会议',
  consultation: '咨询',
  deadline: '截止日期',
  other: '其他',
};

// ========== 待办任务 ==========
export interface Task {
  id: number;
  title: string;
  description: string;
  priority: TaskPriority;
  status: TaskStatus;
  case_id: number | null;
  client_id: number | null;
  due_date: string;
  source_message: string;
  created_at: string;
  completed_at: string | null;
}

export type TaskPriority = 'high' | 'medium' | 'low';
export type TaskStatus = 'pending' | 'in_progress' | 'completed';

export const TASK_PRIORITY_LABELS: Record<TaskPriority, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  pending: '待处理',
  in_progress: '进行中',
  completed: '已完成',
};

// ========== 账单 ==========
export interface Bill {
  id: number;
  bill_number: string;
  client_id: number;
  billing_period_start: string;
  billing_period_end: string;
  items: BillItem[];
  total_amount: number;
  status: BillStatus;
  generated_at: string;
  exported_at: string | null;
}

export interface BillItem {
  id: number;
  bill_id: number;
  case_id: number | null;
  description: string;
  billing_method: 'hourly' | 'fixed' | 'percentage';
  unit_price: number;
  quantity: number;
  amount: number;
}

export type BillStatus = 'draft' | 'generated' | 'exported' | 'paid';

// ========== 工时记录 ==========
export interface TimeRecord {
  id: number;
  case_id: number | null;
  work_category: WorkCategory;
  description: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  created_at: string;
}

export type WorkCategory = 'legal_research' | 'drafting' | 'hearing' | 'consultation' | 'other';

export const WORK_CATEGORY_LABELS: Record<WorkCategory, string> = {
  legal_research: '法律研究',
  drafting: '文书起草',
  hearing: '庭审出庭',
  consultation: '客户咨询',
  other: '其他',
};
