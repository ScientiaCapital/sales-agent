import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Trophy, Medal, Award, Star, HelpCircle } from "lucide-react";

interface ICPQueueResponse {
  summary: {
    total_leads: number;
    untouched_count: number;
    by_quarter: { Q3: number; Q4: number; PPL: number };
  };
  tier_breakdown: { PLATINUM: number; GOLD: number; SILVER: number; BRONZE: number; UNSCORED: number };
  smart_views: Record<
    string,
    {
      name: string;
      color: string;
      priority: number;
      total: number;
      untouched: number;
      leads: any[];
    }
  >;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

interface TierCardProps {
  name: string;
  description: string;
  count: number;
  percentage: number;
  icon: React.ElementType;
  borderColor: string;
  iconColor: string;
  bgGradient: string;
}

function TierCard({
  name,
  description,
  count,
  percentage,
  icon: Icon,
  borderColor,
  iconColor,
  bgGradient,
}: TierCardProps) {
  return (
    <Card
      className={`border-2 ${borderColor} ${bgGradient} hover:shadow-xl transition-all duration-300 hover:scale-105`}
    >
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div
              className={`p-3 rounded-xl bg-gradient-to-br ${iconColor} bg-opacity-20`}
            >
              <Icon className={`h-7 w-7 ${iconColor.replace("from-", "text-").split(" ")[0]}`} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">{name}</h3>
              <p className="text-xs text-gray-400 uppercase tracking-wider">Tier</p>
            </div>
          </div>
        </div>
        <div className="mb-3">
          <div className="text-5xl font-black text-white mb-1">{count}</div>
          <div className="text-sm font-medium text-gray-300">
            {percentage.toFixed(1)}% of total pipeline
          </div>
        </div>
        <div className="text-sm text-gray-400 leading-relaxed">{description}</div>
      </CardContent>
    </Card>
  );
}

function TierCardSkeleton() {
  return (
    <Card className="border-2 border-gray-700">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <Skeleton className="h-16 w-16 rounded-xl" />
            <div>
              <Skeleton className="h-6 w-24 mb-2" />
              <Skeleton className="h-3 w-16" />
            </div>
          </div>
        </div>
        <Skeleton className="h-12 w-20 mb-3" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-3/4" />
      </CardContent>
    </Card>
  );
}

export function TierBreakdown() {
  const { data, isLoading, error } = useSWR<ICPQueueResponse>(
    "/api/dashboard/icp-queue?days=7&limit=10",
    fetcher,
    { refreshInterval: 60000 }
  );

  if (error) {
    return (
      <Card className="border border-red-500/30 bg-gradient-to-br from-slate-900/90 to-slate-800/90">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            ICP Tier Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-400">
            <p className="font-medium">Failed to load tier data</p>
            <p className="text-sm text-gray-500 mt-1">
              Please check if the backend server is running
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
          ICP Tier Breakdown
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(5)].map((_, i) => (
            <TierCardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const totalLeads = data.summary.total_leads;

  // Use real tier_breakdown data from API
  const tierBreakdown = data.tier_breakdown || { PLATINUM: 0, GOLD: 0, SILVER: 0, BRONZE: 0, UNSCORED: 0 };
  const tierData = [
    {
      name: "Platinum",
      description: "Full MEP+E contractors with complete service offerings. Highest priority targets with maximum revenue potential.",
      icon: Trophy,
      borderColor: "border-green-500",
      iconColor: "from-green-500 to-emerald-500 text-green-400",
      bgGradient: "bg-gradient-to-br from-slate-900/90 to-green-900/20",
      count: tierBreakdown.PLATINUM || 0,
    },
    {
      name: "Gold",
      description: "Energy + Multi-trade contractors. Strong fit with significant service breadth and growth potential.",
      icon: Medal,
      borderColor: "border-blue-500",
      iconColor: "from-blue-500 to-cyan-500 text-blue-400",
      bgGradient: "bg-gradient-to-br from-slate-900/90 to-blue-900/20",
      count: tierBreakdown.GOLD || 0,
    },
    {
      name: "Silver",
      description: "Multi-trade contractors without electrical services. Good fit with expansion opportunities.",
      icon: Award,
      borderColor: "border-orange-500",
      iconColor: "from-orange-500 to-amber-500 text-orange-400",
      bgGradient: "bg-gradient-to-br from-slate-900/90 to-orange-900/20",
      count: tierBreakdown.SILVER || 0,
    },
    {
      name: "Bronze",
      description: "Single trade specialty contractors. Niche focus with specific use case potential.",
      icon: Star,
      borderColor: "border-purple-500",
      iconColor: "from-purple-500 to-pink-500 text-purple-400",
      bgGradient: "bg-gradient-to-br from-slate-900/90 to-purple-900/20",
      count: tierBreakdown.BRONZE || 0,
    },
    {
      name: "Unscored",
      description: "Companies awaiting ICP classification. Requires enrichment and tier assignment.",
      icon: HelpCircle,
      borderColor: "border-gray-500",
      iconColor: "from-gray-500 to-slate-500 text-gray-400",
      bgGradient: "bg-gradient-to-br from-slate-900/90 to-gray-900/20",
      count: tierBreakdown.UNSCORED || 0,
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400">
          ICP Tier Breakdown
        </h2>
        <div className="text-right">
          <div className="text-3xl font-bold text-white">{totalLeads.toLocaleString()}</div>
          <div className="text-sm text-gray-400">Total Companies</div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tierData.map((tier) => (
          <TierCard
            key={tier.name}
            name={tier.name}
            description={tier.description}
            count={tier.count}
            percentage={(tier.count / totalLeads) * 100}
            icon={tier.icon}
            borderColor={tier.borderColor}
            iconColor={tier.iconColor}
            bgGradient={tier.bgGradient}
          />
        ))}
      </div>
    </div>
  );
}
