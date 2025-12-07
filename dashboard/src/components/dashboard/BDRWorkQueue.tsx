import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Phone,
  Mail,
  ClipboardList,
  Search,
  RefreshCw,
} from "lucide-react";

interface WorkQueueItem {
  id: string;
  company_name: string;
  task_type: string;
  priority: number;
  due_date?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  notes?: string;
}

interface WorkQueueResponse {
  tasks: WorkQueueItem[];
  total: number;
  by_priority: Record<string, number>;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const TASK_TYPE_CONFIG: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  CALL: { icon: Phone, color: "bg-green-100 text-green-700", label: "Call" },
  RESEARCH: { icon: Search, color: "bg-purple-100 text-purple-700", label: "Research" },
  FOLLOW_UP: { icon: RefreshCw, color: "bg-blue-100 text-blue-700", label: "Follow-up" },
  EMAIL: { icon: Mail, color: "bg-orange-100 text-orange-700", label: "Email" },
};

const PRIORITY_COLORS: Record<number, string> = {
  1: "bg-red-100 text-red-700 border-red-300",
  2: "bg-amber-100 text-amber-700 border-amber-300",
  3: "bg-gray-100 text-gray-700 border-gray-300",
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

type PriorityFilter = "all" | 1 | 2 | 3;
type TaskTypeFilter = "all" | "CALL" | "RESEARCH" | "FOLLOW_UP" | "EMAIL";

export function BDRWorkQueue() {
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("all");
  const [taskTypeFilter, setTaskTypeFilter] = useState<TaskTypeFilter>("all");

  const { data, isLoading, error } = useSWR<WorkQueueResponse>(
    "/api/dashboard/workqueue",
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  // Filter tasks based on priority and task type
  const filteredTasks = data?.tasks.filter(task => {
    const matchesPriority = priorityFilter === "all" || task.priority === priorityFilter;
    const matchesType = taskTypeFilter === "all" || task.task_type === taskTypeFilter;
    return matchesPriority && matchesType;
  }) ?? [];

  if (error) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <ClipboardList className="h-5 w-5" />
            BDR Work Queue
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <p className="font-medium">Failed to load work queue</p>
            <p className="text-sm text-muted-foreground">Please try refreshing the page</p>
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

  const p1Count = data.by_priority?.P1 || 0;
  const p2Count = data.by_priority?.P2 || 0;
  const p3Count = data.by_priority?.P3 || 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <ClipboardList className="h-5 w-5" />
            BDR Work Queue
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {data.total} tasks
          </Badge>
        </div>
        {/* Priority summary badges */}
        <div className="flex gap-2 mt-2 flex-wrap">
          {p1Count > 0 && (
            <Badge className="bg-red-100 text-red-700 text-xs">
              {p1Count} P1 (urgent)
            </Badge>
          )}
          {p2Count > 0 && (
            <Badge className="bg-amber-100 text-amber-700 text-xs">
              {p2Count} P2 (high)
            </Badge>
          )}
          {p3Count > 0 && (
            <Badge className="bg-gray-100 text-gray-700 text-xs">
              {p3Count} P3 (normal)
            </Badge>
          )}
        </div>

        {/* Filter Chips */}
        <div className="mt-3 space-y-2">
          {/* Priority Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground font-medium">Priority:</span>
            {(["all", 1, 2, 3] as PriorityFilter[]).map((priority) => (
              <Button
                key={String(priority)}
                variant={priorityFilter === priority ? "default" : "outline"}
                size="sm"
                className={`h-6 px-2 text-xs ${
                  priorityFilter === priority
                    ? "bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
                    : priority === 1 ? "hover:bg-red-100" :
                      priority === 2 ? "hover:bg-amber-100" :
                      priority === 3 ? "hover:bg-gray-100" : ""
                }`}
                onClick={() => setPriorityFilter(priority)}
              >
                {priority === "all" ? "All" : `P${priority}`}
              </Button>
            ))}
          </div>

          {/* Task Type Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground font-medium">Type:</span>
            {(["all", "CALL", "RESEARCH", "FOLLOW_UP", "EMAIL"] as TaskTypeFilter[]).map((type) => (
              <Button
                key={type}
                variant={taskTypeFilter === type ? "default" : "outline"}
                size="sm"
                className={`h-6 px-2 text-xs ${
                  taskTypeFilter === type
                    ? "bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
                    : type === "CALL" ? "hover:bg-green-100" :
                      type === "RESEARCH" ? "hover:bg-purple-100" :
                      type === "FOLLOW_UP" ? "hover:bg-blue-100" :
                      type === "EMAIL" ? "hover:bg-orange-100" : ""
                }`}
                onClick={() => setTaskTypeFilter(type)}
              >
                {type === "all" ? "All Types" : type.replace("_", " ")}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {filteredTasks.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <p className="font-medium">Queue empty!</p>
            <p className="text-sm">No tasks pending.</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {filteredTasks.map((task) => {
              const taskConfig = TASK_TYPE_CONFIG[task.task_type] || TASK_TYPE_CONFIG.CALL;
              const IconComponent = taskConfig.icon;
              const priorityColor = PRIORITY_COLORS[task.priority] || PRIORITY_COLORS[3];
              const isUrgent = task.priority === 1;

              return (
                <div
                  key={task.id}
                  className={`flex flex-col gap-2 p-3 rounded-lg border transition-all ${
                    isUrgent
                      ? "border-red-300 bg-red-50/50 shadow-sm"
                      : "border-gray-200 hover:bg-muted/50"
                  }`}
                >
                  {/* Header Row */}
                  <div className="flex items-start gap-3">
                    <Checkbox id={task.id} className="mt-1" />
                    <div className={`mt-0.5 p-1 rounded ${taskConfig.color}`}>
                      <IconComponent className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      {/* Company + Priority */}
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-semibold text-sm truncate">
                          {task.company_name}
                        </p>
                        <Badge className={`${priorityColor} text-xs px-1.5 py-0`}>
                          P{task.priority}
                        </Badge>
                        <Badge className={`${taskConfig.color} text-xs px-1.5 py-0`}>
                          {taskConfig.label}
                        </Badge>
                      </div>

                      {/* Notes */}
                      {task.notes && (
                        <p className="text-xs text-muted-foreground mb-2">
                          {task.notes}
                        </p>
                      )}

                      {/* Contact Info */}
                      {task.contact_name && (
                        <div className="flex flex-col gap-1 text-xs">
                          <span className="font-medium">{task.contact_name}</span>
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
                          </div>
                        </div>
                      )}
                    </div>
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
