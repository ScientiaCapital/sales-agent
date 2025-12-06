"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  Building2,
  Phone,
  Mail,
  Globe,
  User,
} from "lucide-react";

interface ImportData {
  id: string;
  filename: string;
  imported_at: string;
  total_rows: number;
  fields: {
    company_name: boolean;
    phone: boolean;
    email: boolean;
    website: boolean;
    contact_name: boolean;
  };
  source: string;
  progress: {
    processed: number;
    qualified: number;
    enriched: number;
    exported: number;
    failed: number;
    progress_pct: number;
    qualification_rate: number;
  };
}

interface ImportsResponse {
  imports: ImportData[];
  total: number;
  data_source: string;
  updated_at: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

function ImportSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2].map((i) => (
        <div key={i} className="border rounded-lg p-3">
          <Skeleton className="h-4 w-48 mb-2" />
          <Skeleton className="h-3 w-32 mb-2" />
          <Skeleton className="h-2 w-full" />
        </div>
      ))}
    </div>
  );
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ImportHistory() {
  const { data, isLoading } = useSWR<ImportsResponse>(
    "/api/dashboard/imports?limit=5",
    fetcher,
    { refreshInterval: 300000 } // Refresh every 5 min
  );

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            Recent Imports
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ImportSkeleton />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            Recent Imports
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {data.total} total
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {data.imports.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            <p className="font-medium">No imports yet</p>
            <p className="text-sm">Import a CSV to get started.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {data.imports.map((imp) => (
              <div
                key={imp.id}
                className="border rounded-lg p-3 hover:bg-muted/30 transition-colors"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-sm truncate max-w-[200px]">
                      {imp.filename}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(imp.imported_at)} • {imp.total_rows.toLocaleString()} rows
                    </p>
                  </div>
                  <Badge
                    variant={imp.progress.progress_pct >= 100 ? "default" : "outline"}
                    className={
                      imp.progress.progress_pct >= 100
                        ? "bg-green-100 text-green-700"
                        : ""
                    }
                  >
                    {imp.progress.progress_pct.toFixed(0)}%
                  </Badge>
                </div>

                {/* Field availability */}
                <div className="flex gap-1 mb-2 flex-wrap">
                  <FieldBadge
                    icon={Building2}
                    label="Company"
                    available={imp.fields.company_name}
                  />
                  <FieldBadge
                    icon={Phone}
                    label="Phone"
                    available={imp.fields.phone}
                  />
                  <FieldBadge
                    icon={Mail}
                    label="Email"
                    available={imp.fields.email}
                  />
                  <FieldBadge
                    icon={Globe}
                    label="Website"
                    available={imp.fields.website}
                  />
                  <FieldBadge
                    icon={User}
                    label="Contact"
                    available={imp.fields.contact_name}
                  />
                </div>

                {/* Progress bar */}
                <Progress value={imp.progress.progress_pct} className="h-2 mb-2" />

                {/* Stats */}
                <div className="flex gap-3 text-xs text-muted-foreground">
                  <span className="text-green-600">
                    {imp.progress.qualified} qualified
                  </span>
                  <span className="text-blue-600">
                    {imp.progress.enriched} enriched
                  </span>
                  <span className="text-purple-600">
                    {imp.progress.exported} exported
                  </span>
                  {imp.progress.failed > 0 && (
                    <span className="text-red-600">
                      {imp.progress.failed} failed
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FieldBadge({
  icon: Icon,
  label,
  available,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  available: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-xs ${
        available
          ? "bg-green-50 text-green-700"
          : "bg-red-50 text-red-400 line-through"
      }`}
    >
      {available ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <XCircle className="h-3 w-3" />
      )}
      <span>{label}</span>
    </div>
  );
}
