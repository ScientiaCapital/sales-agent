"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  UserPlus,
  Phone,
  PhoneIncoming,
  PhoneMissed,
  Mail,
  ClipboardList,
  Flame,
  Search,
  RefreshCw,
  UserCheck,
  Linkedin,
  ExternalLink,
} from "lucide-react";

interface Task {
  id: string;
  rank: number;
  task_type: "hot_intent" | "new_lead" | "follow_up" | "research" | string;
  recommended_action: string;
  action_reason: string;
  company_name: string;
  icp_tier: "PLATINUM" | "GOLD" | "SILVER" | "BRONZE" | null;
  icp_score: number | null;
  total_touches: number;
  days_since_activity: number;
  days_in_pipeline: number;
  opportunity_value: number | null;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  contact_title: string | null;
  contact_linkedin: string | null;
  close_url: string | null;
  icon: string;
  color: string;
}

interface WorkQueueResponse {
  tasks: Task[];
  summary: {
    total: number;
    hot_intent: number;
    new_leads: number;
    follow_ups: number;
    research: number;
  };
  data_source: "star_schema" | "mock";
  view: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  flame: Flame,
  "user-plus": UserPlus,
  phone: Phone,
  "phone-incoming": PhoneIncoming,
  "phone-missed": PhoneMissed,
  mail: Mail,
  search: Search,
  "refresh-cw": RefreshCw,
  "user-check": UserCheck,
  linkedin: Linkedin,
};

const ICP_TIER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  PLATINUM: { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-300" },
  GOLD: { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-300" },
  SILVER: { bg: "bg-gray-100", text: "text-gray-700", border: "border-gray-300" },
  BRONZE: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-300" },
};

function TaskSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="flex items-center gap-3 p-2">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-5 w-5 rounded-full" />
          <div className="flex-1">
            <Skeleton className="h-4 w-40 mb-1" />
            <Skeleton className="h-3 w-24" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function BDRWorkQueue() {
  const { data, isLoading } = useSWR<WorkQueueResponse>(
    "/api/workqueue",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <ClipboardList className="h-5 w-5" />
            BDR Work Queue
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TaskSkeleton />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <ClipboardList className="h-5 w-5" />
            BDR Work Queue
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {data.summary.total} tasks
          </Badge>
        </div>
        {/* Summary badges */}
        <div className="flex gap-2 mt-2 flex-wrap">
          {data.summary.hot_intent > 0 && (
            <Badge className="bg-red-100 text-red-700 text-xs flex items-center gap-1">
              <Flame className="h-3 w-3" />
              {data.summary.hot_intent} hot intent
            </Badge>
          )}
          {data.summary.new_leads > 0 && (
            <Badge className="bg-blue-100 text-blue-700 text-xs flex items-center gap-1">
              <UserPlus className="h-3 w-3" />
              {data.summary.new_leads} new leads
            </Badge>
          )}
          {data.summary.follow_ups > 0 && (
            <Badge className="bg-green-100 text-green-700 text-xs flex items-center gap-1">
              <RefreshCw className="h-3 w-3" />
              {data.summary.follow_ups} follow-ups
            </Badge>
          )}
          {data.summary.research > 0 && (
            <Badge className="bg-purple-100 text-purple-700 text-xs flex items-center gap-1">
              <Search className="h-3 w-3" />
              {data.summary.research} research
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {data.tasks.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <p className="font-medium">Queue empty!</p>
            <p className="text-sm">No tasks pending.</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {data.tasks.map((task) => {
              const IconComponent = ICON_MAP[task.icon] || Phone;
              const tierColors = task.icp_tier ? ICP_TIER_COLORS[task.icp_tier] : null;
              const isHotIntent = task.task_type === "hot_intent";

              return (
                <div
                  key={task.id}
                  className={`flex flex-col gap-2 p-3 rounded-lg border transition-all ${
                    isHotIntent
                      ? "border-red-300 bg-red-50/50 shadow-sm"
                      : "border-gray-200 hover:bg-muted/50"
                  }`}
                >
                  {/* Header Row */}
                  <div className="flex items-start gap-3">
                    <Checkbox id={task.id} className="mt-1" />
                    <div style={{ color: task.color }} className="mt-0.5">
                      <IconComponent className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      {/* Company + ICP Tier */}
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-semibold text-sm truncate">
                          {task.company_name}
                        </p>
                        {tierColors && (
                          <Badge
                            className={`${tierColors.bg} ${tierColors.text} text-xs px-1.5 py-0`}
                          >
                            {task.icp_tier}
                          </Badge>
                        )}
                      </div>

                      {/* Recommended Action */}
                      <p className="font-medium text-sm text-[var(--turkish-blue)] mb-1">
                        {task.recommended_action}
                      </p>

                      {/* Action Reason */}
                      <p className="text-xs text-muted-foreground mb-2">
                        {task.action_reason}
                      </p>

                      {/* Contact Info */}
                      {task.contact_name && (
                        <div className="flex flex-col gap-1 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{task.contact_name}</span>
                            {task.contact_title && (
                              <span className="text-muted-foreground">
                                • {task.contact_title}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 flex-wrap">
                            {task.contact_phone && (
                              <a
                                href={`tel:${task.contact_phone}`}
                                className="text-[var(--turkish-blue)] hover:underline flex items-center gap-1"
                              >
                                <Phone className="h-3 w-3" />
                                {task.contact_phone}
                              </a>
                            )}
                            {task.contact_email && (
                              <a
                                href={`mailto:${task.contact_email}`}
                                className="text-[var(--turkish-blue)] hover:underline flex items-center gap-1"
                              >
                                <Mail className="h-3 w-3" />
                                {task.contact_email}
                              </a>
                            )}
                            {task.contact_linkedin && (
                              <a
                                href={
                                  task.contact_linkedin.startsWith("http")
                                    ? task.contact_linkedin
                                    : `https://${task.contact_linkedin}`
                                }
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[var(--turkish-blue)] hover:underline flex items-center gap-1"
                              >
                                <Linkedin className="h-3 w-3" />
                                LinkedIn
                              </a>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Footer Row - Metrics + Close Link */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground ml-9">
                    <div className="flex items-center gap-3 flex-wrap">
                      {task.days_since_activity !== null && (
                        <span
                          className={
                            task.days_since_activity > 7
                              ? "text-amber-600 font-medium"
                              : ""
                          }
                        >
                          {task.days_since_activity}d since activity
                        </span>
                      )}
                      {task.total_touches > 0 && (
                        <span>{task.total_touches} touches</span>
                      )}
                      {task.icp_score !== null && (
                        <span className="text-[var(--turkish-blue)]">
                          Score: {task.icp_score}
                        </span>
                      )}
                      {task.opportunity_value !== null && task.opportunity_value > 0 && (
                        <span className="text-green-600 font-medium">
                          ${(task.opportunity_value / 1000).toFixed(0)}K
                        </span>
                      )}
                    </div>
                    {task.close_url && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-[var(--turkish-blue)] hover:text-[var(--turkish-blue)]"
                        asChild
                      >
                        <a
                          href={task.close_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Open in Close
                          <ExternalLink className="h-3 w-3 ml-1" />
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
