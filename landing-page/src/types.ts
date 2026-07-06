import type { LucideIcon } from "lucide-react";

export type AppRoute = "workspace" | "explore" | "account" | "admin";

export type AccountSection =
  | "projects"
  | "assets"
  | "library"
  | "presets"
  | "orders"
  | "settings"
  | "admin-overview"
  | "admin-frontend"
  | "admin-models"
  | "admin-providers"
  | "admin-routing";

export type CapabilityCategory = string;

export type ModelCategory = {
  id: string;
  key: string;
  name: string;
  icon?: string | null;
  sortOrder: number;
  visible: boolean;
  parentId?: string | null;
  aliases?: string[];
};

export type ModelParameterOption = {
  label: string;
  value: string | number | boolean;
};

export type ModelParameter = {
  key: string;
  label: string;
  type: "textarea" | "text" | "select" | "segmented" | "slider" | "switch" | "number";
  required?: boolean;
  advanced?: boolean;
  helper?: string;
  defaultValue?: string | number | boolean;
  min?: number;
  max?: number;
  step?: number;
  options?: ModelParameterOption[];
};

export type CreativeModel = {
  id: string;
  name: string;
  category: CapabilityCategory;
  categoryKeys?: CapabilityCategory[];
  aliases?: string[];
  slug?: string;
  group: string;
  description: string;
  bestFor: string[];
  tags: string[];
  cost: number;
  health: number;
  platformModelId: string;
  upstreamModelName: string;
  endpointPath: string;
  parameters: ModelParameter[];
  icon: LucideIcon;
};

export type Template = {
  id: string;
  title: string;
  category: string;
  description: string;
  prompt: string;
  tokens: number;
  accent: "teal" | "violet" | "amber" | "sky";
};

export type UserProfile = {
  initials: string;
  name: string;
  email: string;
  role: "creator" | "admin";
  tokens: number;
  frozenTokens: number;
  plan: string;
  monthlyAllowance: number;
};

export type LibraryAsset = {
  id: string;
  title: string;
  type: "图片" | "视频";
  createdAt: string;
  model: string;
  favorite?: boolean;
};

export type LedgerItem = {
  id: string;
  title: string;
  time: string;
  tokens: number;
  status: "已完成" | "已退回" | "冻结中";
};

export type OrderRecord = {
  id: string;
  tokens: number;
  status: "已完成" | "处理中" | "已取消";
  time: string;
};
