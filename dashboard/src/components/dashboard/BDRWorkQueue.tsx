"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  UserPlus,
  Phone,
  PhoneIncoming,
  PhoneMissed,
  Mail,
  ClipboardList,
} from "lucide-react";

interface Task {
  id: string;
  task_type: string;
  label: string;
  company_name: string;
  score: number | null;
  is_atl: boolean;
  due: string;
  icon: string;
  color: string;
  priority: number;
}

interface WorkQueueResponse {
  tasks: Task[];
  summary: {
    total: number;
    new_leads: number;
    follow_ups: number;
    callbacks: number;
  };
  data_source: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  "user-plus": UserPlus,
  phone: Phone,
  "phone-incoming": PhoneIncoming,
  "phone-missed": PhoneMissed,
  mail: Mail,
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
        <div className="flex gap-2 mt-2">
          {data.summary.new_leads > 0 && (
            <Badge className="bg-blue-100 text-blue-700 text-xs">
              {data.summary.new_leads} new leads
            </Badge>
          )}
          {data.summary.follow_ups > 0 && (
            <Badge className="bg-green-100 text-green-700 text-xs">
              {data.summary.follow_ups} follow-ups
            </Badge>
          )}
          {data.summary.callbacks > 0 && (
            <Badge className="bg-amber-100 text-amber-700 text-xs">
              {data.summary.callbacks} callbacks
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
          <div className="space-y-2 max-h-[350px] overflow-y-auto">
            {data.tasks.map((task) => {
              const IconComponent = ICON_MAP[task.icon] || Phone;

              return (
                <div
                  key={task.id}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <Checkbox id={task.id} />
                  <div style={{ color: task.color }}>
                    <IconComponent className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm truncate">
                        {task.company_name}
                      </p>
                      {task.is_atl && (
                        <Badge className="bg-green-100 text-green-700 text-xs px-1">
                          ATL
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{task.label}</span>
                      {task.score && (
                        <span className="text-[var(--turkish-blue)]">
                          Score: {task.score}
                        </span>
                      )}
                    </div>
                  </div>
                  <Badge
                    variant={
                      task.due === "ASAP"
                        ? "destructive"
                        : task.due === "Overdue"
                        ? "outline"
                        : "secondary"
                    }
                    className={
                      task.due === "Overdue"
                        ? "border-amber-500 text-amber-600"
                        : ""
                    }
                  >
                    {task.due}
                  </Badge>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
