export type SolverStatus = "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | string;

export type ObjectiveBreakdown = {
  cost: number;
  preference: number;
  fairness: number;
  overtime: number;
  night_imbalance: number;
  weekend_imbalance: number;
  understaff: number;
  total: number;
};

export type ConflictGroup = {
  group: string;
  label: string;
};

export type Diagnostics = {
  note: string;
  findings: Array<{
    code: string;
    message: string;
    shift_id?: number;
    employee_id?: number;
    skill?: string;
  }>;
  relaxations: Array<{
    relaxed: string[];
    solver_status: string;
    error?: string | null;
    detail?: string;
  }>;
  assumptions_available?: boolean;
  assumption_method?: string | null;
  conflict_groups?: ConflictGroup[];
  unsat_core_kind?: string;
};

export type OptimizationRun = {
  id: number;
  status: string;
  solver_status: SolverStatus | null;
  objective: number | null;
  best_bound: number | null;
  runtime_seconds: number | null;
  mode: string;
  reproducible: boolean;
  mode_label: string | null;
  random_seed: number;
  parameters: Record<string, unknown>;
  label: string;
  error_message: string | null;
  diagnostics: Diagnostics | null;
  objective_breakdown: ObjectiveBreakdown | null;
  schedule_id: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
};

export type Validation = {
  valid: boolean;
  violations: Array<{
    code: string;
    message: string;
    shift_id: number | null;
    employee_id: number | null;
  }>;
};

export type Overview = {
  demo: boolean;
  synthetic_data: boolean;
  organization_name: string | null;
  planning_timezone: string | null;
  counts: {
    employees: number;
    shifts: number;
    skills: number;
  };
  latest_run: OptimizationRun | null;
  recent_runs: OptimizationRun[];
  schedule: {
    id: number;
    solver_status: SolverStatus;
    objective_breakdown: ObjectiveBreakdown;
    kpis: Record<string, unknown>;
    validation: Validation;
    mode_label: string | null;
  } | null;
};

export type Employee = {
  id: number;
  display_alias: string;
  weekly_hour_cap: number;
  cost_per_hour: number;
  night_preference: string;
  weekend_preference: string;
  skills: string[];
  availability: Array<Record<string, unknown>>;
  time_off: Array<{
    id: number;
    start_local: string;
    end_local: string;
    reason: string;
  }>;
};

export type Shift = {
  id: number;
  template_id: number | null;
  label: string;
  local_date: string;
  start_local: string;
  end_local: string;
  start_utc: string;
  end_utc: string;
  overnight: boolean;
  required_count: number;
  is_night: boolean;
  is_weekend: boolean;
  duration_hours: number;
  skill_requirements: Array<{
    skill_names?: string[];
    label: string;
    min_count: number;
  }>;
};

export type ScheduleAssignment = {
  employee_id: number;
  display_alias: string;
  shift_id: number;
  label: string;
  local_date: string;
  start_local: string;
  end_local: string;
  start_utc: string;
  end_utc: string;
  overnight: boolean;
  is_night: boolean;
  is_weekend: boolean;
  hours: number;
};

export type Schedule = {
  id: number;
  run_id: number;
  solver_status: SolverStatus;
  objective: number;
  best_bound: number | null;
  runtime_seconds: number | null;
  mode: string | null;
  reproducible: boolean;
  mode_label: string | null;
  objective_breakdown: ObjectiveBreakdown;
  employee_hours: Array<{ employee_id: number; hours: number; display_alias?: string }>;
  assignments: ScheduleAssignment[];
  shifts: Shift[];
  employees: Array<{
    id: number;
    display_alias: string;
    skills: string[];
    weekly_hour_cap: number;
    hours: number;
  }>;
  validation: Validation;
  kpis: Record<string, unknown>;
  planning_timezone: string;
  organization_name: string;
  days: string[];
  rules: Record<string, unknown>;
  created_at: string;
};

export type DemoScenario = "optimal" | "feasible" | "infeasible";

export type DemoLoadResult = {
  scenario: DemoScenario;
  synthetic: boolean;
  employees?: number;
  shifts?: number;
  [key: string]: unknown;
};

export type ScenarioTiming = {
  scenario: DemoScenario;
  expected: SolverStatus;
  solver_status: SolverStatus | null;
  wall_ms: number | null;
  objective: number | null;
  best_bound: number | null;
  gap: number | null;
  run_id: number | null;
  error?: string;
};

export type ScheduleSummary = {
  id: number;
  run_id: number;
  label: string;
  solver_status: SolverStatus;
  objective: number | null;
  mode: string | null;
  mode_label: string | null;
  created_at: string;
  assignment_count: number;
};

export type ScheduleCompare = {
  left: {
    id: number;
    run_id: number;
    label: string;
    solver_status: SolverStatus;
    objective: number;
    objective_breakdown: ObjectiveBreakdown;
    mode_label: string | null;
    validation: Validation;
    rules: Record<string, unknown>;
  };
  right: {
    id: number;
    run_id: number;
    label: string;
    solver_status: SolverStatus;
    objective: number;
    objective_breakdown: ObjectiveBreakdown;
    mode_label: string | null;
    validation: Validation;
    rules: Record<string, unknown>;
  };
  objective_delta: Record<string, number>;
  rules_match: boolean;
  weight_deltas: Record<string, number>;
  assignment_diff: {
    shared_count: number;
    only_left: Array<{ employee_id: number; shift_id: number }>;
    only_right: Array<{ employee_id: number; shift_id: number }>;
    only_left_count: number;
    only_right_count: number;
  };
};

export type Ruleset = {
  id: number;
  name: string;
  min_rest_hours: number;
  max_shift_hours: number;
  max_consecutive_days: number | null;
  overtime_threshold_hours: number;
  relaxed_understaffing: boolean;
  weights: ObjectiveBreakdown & Record<string, number>;
  is_active: boolean;
};
