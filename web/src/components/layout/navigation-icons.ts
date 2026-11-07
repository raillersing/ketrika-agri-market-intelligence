import { Activity, ArrowLeftRight, BarChart3, Bell, CheckSquare, CloudSun, FileText, Info, LayoutDashboard, Map, MessageSquare, Package, Settings2, TrendingUp, type LucideIcon } from "lucide-react";
import type { NavigationIcon } from "@/lib/navigation";

export const NAVIGATION_ICONS: Record<NavigationIcon, LucideIcon> = {
  overview: LayoutDashboard, prices: TrendingUp, map: Map, trade: ArrowLeftRight,
  economy: BarChart3, climate: CloudSun, assistant: MessageSquare, alerts: Bell,
  bulletins: FileText, sources: Activity, review: CheckSquare, system: Settings2, about: Info,
  products: Package,
};
