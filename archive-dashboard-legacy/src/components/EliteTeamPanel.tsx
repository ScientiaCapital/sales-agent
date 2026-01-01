import { useEffect } from 'react';
import useSWR from 'swr';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

// Types
type AgentStatus = 'IDLE' | 'WATCHING' | 'HUNTING' | 'PROCESSING' | 'ERROR';

interface SignalScoutData {
  status: AgentStatus;
  lastRun: string;
  signalsDetected: Array<{ vertical: string; count: number }>;
  nextScan: string;
}

interface DeepHunterData {
  status: AgentStatus;
  activeRegion: string;
  scrapedToday: number;
  unicornsFound: number;
  oemsActive: string[];
}

interface IntakeCommanderData {
  status: AgentStatus;
  queueSize: number;
  todayStats: {
    newCompanies: number;
    dupesBlocked: number;
    sentToBDR: number;
  };
  trifectaScores: {
    unicorn: number;
    partial: number;
  };
}

interface EliteTeamResponse {
  signalScout: SignalScoutData;
  deepHunter: DeepHunterData;
  intakeCommander: IntakeCommanderData;
  lastUpdated: string;
}

// Fetcher for SWR
const fetcher = (url: string) => fetch(url).then((r) => r.json());

// Relative time formatter
const formatRelativeTime = (timestamp: string): string => {
  const now = new Date();
  const past = new Date(timestamp);
  const diffMs = now.getTime() - past.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
};

// Format next scan time
const formatNextScan = (timestamp: string): string => {
  const now = new Date();
  const next = new Date(timestamp);
  const diffMs = next.getTime() - now.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Now';
  if (diffMins < 60) return `${diffMins} min`;

  const diffHours = Math.floor(diffMins / 60);
  return `${diffHours}h ${diffMins % 60}m`;
};

// Status badge component
const StatusBadge = ({ status }: { status: AgentStatus }) => {
  const variants: Record<AgentStatus, { color: string; className: string }> = {
    IDLE: { color: 'gray', className: 'bg-gray-500/10 text-gray-600 border-gray-500/20' },
    WATCHING: { color: 'blue', className: 'bg-blue-500/10 text-blue-600 border-blue-500/20 animate-pulse' },
    HUNTING: { color: 'amber', className: 'bg-amber-500/10 text-amber-600 border-amber-500/20 animate-pulse' },
    PROCESSING: { color: 'green', className: 'bg-green-500/10 text-green-600 border-green-500/20 animate-pulse' },
    ERROR: { color: 'red', className: 'bg-red-500/10 text-red-600 border-red-500/20' },
  };

  const variant = variants[status];

  return (
    <Badge variant="outline" className={`${variant.className} font-mono text-xs`}>
      {status}
    </Badge>
  );
};

// Agent card component
const AgentCard = ({
  icon,
  name,
  status,
  children
}: {
  icon: string;
  name: string;
  status: AgentStatus;
  children: React.ReactNode;
}) => {
  return (
    <div className="rounded-lg border border-border bg-card p-4 transition-all hover:border-primary/50">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <h3 className="font-semibold text-foreground">{name}</h3>
        </div>
        <StatusBadge status={status} />
      </div>
      <div className="space-y-1 text-sm text-muted-foreground">
        {children}
      </div>
    </div>
  );
};

export function EliteTeamPanel() {
  const { data, error, mutate } = useSWR<EliteTeamResponse>(
    '/api/dashboard/elite-team',
    fetcher,
    {
      refreshInterval: 30000, // Auto-refresh every 30 seconds
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );

  // Manual refresh on mount
  useEffect(() => {
    mutate();
  }, [mutate]);

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span className="text-xl">🎖️</span>
            ELITE TEAM STATUS
          </h2>
          <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20">
            ERROR
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">Failed to load elite team status</p>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span className="text-xl">🎖️</span>
            ELITE TEAM STATUS
          </h2>
          <Badge variant="outline" className="bg-gray-500/10 text-gray-600 border-gray-500/20">
            LOADING
          </Badge>
        </div>
        <div className="space-y-3">
          <div className="h-24 rounded-lg border border-dashed border-border animate-pulse" />
          <div className="h-24 rounded-lg border border-dashed border-border animate-pulse" />
          <div className="h-24 rounded-lg border border-dashed border-border animate-pulse" />
        </div>
      </Card>
    );
  }

  const { signalScout, deepHunter, intakeCommander } = data;

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <span className="text-xl">🎖️</span>
          ELITE TEAM STATUS
        </h2>
        <Badge variant="outline" className="bg-purple-500/10 text-purple-600 border-purple-500/20 font-mono">
          SPEC OPS
        </Badge>
      </div>

      <div className="space-y-4">
        {/* Signal Scout */}
        <AgentCard icon="🔭" name="SIGNAL SCOUT" status={signalScout.status}>
          <div className="flex items-center justify-between">
            <span>Last run: {formatRelativeTime(signalScout.lastRun)}</span>
            <span className="text-xs">Next: {formatNextScan(signalScout.nextScan)}</span>
          </div>
          {signalScout.signalsDetected.length > 0 && (
            <div>
              Signals detected: {signalScout.signalsDetected.map((s, i) => (
                <span key={s.vertical}>
                  {s.vertical} ({s.count}){i < signalScout.signalsDetected.length - 1 ? ', ' : ''}
                </span>
              ))}
            </div>
          )}
          {signalScout.signalsDetected.length === 0 && (
            <div className="text-muted-foreground/60">No signals detected yet</div>
          )}
        </AgentCard>

        {/* Deep Hunter */}
        <AgentCard icon="🕵️" name="DEEP HUNTER" status={deepHunter.status}>
          <div className="flex items-center justify-between">
            <span>Active: {deepHunter.activeRegion || 'Idle'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Scraped today: {deepHunter.scrapedToday.toLocaleString()}</span>
            <span className="font-semibold text-amber-600">
              Unicorns found: {deepHunter.unicornsFound}
            </span>
          </div>
          {deepHunter.oemsActive.length > 0 && (
            <div className="truncate">
              OEMs active: {deepHunter.oemsActive.join(', ')}
            </div>
          )}
        </AgentCard>

        {/* Intake Commander */}
        <AgentCard icon="⚡" name="INTAKE COMMANDER" status={intakeCommander.status}>
          <div className="flex items-center justify-between">
            <span>Queue size: {intakeCommander.queueSize}</span>
          </div>
          <div>
            Today: +{intakeCommander.todayStats.newCompanies} new, {intakeCommander.todayStats.dupesBlocked} dupes blocked, {intakeCommander.todayStats.sentToBDR} → BDR
          </div>
          <div className="flex items-center gap-3">
            <span className="font-semibold text-purple-600">
              {intakeCommander.trifectaScores.unicorn} UNICORN
            </span>
            <span className="text-blue-600">
              {intakeCommander.trifectaScores.partial} PARTIAL
            </span>
          </div>
        </AgentCard>
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground text-center">
          Last updated: {formatRelativeTime(data.lastUpdated)}
        </p>
      </div>
    </Card>
  );
}
