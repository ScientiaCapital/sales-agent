import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Sparkles, AlertCircle } from "lucide-react";

interface TrifectaMetrics {
  full_trifecta: {
    count: number;
    companies: string[];
    tier_distribution: {
      PLATINUM: number;
      GOLD: number;
      SILVER: number;
      BRONZE: number;
    };
  };
  partial_trifecta: {
    count: number;
    solar_gen: number;
    solar_battery: number;
    gen_battery: number;
  };
  multi_oem: {
    count: number;
    brands_3_plus: number;
    brands_5_plus: number;
    top_brands: Record<string, number>;
  };
  totals: {
    total_companies: number;
    with_solar: number;
    with_generator: number;
    with_battery: number;
    unicorn_count: number;
  };
}

interface TrifectaResponse {
  metrics: TrifectaMetrics;
  summary: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function TrifectaSkeleton() {
  return (
    <div className="space-y-6">
      {[1, 2, 3].map((i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-6 w-full" />
        </div>
      ))}
    </div>
  );
}

function ProgressBar({
  label,
  value,
  max,
  sublabel,
  gradient = false,
}: {
  label: string;
  value: number;
  max: number;
  sublabel?: string;
  gradient?: boolean;
}) {
  const percentage = max > 0 ? (value / max) * 100 : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">{label}</p>
          {sublabel && (
            <p className="text-xs text-muted-foreground">{sublabel}</p>
          )}
        </div>
        <span className="text-2xl font-bold text-[var(--turkish-blue)]">
          {value.toLocaleString()}
        </span>
      </div>
      <div className="relative">
        <Progress
          value={percentage}
          className={`h-6 ${gradient ? "bg-gradient-to-r from-purple-100 to-purple-50" : "bg-gray-100"}`}
        />
        <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-700">
          {percentage.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export function TrifectaPanel() {
  const { data, isLoading, error } = useSWR<TrifectaResponse>(
    "/api/dashboard/trifecta",
    fetcher,
    { refreshInterval: 300000 } // Refresh every 5 min
  );

  if (error) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <span className="text-xl">☀️⚡🔋</span>
            TRIFECTA HUNTERS
            <Badge variant="outline" className="ml-2 border-purple-500 text-purple-600">
              UNICORN DETECTION
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">Failed to load trifecta data</p>
            <p className="text-sm text-muted-foreground">
              Please check if the backend server is running
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <span className="text-xl">☀️⚡🔋</span>
            TRIFECTA HUNTERS
            <Badge variant="outline" className="ml-2 border-purple-500 text-purple-600">
              UNICORN DETECTION
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TrifectaSkeleton />
        </CardContent>
      </Card>
    );
  }

  const { metrics, summary } = data;
  const maxCount = Math.max(
    metrics.full_trifecta.count,
    metrics.partial_trifecta.count,
    metrics.multi_oem.count
  );

  return (
    <Card className="border-2 border-purple-200">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <span className="text-xl">☀️⚡🔋</span>
            TRIFECTA HUNTERS
            <Badge variant="outline" className="ml-2 border-purple-500 text-purple-600">
              UNICORN DETECTION
            </Badge>
          </CardTitle>
          {metrics.totals.unicorn_count > 0 && (
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-600" />
              <span className="text-2xl font-bold text-purple-600">
                {metrics.totals.unicorn_count}
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Full Trifecta */}
        <ProgressBar
          label="FULL TRIFECTA (Solar + Generator + Battery)"
          sublabel="Complete energy independence systems"
          value={metrics.full_trifecta.count}
          max={maxCount}
          gradient={true}
        />

        {/* Partial Trifecta */}
        <ProgressBar
          label="PARTIAL TRIFECTA (2 of 3)"
          sublabel={`Solar+Gen: ${metrics.partial_trifecta.solar_gen} | Solar+Battery: ${metrics.partial_trifecta.solar_battery} | Gen+Battery: ${metrics.partial_trifecta.gen_battery}`}
          value={metrics.partial_trifecta.count}
          max={maxCount}
        />

        {/* Multi-OEM */}
        <ProgressBar
          label="MULTI-OEM (3+ brands)"
          sublabel={`5+ brands: ${metrics.multi_oem.brands_5_plus} companies`}
          value={metrics.multi_oem.count}
          max={maxCount}
        />

        {/* Unicorn Highlight */}
        {metrics.totals.unicorn_count > 0 && (
          <div className="bg-gradient-to-r from-purple-50 to-pink-50 border-2 border-purple-300 rounded-lg p-4 mt-4">
            <div className="flex items-start gap-3">
              <span className="text-3xl">🦄</span>
              <div className="flex-1">
                <p className="font-bold text-purple-900 text-lg mb-1">
                  UNICORNS: {metrics.totals.unicorn_count} contractors with FULL
                  TRIFECTA
                </p>
                <p className="text-sm text-purple-700 mb-2">
                  → These are the HIGHEST VALUE targets
                </p>

                {/* Tier Distribution */}
                <div className="grid grid-cols-4 gap-2 mt-3">
                  {metrics.full_trifecta.tier_distribution.PLATINUM > 0 && (
                    <div className="bg-purple-100 rounded px-2 py-1 text-center">
                      <p className="text-xs font-semibold text-purple-900">
                        PLATINUM
                      </p>
                      <p className="text-lg font-bold text-purple-700">
                        {metrics.full_trifecta.tier_distribution.PLATINUM}
                      </p>
                    </div>
                  )}
                  {metrics.full_trifecta.tier_distribution.GOLD > 0 && (
                    <div className="bg-yellow-100 rounded px-2 py-1 text-center">
                      <p className="text-xs font-semibold text-yellow-900">
                        GOLD
                      </p>
                      <p className="text-lg font-bold text-yellow-700">
                        {metrics.full_trifecta.tier_distribution.GOLD}
                      </p>
                    </div>
                  )}
                  {metrics.full_trifecta.tier_distribution.SILVER > 0 && (
                    <div className="bg-gray-100 rounded px-2 py-1 text-center">
                      <p className="text-xs font-semibold text-gray-900">
                        SILVER
                      </p>
                      <p className="text-lg font-bold text-gray-700">
                        {metrics.full_trifecta.tier_distribution.SILVER}
                      </p>
                    </div>
                  )}
                  {metrics.full_trifecta.tier_distribution.BRONZE > 0 && (
                    <div className="bg-orange-100 rounded px-2 py-1 text-center">
                      <p className="text-xs font-semibold text-orange-900">
                        BRONZE
                      </p>
                      <p className="text-lg font-bold text-orange-700">
                        {metrics.full_trifecta.tier_distribution.BRONZE}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-3 pt-4 border-t">
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Solar</p>
            <p className="text-xl font-bold text-[var(--turkish-blue)]">
              {metrics.totals.with_solar}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Generators</p>
            <p className="text-xl font-bold text-[var(--turkish-blue)]">
              {metrics.totals.with_generator}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Batteries</p>
            <p className="text-xl font-bold text-[var(--turkish-blue)]">
              {metrics.totals.with_battery}
            </p>
          </div>
        </div>

        {/* Insight */}
        <div className="text-xs text-muted-foreground italic pt-2 border-t">
          {summary}
        </div>
      </CardContent>
    </Card>
  );
}
