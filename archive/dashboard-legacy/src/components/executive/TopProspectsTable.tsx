import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, ExternalLink, TrendingUp } from "lucide-react";

interface WorkQueueItem {
  id: string;
  company_name: string;
  state: string;
  lead_score: number;
  icp_tier?: string;
  website?: string;
  contact_name?: string;
  contact_title?: string;
  close_lead_url?: string;
}

interface WorkQueueResponse {
  tasks: WorkQueueItem[];
  total: number;
  by_priority: Record<string, number>;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function getScoreBadgeColor(score: number): string {
  if (score >= 80) return "bg-green-500/20 text-green-400 border-green-500/50";
  if (score >= 60) return "bg-blue-500/20 text-blue-400 border-blue-500/50";
  if (score >= 40) return "bg-orange-500/20 text-orange-400 border-orange-500/50";
  return "bg-gray-500/20 text-gray-400 border-gray-500/50";
}

function getTierBadgeColor(tier?: string): string {
  if (!tier) return "bg-gray-500/20 text-gray-400 border-gray-500/50";
  switch (tier.toLowerCase()) {
    case "platinum":
      return "bg-green-500/20 text-green-400 border-green-500/50";
    case "gold":
      return "bg-blue-500/20 text-blue-400 border-blue-500/50";
    case "silver":
      return "bg-orange-500/20 text-orange-400 border-orange-500/50";
    case "bronze":
      return "bg-purple-500/20 text-purple-400 border-purple-500/50";
    default:
      return "bg-gray-500/20 text-gray-400 border-gray-500/50";
  }
}

function TableRowSkeleton() {
  return (
    <tr className="border-b border-gray-800/50">
      <td className="px-4 py-3">
        <Skeleton className="h-6 w-16" />
      </td>
      <td className="px-4 py-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-3 w-32 mt-1" />
      </td>
      <td className="px-4 py-3">
        <Skeleton className="h-6 w-20" />
      </td>
      <td className="px-4 py-3">
        <Skeleton className="h-6 w-12" />
      </td>
      <td className="px-4 py-3">
        <Skeleton className="h-4 w-32" />
      </td>
    </tr>
  );
}

export function TopProspectsTable() {
  const { data, isLoading, error } = useSWR<WorkQueueResponse>(
    "/api/dashboard/workqueue?limit=20",
    fetcher,
    { refreshInterval: 60000 }
  );

  if (error) {
    return (
      <Card className="border border-red-500/30 bg-gradient-to-br from-slate-900/90 to-slate-800/90">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            Top 20 Prospects
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-400">
            <p className="font-medium">Failed to load prospects</p>
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
      <Card className="border border-purple-500/30 bg-gradient-to-br from-slate-900/90 to-purple-900/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
            <TrendingUp className="h-5 w-5 text-purple-400" />
            Top 20 Prospects
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Score
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Company
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Tier
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    State
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Website
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...Array(10)].map((_, i) => (
                  <TableRowSkeleton key={i} />
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    );
  }

  const topProspects = (data.tasks || []).slice(0, 20);

  return (
    <Card className="border border-purple-500/30 bg-gradient-to-br from-slate-900/90 to-purple-900/10">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400">
            <TrendingUp className="h-5 w-5 text-purple-400" />
            Top 20 Prospects
          </CardTitle>
          <Badge
            variant="outline"
            className="bg-purple-500/10 text-purple-300 border-purple-500/50"
          >
            {data.total.toLocaleString()} total leads
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Score
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Company
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Tier
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  State
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Website
                </th>
              </tr>
            </thead>
            <tbody>
              {topProspects.map((prospect, index) => (
                <tr
                  key={prospect.id}
                  className={`border-b border-gray-800/50 hover:bg-purple-500/5 transition-colors ${
                    index < 3 ? "bg-gradient-to-r from-purple-500/10 to-transparent" : ""
                  }`}
                >
                  {/* Score Badge */}
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={`font-bold text-sm ${getScoreBadgeColor(prospect.lead_score)}`}
                    >
                      {prospect.lead_score}
                    </Badge>
                  </td>

                  {/* Company Name */}
                  <td className="px-4 py-3">
                    <div>
                      <div className="font-semibold text-white hover:text-purple-300 transition-colors">
                        {prospect.company_name}
                      </div>
                      {prospect.contact_name && (
                        <div className="text-xs text-gray-400 mt-0.5">
                          {prospect.contact_name}
                          {prospect.contact_title && ` • ${prospect.contact_title}`}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Tier Badge */}
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={`text-xs ${getTierBadgeColor(prospect.icp_tier)}`}
                    >
                      {prospect.icp_tier || "Unscored"}
                    </Badge>
                  </td>

                  {/* State Badge */}
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className="text-xs bg-slate-700/30 text-slate-300 border-slate-600/50"
                    >
                      {prospect.state || "N/A"}
                    </Badge>
                  </td>

                  {/* Website Link */}
                  <td className="px-4 py-3">
                    {prospect.website ? (
                      <a
                        href={
                          prospect.website.startsWith("http")
                            ? prospect.website
                            : `https://${prospect.website}`
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 transition-colors inline-flex items-center gap-1 text-sm"
                      >
                        Visit
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-gray-500 text-sm">N/A</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
