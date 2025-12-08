import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import {
  Mail,
  MessageSquare,
  Phone,
  RefreshCw,
  Trash2,
  Send,
  Filter,
  CheckCheck,
  Edit,
  ExternalLink,
  Upload,
} from "lucide-react";

interface Draft {
  draft_id: string;
  company_id: string;
  draft_type: "email" | "sms" | "voice";
  status: "pending" | "approved" | "sent" | "discarded";
  company_name: string;
  contact_name: string | null;
  contact_title: string | null;
  subject: string | null; // Email only
  body: string;
  personal_hooks: Array<{ type: string; hook: string }>;
  close_lead_url: string | null; // "Open in Close" CRM link
  confidence: number;
  generated_at: string;
  updated_at: string;
  sent_at: string | null;
}

interface DraftListResponse {
  drafts: Draft[];
  total: number;
  page?: number;
  page_size?: number;
}

const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8001";

// Use /api/v1 prefix for FastAPI endpoints
const API_BASE = `${apiUrl}/api/v1`;

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const DRAFT_TYPE_CONFIG: Record<
  Draft["draft_type"],
  {
    icon: React.ComponentType<{ className?: string }>;
    color: string;
    label: string;
  }
> = {
  email: { icon: Mail, color: "text-blue-600", label: "Email" },
  sms: { icon: MessageSquare, color: "text-green-600", label: "SMS" },
  voice: { icon: Phone, color: "text-purple-600", label: "Voice Script" },
};

function DraftSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="p-4 border rounded-lg">
          <div className="flex items-start gap-3">
            <Skeleton className="h-4 w-4 mt-1" />
            <Skeleton className="h-5 w-5 rounded-full" />
            <div className="flex-1">
              <Skeleton className="h-4 w-48 mb-2" />
              <Skeleton className="h-3 w-32 mb-3" />
              <Skeleton className="h-20 w-full" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

type DraftTypeFilter = "all" | "email" | "sms" | "voice";

export function DraftReviewQueue() {
  const [typeFilter, setTypeFilter] = useState<DraftTypeFilter>("all");
  const [selectedDrafts, setSelectedDrafts] = useState<Set<string>>(new Set());
  const [editingDrafts, setEditingDrafts] = useState<Map<string, string>>(
    new Map()
  );
  const [characterCounts, setCharacterCounts] = useState<Map<string, number>>(
    new Map()
  );

  const { data, error, isLoading, mutate } = useSWR<DraftListResponse>(
    `${API_BASE}/ai/drafts?status=pending`,
    fetcher,
    { refreshInterval: 30000 } // Refresh every 30s
  );

  // Filter drafts by type
  const filteredDrafts =
    data?.drafts.filter(
      (draft) => typeFilter === "all" || draft.draft_type === typeFilter
    ) ?? [];

  // Toggle single draft selection
  const toggleDraftSelection = (draftId: string) => {
    setSelectedDrafts((prev) => {
      const next = new Set(prev);
      if (next.has(draftId)) {
        next.delete(draftId);
      } else {
        next.add(draftId);
      }
      return next;
    });
  };

  // Toggle all visible drafts (used by "Select All" checkbox in header)
  const toggleAllDrafts = () => {
    if (selectedDrafts.size === filteredDrafts.length) {
      setSelectedDrafts(new Set());
    } else {
      setSelectedDrafts(new Set(filteredDrafts.map((d) => d.draft_id)));
    }
  };
  // Expose for potential future "Select All" checkbox
  void toggleAllDrafts;

  // Start editing a draft
  const startEditing = (draftId: string, currentBody: string) => {
    setEditingDrafts((prev) => {
      const next = new Map(prev);
      next.set(draftId, currentBody);
      return next;
    });
    setCharacterCounts((prev) => {
      const next = new Map(prev);
      next.set(draftId, currentBody.length);
      return next;
    });
  };

  // Update draft body while editing
  const updateDraftBody = (draftId: string, newBody: string) => {
    setEditingDrafts((prev) => {
      const next = new Map(prev);
      next.set(draftId, newBody);
      return next;
    });
    setCharacterCounts((prev) => {
      const next = new Map(prev);
      next.set(draftId, newBody.length);
      return next;
    });
  };

  // Save edited draft
  const saveEdit = async (draftId: string) => {
    const editedBody = editingDrafts.get(draftId);
    if (!editedBody) return;

    try {
      await fetch(`${API_BASE}/ai/drafts/${draftId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: editedBody }),
      });
      setEditingDrafts((prev) => {
        const next = new Map(prev);
        next.delete(draftId);
        return next;
      });
      mutate(); // Refresh data
    } catch (err) {
      console.error("Failed to save edit:", err);
    }
  };

  // Cancel editing
  const cancelEdit = (draftId: string) => {
    setEditingDrafts((prev) => {
      const next = new Map(prev);
      next.delete(draftId);
      return next;
    });
    setCharacterCounts((prev) => {
      const next = new Map(prev);
      next.delete(draftId);
      return next;
    });
  };

  // Regenerate draft
  const regenerateDraft = async (draftId: string) => {
    try {
      await fetch(`${API_BASE}/ai/drafts/${draftId}/regenerate`, {
        method: "POST",
      });
      mutate(); // Refresh data
    } catch (err) {
      console.error("Failed to regenerate:", err);
    }
  };

  // Approve and send single draft
  const approveAndSend = async (draftId: string) => {
    try {
      await fetch(`${API_BASE}/ai/drafts/${draftId}/send`, {
        method: "POST",
      });
      mutate(); // Refresh data
    } catch (err) {
      console.error("Failed to send:", err);
    }
  };

  // Discard single draft
  const discardDraft = async (draftId: string) => {
    try {
      await fetch(`${API_BASE}/ai/drafts/${draftId}`, {
        method: "DELETE",
      });
      mutate(); // Refresh data
    } catch (err) {
      console.error("Failed to discard:", err);
    }
  };

  // Stage draft to Close CRM as a real email draft
  const stageToClose = async (draftId: string) => {
    try {
      const response = await fetch(`${API_BASE}/ai/drafts/${draftId}/stage`, {
        method: "POST",
      });
      const result = await response.json();

      if (response.ok && result.close_lead_url) {
        // Open Close CRM in new tab so user can review/send the draft
        window.open(result.close_lead_url, "_blank");
      } else if (!response.ok) {
        // Show error message from API
        alert(result.detail || "Failed to stage draft to Close CRM");
      }

      mutate(); // Refresh data
    } catch (err) {
      console.error("Failed to stage to Close:", err);
      alert("Failed to stage draft to Close CRM. Check console for details.");
    }
  };

  // Bulk approve selected drafts
  const bulkApprove = async () => {
    try {
      await Promise.all(
        Array.from(selectedDrafts).map((id) =>
          fetch(`${API_BASE}/ai/drafts/${id}/send`, { method: "POST" })
        )
      );
      setSelectedDrafts(new Set());
      mutate(); // Refresh data
    } catch (err) {
      console.error("Failed to bulk approve:", err);
    }
  };

  // Format relative time
  const formatRelativeTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Confidence badge color
  const getConfidenceBadgeColor = (confidence: number | null): string => {
    if (!confidence) return "bg-gray-100 text-gray-700";
    if (confidence >= 0.8) return "bg-green-100 text-green-700";
    if (confidence >= 0.6) return "bg-yellow-100 text-yellow-700";
    return "bg-red-100 text-red-700";
  };

  if (error) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <CheckCheck className="h-5 w-5" />
            Draft Review Queue
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6 text-red-500">
            <p className="font-medium">Failed to load drafts</p>
            <p className="text-sm text-muted-foreground">
              Please try refreshing the page
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
            <CheckCheck className="h-5 w-5" />
            Draft Review Queue
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DraftSkeleton />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-[var(--turkish-blue)] flex items-center gap-2">
            <CheckCheck className="h-5 w-5" />
            Draft Review Queue
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {data.total} pending
          </Badge>
        </div>

        {/* Type Filters */}
        <div className="flex items-center gap-2 flex-wrap mt-3">
          <Filter className="h-4 w-4 text-muted-foreground" />
          {(["all", "email", "sms", "voice"] as DraftTypeFilter[]).map(
            (type) => {
              const config =
                type !== "all"
                  ? DRAFT_TYPE_CONFIG[type as Draft["draft_type"]]
                  : null;
              const Icon = config?.icon;

              return (
                <Button
                  key={type}
                  variant={typeFilter === type ? "default" : "outline"}
                  size="sm"
                  className={`h-7 px-2 text-xs ${
                    typeFilter === type
                      ? "bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
                      : ""
                  }`}
                  onClick={() => setTypeFilter(type)}
                >
                  {Icon && <Icon className="h-3 w-3 mr-1" />}
                  {type === "all"
                    ? "All"
                    : config?.label || type.toUpperCase()}
                </Button>
              );
            }
          )}
        </div>

        {/* Bulk Actions */}
        {selectedDrafts.size > 0 && (
          <div className="flex items-center gap-2 mt-3 p-2 bg-blue-50 rounded-md border border-blue-200">
            <span className="text-xs font-medium text-blue-700">
              {selectedDrafts.size} selected
            </span>
            <Button
              size="sm"
              className="h-7 px-2 text-xs bg-green-600 hover:bg-green-700"
              onClick={bulkApprove}
            >
              <CheckCheck className="h-3 w-3 mr-1" />
              Approve All
            </Button>
          </div>
        )}
      </CardHeader>

      <CardContent>
        {filteredDrafts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <CheckCheck className="h-12 w-12 mx-auto mb-3 text-green-500" />
            <p className="font-medium">All caught up!</p>
            <p className="text-sm">No pending drafts to review.</p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {filteredDrafts.map((draft) => {
              const config = DRAFT_TYPE_CONFIG[draft.draft_type];
              const IconComponent = config.icon;
              const isEditing = editingDrafts.has(draft.draft_id);
              const editedBody = editingDrafts.get(draft.draft_id) || draft.body;
              const charCount = characterCounts.get(draft.draft_id) || draft.body.length;
              const isSmsOverLimit = draft.draft_type === "sms" && charCount > 160;

              return (
                <div
                  key={draft.draft_id}
                  className="flex flex-col gap-3 p-4 rounded-lg border border-gray-200 hover:bg-muted/50 transition-all"
                >
                  {/* Header Row */}
                  <div className="flex items-start gap-3">
                    <Checkbox
                      id={draft.draft_id}
                      checked={selectedDrafts.has(draft.draft_id)}
                      onCheckedChange={() => toggleDraftSelection(draft.draft_id)}
                      className="mt-1"
                    />
                    <div className={`${config.color} mt-0.5`}>
                      <IconComponent className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      {/* Company + Contact */}
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-semibold text-sm">
                          {draft.company_name}
                        </p>
                        {draft.contact_name && (
                          <span className="text-xs text-muted-foreground">
                            • {draft.contact_name}
                          </span>
                        )}
                      </div>

                      {/* Draft Type Badge + Confidence */}
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className={`${config.color} text-xs px-1.5 py-0`}>
                          {config.label}
                        </Badge>
                        {draft.confidence !== null && (
                          <Badge
                            className={`${getConfidenceBadgeColor(
                              draft.confidence
                            )} text-xs px-1.5 py-0`}
                          >
                            {Math.round(draft.confidence * 100)}%
                            confidence
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(draft.generated_at)}
                        </span>
                      </div>

                      {/* Email Subject */}
                      {draft.draft_type === "email" && draft.subject && (
                        <p className="text-sm font-medium text-gray-700 mb-2">
                          Subject: {draft.subject}
                        </p>
                      )}

                      {/* Body (Editable or Display) */}
                      {isEditing ? (
                        <div>
                          <textarea
                            value={editedBody}
                            onChange={(e) =>
                              updateDraftBody(draft.draft_id, e.target.value)
                            }
                            className="w-full p-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--turkish-blue)] resize-none"
                            rows={6}
                          />
                          {/* Character Count for SMS */}
                          {draft.draft_type === "sms" && (
                            <p
                              className={`text-xs mt-1 ${
                                isSmsOverLimit
                                  ? "text-red-600 font-semibold"
                                  : "text-muted-foreground"
                              }`}
                            >
                              {charCount}/160 characters
                              {isSmsOverLimit && " (over limit!)"}
                            </p>
                          )}
                          {/* Edit Actions */}
                          <div className="flex gap-2 mt-2">
                            <Button
                              size="sm"
                              className="h-7 px-2 text-xs bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
                              onClick={() => saveEdit(draft.draft_id)}
                            >
                              Save
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 px-2 text-xs"
                              onClick={() => cancelEdit(draft.draft_id)}
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <p className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded-md border">
                            {draft.body}
                          </p>
                          {/* Character Count for SMS (Display Mode) */}
                          {draft.draft_type === "sms" && (
                            <p
                              className={`text-xs mt-1 ${
                                draft.body.length > 160
                                  ? "text-red-600 font-semibold"
                                  : "text-muted-foreground"
                              }`}
                            >
                              {draft.body.length}/160 characters
                              {draft.body.length > 160 && " (over limit!)"}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  {!isEditing && (
                    <div className="flex items-center gap-2 ml-9 flex-wrap">
                      {/* Open in Close CRM - shows first when available */}
                      {draft.close_lead_url && (
                        <a
                          href={draft.close_lead_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-xs border-[var(--turkish-blue)] text-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/10"
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            Open in Close
                          </Button>
                        </a>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2 text-xs"
                        onClick={() => startEditing(draft.draft_id, draft.body)}
                      >
                        <Edit className="h-3 w-3 mr-1" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2 text-xs"
                        onClick={() => regenerateDraft(draft.draft_id)}
                      >
                        <RefreshCw className="h-3 w-3 mr-1" />
                        Regenerate
                      </Button>
                      {/* Stage to Close - only for email drafts */}
                      {draft.draft_type === "email" && (
                        <Button
                          size="sm"
                          className="h-7 px-2 text-xs bg-[var(--turkish-blue)] hover:bg-[var(--turkish-blue)]/90"
                          onClick={() => stageToClose(draft.draft_id)}
                        >
                          <Upload className="h-3 w-3 mr-1" />
                          Stage to Close
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className="h-7 px-2 text-xs bg-green-600 hover:bg-green-700"
                        onClick={() => approveAndSend(draft.draft_id)}
                      >
                        <Send className="h-3 w-3 mr-1" />
                        Approve & Send
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        className="h-7 px-2 text-xs"
                        onClick={() => discardDraft(draft.draft_id)}
                      >
                        <Trash2 className="h-3 w-3 mr-1" />
                        Discard
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
