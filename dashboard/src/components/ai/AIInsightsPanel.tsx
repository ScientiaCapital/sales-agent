import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  User,
  Building2,
  AlertTriangle,
  TrendingUp,
  Mail,
  MessageSquare,
  Phone,
  RefreshCw,
  Copy,
  Check,
  Edit2,
  X,
  Sparkles,
} from 'lucide-react';

// Type definitions
interface PersonalHook {
  category: string;
  detail: string;
  conversation_opener: string;
}

interface AIInsights {
  personal_hooks?: PersonalHook[];
  company_story?: string;
  pain_points?: string[];
  buying_signals?: string[];
  confidence?: number;
}

interface Draft {
  id: string;
  draft_type: 'email' | 'sms' | 'voice';
  subject?: string;
  body: string;
  confidence?: number;
}

interface AIInsightsPanelProps {
  companyId: string | null;
  companyName: string;
  contactName: string;
  insights: AIInsights | null;
  drafts: Draft[];
  loading: boolean;
  onEnrich: () => void;
  onEditDraft: (draftId: string, body: string, subject?: string) => void;
  onSendDraft: (draftId: string) => void;
  onRegenerateDraft: (draftId: string) => void;
}

// Draft Icon Component
const DraftIcon = ({ type }: { type: 'email' | 'sms' | 'voice' }) => {
  switch (type) {
    case 'email':
      return <Mail className="size-4" />;
    case 'sms':
      return <MessageSquare className="size-4" />;
    case 'voice':
      return <Phone className="size-4" />;
  }
};

// Loading Skeleton Component
const LoadingSkeleton = () => (
  <div className="space-y-6">
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </CardContent>
    </Card>
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-32" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-32 w-full" />
      </CardContent>
    </Card>
  </div>
);

// Empty State Component
const EmptyState = () => (
  <Card className="h-full flex items-center justify-center min-h-[400px]">
    <CardContent className="text-center space-y-4">
      <div className="flex justify-center">
        <Sparkles className="size-12 text-muted-foreground" />
      </div>
      <div className="space-y-2">
        <h3 className="text-lg font-semibold">No Lead Selected</h3>
        <p className="text-sm text-muted-foreground max-w-sm mx-auto">
          Select a lead from the table to view AI-powered insights, company story, and personalized outreach drafts.
        </p>
      </div>
    </CardContent>
  </Card>
);

// Draft Editor Component
const DraftEditor = ({
  draft,
  onEdit,
  onSend,
  onRegenerate,
}: {
  draft: Draft;
  onEdit: (draftId: string, body: string, subject?: string) => void;
  onSend: (draftId: string) => void;
  onRegenerate: (draftId: string) => void;
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedBody, setEditedBody] = useState(draft.body);
  const [editedSubject, setEditedSubject] = useState(draft.subject || '');
  const [copied, setCopied] = useState(false);

  const handleSave = () => {
    onEdit(draft.id, editedBody, draft.draft_type === 'email' ? editedSubject : undefined);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedBody(draft.body);
    setEditedSubject(draft.subject || '');
    setIsEditing(false);
  };

  const handleCopy = async () => {
    const textToCopy = draft.draft_type === 'email' && draft.subject
      ? `${draft.subject}\n\n${draft.body}`
      : draft.body;

    await navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const charCount = draft.draft_type === 'sms' ? editedBody.length : null;
  const isOverLimit = charCount !== null && charCount > 160;

  return (
    <div className="space-y-3">
      {/* Draft Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DraftIcon type={draft.draft_type} />
          <span className="font-medium capitalize">{draft.draft_type}</span>
          {draft.confidence && (
            <Badge variant="outline" className="text-xs">
              {Math.round(draft.confidence * 100)}% confidence
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          {!isEditing ? (
            <>
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={() => setIsEditing(true)}
                title="Edit draft"
              >
                <Edit2 className="size-4" />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={handleCopy}
                title="Copy to clipboard"
              >
                {copied ? <Check className="size-4 text-green-600" /> : <Copy className="size-4" />}
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={() => onRegenerate(draft.id)}
                title="Regenerate draft"
              >
                <RefreshCw className="size-4" />
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" onClick={handleSave}>
                Save
              </Button>
              <Button size="icon-sm" variant="ghost" onClick={handleCancel}>
                <X className="size-4" />
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Subject Line (Email Only) */}
      {draft.draft_type === 'email' && (
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Subject</label>
          {isEditing ? (
            <input
              type="text"
              value={editedSubject}
              onChange={(e) => setEditedSubject(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Email subject..."
            />
          ) : (
            <p className="text-sm font-medium">{draft.subject}</p>
          )}
        </div>
      )}

      {/* Body */}
      <div className="space-y-1">
        {draft.draft_type !== 'email' && (
          <label className="text-xs font-medium text-muted-foreground">Message</label>
        )}
        {isEditing ? (
          <div className="space-y-1">
            <textarea
              value={editedBody}
              onChange={(e) => setEditedBody(e.target.value)}
              rows={draft.draft_type === 'sms' ? 4 : 8}
              className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              placeholder="Message body..."
            />
            {charCount !== null && (
              <p className={`text-xs text-right ${isOverLimit ? 'text-destructive' : 'text-muted-foreground'}`}>
                {charCount}/160 characters {isOverLimit && '(over limit)'}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm whitespace-pre-wrap bg-muted/50 p-3 rounded-md">
              {draft.body}
            </p>
            {charCount !== null && (
              <p className={`text-xs text-right ${isOverLimit ? 'text-destructive' : 'text-muted-foreground'}`}>
                {charCount}/160 characters
              </p>
            )}
          </div>
        )}
      </div>

      {/* Send Button */}
      {!isEditing && (
        <Button
          className="w-full"
          onClick={() => onSend(draft.id)}
          disabled={draft.draft_type === 'sms' && isOverLimit}
        >
          Send {draft.draft_type === 'email' ? 'Email' : draft.draft_type === 'sms' ? 'SMS' : 'Voice Script'}
        </Button>
      )}
    </div>
  );
};

// Main Component
export const AIInsightsPanel = ({
  companyId,
  companyName,
  contactName,
  insights,
  drafts,
  loading,
  onEnrich,
  onEditDraft,
  onSendDraft,
  onRegenerateDraft,
}: AIInsightsPanelProps) => {
  // Empty state
  if (!companyId) {
    return <EmptyState />;
  }

  // Loading state
  if (loading) {
    return <LoadingSkeleton />;
  }

  // No insights yet
  const hasInsights = insights && (
    insights.personal_hooks?.length ||
    insights.company_story ||
    insights.pain_points?.length ||
    insights.buying_signals?.length
  );

  return (
    <div className="space-y-6">
      {/* Enrich Button */}
      {!hasInsights && (
        <Card>
          <CardContent className="py-8 text-center space-y-4">
            <Sparkles className="size-12 text-muted-foreground mx-auto" />
            <div className="space-y-2">
              <h3 className="font-semibold">No Insights Yet</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Enrich this lead to generate AI-powered insights, company story, and personalized outreach drafts.
              </p>
            </div>
            <Button onClick={onEnrich}>
              <Sparkles className="size-4" />
              Enrich with AI
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Personal Hooks */}
      {insights?.personal_hooks && insights.personal_hooks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="size-5" />
              Personal Hooks - {contactName}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {insights.personal_hooks.map((hook, idx) => (
              <div key={idx} className="space-y-2 p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{hook.category}</Badge>
                </div>
                <p className="text-sm">{hook.detail}</p>
                <div className="pt-2 border-t border-border">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Conversation Opener:</p>
                  <p className="text-sm italic">{hook.conversation_opener}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Company Story */}
      {insights?.company_story && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="size-5" />
              Company Story - {companyName}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{insights.company_story}</p>
            {insights.confidence && (
              <div className="mt-4 pt-4 border-t border-border">
                <Badge variant="outline">
                  {Math.round(insights.confidence * 100)}% confidence
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Pain Points and Buying Signals */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Pain Points */}
        {insights?.pain_points && insights.pain_points.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="size-5" />
                Pain Points
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {insights.pain_points.map((point, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <span className="text-destructive mt-1">•</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Buying Signals */}
        {insights?.buying_signals && insights.buying_signals.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="size-5" />
                Buying Signals
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {insights.buying_signals.map((signal, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <span className="text-green-600 mt-1">•</span>
                    <span>{signal}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Outreach Drafts */}
      {drafts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Personalized Outreach Drafts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {drafts.map((draft) => (
              <DraftEditor
                key={draft.id}
                draft={draft}
                onEdit={onEditDraft}
                onSend={onSendDraft}
                onRegenerate={onRegenerateDraft}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Enrich Again Button */}
      {hasInsights && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={onEnrich}>
            <RefreshCw className="size-4" />
            Re-enrich with Latest Data
          </Button>
        </div>
      )}
    </div>
  );
};
