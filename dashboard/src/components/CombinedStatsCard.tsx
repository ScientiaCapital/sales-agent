import { Card, CardContent, CardHeader } from '@/components/ui/card';
import useSWR from 'swr';
import { useEffect, useState } from 'react';

interface CombinedStats {
  total_companies: number;
  total_contacts: number;
  icp_ready: number;
  dealer_scraper_count: number;
  sales_agent_count: number;
  new_companies_delta: number;
  new_contacts_delta: number;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function formatNumber(num: number): string {
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(0)}K`;
  }
  return num.toLocaleString();
}

function formatDelta(num: number): string {
  if (num >= 1_000) {
    return `+${(num / 1_000).toFixed(0)}K`;
  }
  return `+${num.toLocaleString()}`;
}

function AnimatedNumber({ value }: { value: number }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const duration = 1000; // 1 second animation
    const steps = 30;
    const increment = value / steps;
    let current = 0;

    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplayValue(value);
        clearInterval(timer);
      } else {
        setDisplayValue(Math.floor(current));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value]);

  return <>{displayValue.toLocaleString()}</>;
}

export default function CombinedStatsCard() {
  const { data, error, isLoading } = useSWR<CombinedStats>(
    '/api/dashboard/combined-stats',
    fetcher,
    {
      refreshInterval: 60000, // Refresh every 60 seconds
      revalidateOnFocus: true,
    }
  );

  if (error) {
    return (
      <Card className="border-red-500/20 bg-red-950/10">
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className="text-2xl">⚠️</span>
            <h2 className="text-xl font-bold text-red-500">Error Loading Stats</h2>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-400">Failed to load combined statistics</p>
        </CardContent>
      </Card>
    );
  }

  const stats = data || {
    total_companies: 0,
    total_contacts: 0,
    icp_ready: 0,
    dealer_scraper_count: 0,
    sales_agent_count: 0,
    new_companies_delta: 0,
    new_contacts_delta: 0,
  };

  return (
    <Card className="border-yellow-500/20 bg-gradient-to-br from-yellow-950/10 to-orange-950/10">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🎮</span>
            <h2 className="text-2xl font-bold text-yellow-400">SCORE BOARD</h2>
          </div>
          <div className="text-right">
            <div className="text-xs text-yellow-600 uppercase tracking-wider">High Score</div>
            <div className="text-2xl font-bold text-yellow-400">
              {isLoading ? '...' : stats.total_companies.toLocaleString()}
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Main Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Pipeline */}
          <div className="bg-blue-950/20 border border-blue-500/20 rounded-lg p-4 text-center">
            <div className="text-3xl mb-2">🏢</div>
            <div className="text-xs text-blue-400 uppercase tracking-wider mb-1">
              Pipeline
            </div>
            <div className="text-3xl font-bold text-blue-300 mb-1">
              {isLoading ? '...' : <AnimatedNumber value={stats.total_companies} />}
            </div>
            {stats.new_companies_delta > 0 && (
              <div className="text-sm text-green-400 flex items-center justify-center gap-1">
                <span>▲</span>
                <span>{formatDelta(stats.new_companies_delta)} new</span>
              </div>
            )}
          </div>

          {/* Contacts */}
          <div className="bg-purple-950/20 border border-purple-500/20 rounded-lg p-4 text-center">
            <div className="text-3xl mb-2">👔</div>
            <div className="text-xs text-purple-400 uppercase tracking-wider mb-1">
              Contacts
            </div>
            <div className="text-3xl font-bold text-purple-300 mb-1">
              {isLoading ? '...' : <AnimatedNumber value={stats.total_contacts} />}
            </div>
            {stats.new_contacts_delta > 0 && (
              <div className="text-sm text-green-400 flex items-center justify-center gap-1">
                <span>▲</span>
                <span>{formatDelta(stats.new_contacts_delta)} new</span>
              </div>
            )}
          </div>

          {/* ICP Ready */}
          <div className="bg-green-950/20 border border-green-500/20 rounded-lg p-4 text-center">
            <div className="text-3xl mb-2">🎯</div>
            <div className="text-xs text-green-400 uppercase tracking-wider mb-1">
              ICP Ready
            </div>
            <div className="text-3xl font-bold text-green-300 mb-1">
              {isLoading ? '...' : <AnimatedNumber value={stats.icp_ready} />}
            </div>
            <div className="text-xs text-green-600">PLAT + GOLD</div>
          </div>
        </div>

        {/* Data Sources Breakdown */}
        <div className="bg-slate-950/40 border border-slate-700/30 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">📊</span>
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              Data Sources
            </h3>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between text-slate-400">
              <div className="flex items-center gap-2">
                <span className="text-blue-500">├─</span>
                <span>dealer-scraper-mvp:</span>
              </div>
              <span className="font-mono text-blue-400">
                {isLoading ? '...' : stats.dealer_scraper_count.toLocaleString()}
              </span>
            </div>

            <div className="flex items-center justify-between text-slate-400">
              <div className="flex items-center gap-2">
                <span className="text-green-500">├─</span>
                <span>sales-agent:</span>
              </div>
              <span className="font-mono text-green-400">
                {isLoading ? '...' : stats.sales_agent_count.toLocaleString()}
              </span>
            </div>

            <div className="flex items-center justify-between text-slate-300 font-semibold pt-2 border-t border-slate-700/50">
              <div className="flex items-center gap-2">
                <span className="text-yellow-500">└─</span>
                <span>COMBINED:</span>
              </div>
              <span className="font-mono text-yellow-400">
                {isLoading ? '...' : stats.total_companies.toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-yellow-600 text-sm">
            <div className="animate-spin">⚙️</div>
            <span>Loading stats...</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
