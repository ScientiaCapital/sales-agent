import { useState, useEffect, useCallback } from 'react';
import useSWR from 'swr';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Zap,
  Search,
  ChevronLeft,
  ChevronRight,
  Building2,
  Sparkles,
} from 'lucide-react';
import { AIInsightsPanel } from './AIInsightsPanel';

// Type definitions
interface Lead {
  id: string;
  name: string;
  domain: string | null;
  city: string | null;
  state: string | null;
  icp_tier: string; // PLATINUM, GOLD, SILVER, BRONZE
  icp_score: number;
  ai_enriched_at: string | null;
  ai_confidence: number | null;
  ai_personal_hooks: Array<{
    category: string;
    detail: string;
    opener: string;
  }> | null;
  ai_company_story: string | null;
  ai_pain_points: string[] | null;
  ai_buying_signals: string[] | null;
}

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

// Fetcher for SWR
const fetcher = (url: string) => fetch(url).then((res) => res.json());

// ICP Tier color mapping
const getTierColor = (tier: string): string => {
  switch (tier) {
    case 'PLATINUM':
      return 'bg-purple-100 text-purple-800 border-purple-300';
    case 'GOLD':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'SILVER':
      return 'bg-gray-100 text-gray-800 border-gray-300';
    case 'BRONZE':
      return 'bg-orange-100 text-orange-800 border-orange-300';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300';
  }
};

// Lead Card Component
const LeadCard = ({
  lead,
  isSelected,
  onClick,
}: {
  lead: Lead;
  isSelected: boolean;
  onClick: () => void;
}) => {
  const hasAIData = lead.ai_enriched_at !== null;
  const location = [lead.city, lead.state].filter(Boolean).join(', ');

  return (
    <div
      onClick={onClick}
      className={`
        p-4 rounded-lg border cursor-pointer transition-all
        ${isSelected
          ? 'bg-primary/10 border-primary shadow-md'
          : 'hover:bg-muted/50 hover:shadow-sm'
        }
      `}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm truncate flex items-center gap-2">
            <Building2 className="size-4 shrink-0" />
            {lead.name}
          </h3>
          {lead.domain && (
            <p className="text-xs text-muted-foreground truncate mt-0.5">
              {lead.domain}
            </p>
          )}
        </div>
        {hasAIData && (
          <div title="AI Enriched">
            <Sparkles className="size-4 text-purple-600 shrink-0" />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="outline" className={getTierColor(lead.icp_tier)}>
          {lead.icp_tier}
        </Badge>
        <span className="text-xs text-muted-foreground">
          Score: {lead.icp_score}
        </span>
      </div>

      {location && (
        <p className="text-xs text-muted-foreground mt-2">{location}</p>
      )}
    </div>
  );
};

// Loading Skeleton
const LoadingSkeleton = () => (
  <div className="space-y-3">
    {[1, 2, 3, 4, 5].map((i) => (
      <Skeleton key={i} className="h-24 w-full" />
    ))}
  </div>
);

// Main Component
export const CommandCenter = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [isEnriching, setIsEnriching] = useState(false);
  const leadsPerPage = 10;

  // Fetch leads from API
  const { data: leadsData, isLoading: leadsLoading } = useSWR<{ leads: Lead[] }>(
    '/api/dashboard/icp-queue',
    fetcher,
    { refreshInterval: 30000 }
  );

  // Fetch drafts for selected lead
  const { data: draftsData, isLoading: draftsLoading } = useSWR<{ drafts: Draft[] }>(
    selectedLead ? `/api/ai/drafts?company_id=${selectedLead.id}` : null,
    fetcher
  );

  // Filter leads by search query
  const filteredLeads = (leadsData?.leads || []).filter((lead) => {
    const query = searchQuery.toLowerCase();
    return (
      lead.name.toLowerCase().includes(query) ||
      (lead.domain && lead.domain.toLowerCase().includes(query))
    );
  });

  // Pagination
  const totalPages = Math.ceil(filteredLeads.length / leadsPerPage);
  const startIndex = (currentPage - 1) * leadsPerPage;
  const paginatedLeads = filteredLeads.slice(startIndex, startIndex + leadsPerPage);

  // Reset to page 1 when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // Handle lead enrichment (defined before useEffect that uses it)
  const handleEnrich = useCallback(async () => {
    if (!selectedLead || isEnriching) return;

    setIsEnriching(true);
    try {
      const response = await fetch('/api/ai/enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: selectedLead.id }),
      });

      if (!response.ok) {
        throw new Error('Enrichment failed');
      }

      // TODO: Show success toast
      // Refresh data by mutating SWR cache
    } catch (error) {
      console.error('Enrichment error:', error);
      // TODO: Show error toast
    } finally {
      setIsEnriching(false);
    }
  }, [selectedLead, isEnriching]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case 'j':
          // Navigate down
          e.preventDefault();
          setSelectedLead((current) => {
            if (!current) return paginatedLeads[0] || null;
            const currentIndex = paginatedLeads.findIndex((l) => l.id === current.id);
            if (currentIndex < paginatedLeads.length - 1) {
              return paginatedLeads[currentIndex + 1];
            }
            return current;
          });
          break;

        case 'k':
          // Navigate up
          e.preventDefault();
          setSelectedLead((current) => {
            if (!current) return paginatedLeads[0] || null;
            const currentIndex = paginatedLeads.findIndex((l) => l.id === current.id);
            if (currentIndex > 0) {
              return paginatedLeads[currentIndex - 1];
            }
            return current;
          });
          break;

        case 'e':
          // Enrich selected lead
          e.preventDefault();
          if (selectedLead) {
            handleEnrich();
          }
          break;

        case 'n':
          // Next page
          e.preventDefault();
          if (currentPage < totalPages) {
            setCurrentPage((p) => p + 1);
          }
          break;

        case 'p':
          // Previous page
          e.preventDefault();
          if (currentPage > 1) {
            setCurrentPage((p) => p - 1);
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [selectedLead, paginatedLeads, currentPage, totalPages, handleEnrich]);

  // Handle draft editing
  const handleEditDraft = useCallback(
    async (draftId: string, body: string, subject?: string) => {
      try {
        const response = await fetch(`/api/ai/drafts/${draftId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ body, subject }),
        });

        if (!response.ok) {
          throw new Error('Failed to update draft');
        }

        // TODO: Show success toast
      } catch (error) {
        console.error('Draft update error:', error);
        // TODO: Show error toast
      }
    },
    []
  );

  // Handle draft sending
  const handleSendDraft = useCallback(async (draftId: string) => {
    try {
      const response = await fetch(`/api/ai/drafts/${draftId}/send`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to send draft');
      }

      // TODO: Show success toast
    } catch (error) {
      console.error('Draft send error:', error);
      // TODO: Show error toast
    }
  }, []);

  // Handle draft regeneration
  const handleRegenerateDraft = useCallback(async (draftId: string) => {
    try {
      const response = await fetch(`/api/ai/drafts/${draftId}/regenerate`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to regenerate draft');
      }

      // TODO: Show success toast
    } catch (error) {
      console.error('Draft regenerate error:', error);
      // TODO: Show error toast
    }
  }, []);

  // Convert Lead to AIInsights format
  const getAIInsights = (lead: Lead | null): AIInsights | null => {
    if (!lead || !lead.ai_enriched_at) return null;

    return {
      personal_hooks: lead.ai_personal_hooks?.map((hook) => ({
        category: hook.category,
        detail: hook.detail,
        conversation_opener: hook.opener,
      })),
      company_story: lead.ai_company_story || undefined,
      pain_points: lead.ai_pain_points || undefined,
      buying_signals: lead.ai_buying_signals || undefined,
      confidence: lead.ai_confidence || undefined,
    };
  };

  return (
    <div className="h-screen flex gap-6 p-6">
      {/* Left Panel - Lead List (40%) */}
      <div className="w-2/5 flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="size-5 text-[var(--turkish-blue)]" />
              AI Command Center
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Search Bar */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name or domain..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Stats */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {filteredLeads.length} leads
              </span>
              <span className="text-muted-foreground">
                Page {currentPage} of {totalPages || 1}
              </span>
            </div>

            {/* Keyboard Shortcuts Help */}
            <div className="text-xs text-muted-foreground bg-muted/30 p-2 rounded">
              <strong>Shortcuts:</strong> J/K navigate | E enrich | N/P pages
            </div>
          </CardContent>
        </Card>

        {/* Lead List */}
        <Card className="flex-1 overflow-hidden flex flex-col">
          <CardContent className="flex-1 overflow-y-auto space-y-2 pt-6">
            {leadsLoading ? (
              <LoadingSkeleton />
            ) : paginatedLeads.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Building2 className="size-12 mx-auto mb-2 opacity-50" />
                <p>No leads found</p>
              </div>
            ) : (
              paginatedLeads.map((lead) => (
                <LeadCard
                  key={lead.id}
                  lead={lead}
                  isSelected={selectedLead?.id === lead.id}
                  onClick={() => setSelectedLead(lead)}
                />
              ))
            )}
          </CardContent>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="border-t p-4 flex items-center justify-between">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="size-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>
          )}
        </Card>
      </div>

      {/* Right Panel - AI Insights (60%) */}
      <div className="w-3/5 overflow-y-auto">
        <AIInsightsPanel
          companyId={selectedLead?.id || null}
          companyName={selectedLead?.name || ''}
          contactName="" // TODO: Get from selected contact
          insights={getAIInsights(selectedLead)}
          drafts={draftsData?.drafts || []}
          loading={draftsLoading}
          onEnrich={handleEnrich}
          onEditDraft={handleEditDraft}
          onSendDraft={handleSendDraft}
          onRegenerateDraft={handleRegenerateDraft}
        />
      </div>
    </div>
  );
};
