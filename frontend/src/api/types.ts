export type Role = 'CLIENT' | 'MANAGER' | 'ADMIN'

export interface User {
  id: string
  email: string
  role: Role
  full_name: string
  phone: string
  client_type: string
  company_name: string
  is_senior: boolean
}

export interface Ref { id: string; name: string }
export interface Issue { code: string; message: string }
export interface Validation { verdict: 'OK' | 'WARNING' | 'ERROR'; issues: Issue[]; needs_support: boolean }
export interface Quote {
  total: number; cost_material: number; cost_machine: number; cost_post: number; cost_delivery: number
  adjustment: number; print_hours: number; mass_g: number; estimated_days: number
}
export interface ModelInfo {
  version: number; file_name: string; format: string; size_bytes: number
  bbox: number[]; volume_cm3: number; body_count: number
}
export interface TransitionOpt { to: string; label: string; reason_required: boolean }
export interface OrderEvent {
  id: string; type: string; from_status: string; to_status: string; reason: string; actor: string; created_at: string
}
export interface Assignment {
  printer: string; printer_id: string; workshop: string; planned_start: string; planned_end: string
  is_manual: boolean; reason: string
}
export interface Order {
  id: string; number: string; status: string; status_label: string; priority: number; quantity: number
  material: Ref | null; technology: { id: string; code: string } | null
  quality_profile: Ref | null; color: Ref | null; delivery_method: Ref | null; pickup_point: Ref | null
  post_processing: Ref[]; delivery_address: string; comment: string; desired_date: string | null
  planned_date: string | null; reject_reason: string; version: number
  total: number | null; created_at: string; updated_at: string
  client: { id: string; full_name: string; email: string }
  client_details?: { id: string; full_name: string; email: string; phone: string; company_name: string; client_type: string }
  model: ModelInfo | null; quote: Quote | null; validation: Validation | null; ready: boolean
  assignment: Assignment | null; events: OrderEvent[]; available_transitions: TransitionOpt[]; can_edit: boolean
}
export interface OrderList { count: number; page: number; page_size: number; results: Order[] }
export interface Message {
  id: string; text: string; created_at: string; model_version: number | null
  author: { id: string; full_name: string; role: string }
}
export interface NotificationItem {
  id: string; order_id: string | null; order_number: string | null; text: string; is_read: boolean; created_at: string
}
export interface Printer { printer_id: string; printer: string; workshop?: string; score?: number; t_free_h?: number; planned_start?: string; planned_end?: string }
export interface Recommendation {
  top: Printer[]; others: Printer[]; excluded: { printer_id: string; printer: string; reason: string }[]
}
export interface LoadData {
  horizon_hours: number
  printers: { printer_id: string; printer: string; workshop: string; technology: string; status: string
    planned_hours: number; idle_hours: number; load_percent: number; jobs: { number: string; hours: number }[] }[]
  workshops: { workshop_id: string; workshop: string; load_percent: number }[]
}
