import { getCachedMetrics, METRICS_REVALIDATE_SECONDS } from "@/lib/metrics";
import { StatusDashboard } from "@/components/status-dashboard";

export const revalidate = 300; // 5 minutes ISR cache

export default async function HomePage() {
  const initialData = await getCachedMetrics();

  return <StatusDashboard initialData={initialData} />;
}
