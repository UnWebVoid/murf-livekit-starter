'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  FileSearch,
  MessageSquareText,
  PhoneCall,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  User,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

interface EscalationRecord {
  reference_id: string;
  user_id: string;
  status: 'open' | 'in_progress' | 'resolved';
  urgency: 'low' | 'medium' | 'high' | 'emergency';
  language: string;
  what_happened: string;
  what_checked: string;
  who_needs_help: string;
  follow_up_pref: string;
  created_at: string;
}

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState<EscalationRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'resolved'>('all');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchEscalations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/escalations');
      const data = await res.json();
      if (data.success) {
        setEscalations(data.escalations || []);
      } else {
        setError(data.error || 'Failed to load escalation requests.');
      }
    } catch (err: unknown) {
      console.error('Error fetching escalations:', err);
      setError('Network error loading escalations.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEscalations();
  }, [fetchEscalations]);

  const handleToggleStatus = async (record: EscalationRecord) => {
    const nextStatus = record.status === 'resolved' ? 'open' : 'resolved';
    setUpdatingId(record.reference_id);
    try {
      const res = await fetch('/api/escalations', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference_id: record.reference_id, status: nextStatus }),
      });
      const data = await res.json();
      if (data.success) {
        setEscalations((prev) =>
          prev.map((item) =>
            item.reference_id === record.reference_id ? { ...item, status: nextStatus } : item
          )
        );
      }
    } catch (err) {
      console.error('Error updating status:', err);
    } finally {
      setUpdatingId(null);
    }
  };

  const filtered = escalations.filter((item) => {
    if (statusFilter === 'open') return item.status !== 'resolved';
    if (statusFilter === 'resolved') return item.status === 'resolved';
    return true;
  });

  const openCount = escalations.filter((i) => i.status !== 'resolved').length;
  const resolvedCount = escalations.filter((i) => i.status === 'resolved').length;

  const getUrgencyBadge = (urgency: string) => {
    const u = urgency.toLowerCase();
    switch (u) {
      case 'emergency':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/15 px-2.5 py-0.5 text-xs font-bold text-red-600 dark:text-red-400">
            <AlertTriangle className="h-3 w-3 animate-pulse" /> Emergency
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/15 px-2.5 py-0.5 text-xs font-bold text-amber-600 dark:text-amber-400">
            <ShieldAlert className="h-3 w-3" /> High Urgency
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-yellow-500/30 bg-yellow-500/15 px-2.5 py-0.5 text-xs font-medium text-yellow-600 dark:text-yellow-400">
            Medium
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-blue-500/30 bg-blue-500/15 px-2.5 py-0.5 text-xs font-medium text-blue-600 dark:text-blue-400">
            Low
          </span>
        );
    }
  };

  return (
    <div className="bg-background text-foreground mx-auto min-h-screen max-w-6xl space-y-8 px-4 py-8 md:px-8">
      {/* Header Bar */}
      <div className="border-border/60 flex flex-col items-start justify-between gap-4 border-b pb-6 md:flex-row md:items-center">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link href="/">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground gap-1.5 rounded-full"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Assistant
              </Button>
            </Link>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              <Sparkles className="h-3 w-3" /> Day 7 Human Help
            </span>
          </div>
          <h1 className="bg-gradient-to-r from-emerald-600 via-teal-600 to-amber-600 bg-clip-text text-3xl font-extrabold tracking-tight text-transparent">
            Escalation Dashboard
          </h1>
          <p className="text-muted-foreground text-sm">
            Local database-backed management for financial fraud reports and human support requests.
          </p>
        </div>

        <Button
          onClick={fetchEscalations}
          disabled={isLoading}
          variant="outline"
          className="gap-2 rounded-full border-emerald-500/20 hover:bg-emerald-500/10"
        >
          <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="bg-card/60 space-y-1 rounded-2xl border border-emerald-500/20 p-5 shadow-sm backdrop-blur-xl">
          <p className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">
            Total Requests
          </p>
          <p className="text-foreground text-3xl font-bold">{escalations.length}</p>
        </div>
        <div className="space-y-1 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5 shadow-sm backdrop-blur-xl">
          <p className="text-xs font-semibold tracking-wider text-amber-600 uppercase dark:text-amber-400">
            Open Requests
          </p>
          <p className="text-3xl font-bold text-amber-600 dark:text-amber-400">{openCount}</p>
        </div>
        <div className="space-y-1 rounded-2xl border border-teal-500/20 bg-teal-500/5 p-5 shadow-sm backdrop-blur-xl">
          <p className="text-xs font-semibold tracking-wider text-teal-600 uppercase dark:text-teal-400">
            Resolved Requests
          </p>
          <p className="text-3xl font-bold text-teal-600 dark:text-teal-400">{resolvedCount}</p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="border-border/40 flex items-center justify-between border-b pb-2">
        <div className="flex items-center gap-2">
          <Button
            variant={statusFilter === 'all' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('all')}
            className="rounded-full text-xs font-semibold"
          >
            All ({escalations.length})
          </Button>
          <Button
            variant={statusFilter === 'open' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('open')}
            className="rounded-full text-xs font-semibold"
          >
            Open ({openCount})
          </Button>
          <Button
            variant={statusFilter === 'resolved' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setStatusFilter('resolved')}
            className="rounded-full text-xs font-semibold"
          >
            Resolved ({resolvedCount})
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="text-muted-foreground space-y-2 py-16 text-center">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-emerald-500" />
          <p className="text-sm">Loading escalation records from database...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="border-border/80 space-y-3 rounded-3xl border border-dashed py-16 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500/60" />
          <h3 className="text-lg font-bold">No Escalation Requests Found</h3>
          <p className="text-muted-foreground mx-auto max-w-sm text-xs">
            {statusFilter === 'all'
              ? 'No human help requests have been submitted yet.'
              : `No ${statusFilter} escalation requests found.`}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filtered.map((item) => (
            <div
              key={item.reference_id}
              className={cn(
                'space-y-4 rounded-2xl border p-6 shadow-md backdrop-blur-xl transition-all',
                item.status === 'resolved'
                  ? 'border-border/40 bg-card/30 opacity-75'
                  : 'bg-card/80 border-emerald-500/20 hover:border-emerald-500/40'
              )}
            >
              {/* Card Top Row */}
              <div className="border-border/40 flex flex-col items-start justify-between gap-3 border-b pb-3 sm:flex-row sm:items-center">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="bg-muted text-foreground border-border/60 rounded-lg border px-3 py-1 font-mono text-sm font-extrabold">
                    {item.reference_id}
                  </span>
                  {getUrgencyBadge(item.urgency)}
                  <span
                    className={cn(
                      'rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wider uppercase',
                      item.status === 'resolved'
                        ? 'border border-teal-500/20 bg-teal-500/10 text-teal-600'
                        : 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                    )}
                  >
                    {item.status}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant={item.status === 'resolved' ? 'outline' : 'default'}
                    onClick={() => handleToggleStatus(item)}
                    disabled={updatingId === item.reference_id}
                    className="gap-1.5 rounded-full text-xs"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {item.status === 'resolved' ? 'Reopen Request' : 'Mark as Resolved'}
                  </Button>
                </div>
              </div>

              {/* Grid Information Details */}
              <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
                {/* Left Column: What Happened */}
                <div className="bg-muted/40 border-border/40 space-y-1.5 rounded-xl border p-3.5">
                  <div className="text-muted-foreground flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase">
                    <MessageSquareText className="h-3.5 w-3.5 text-emerald-500" />
                    What Happened (Sanitized Summary)
                  </div>
                  <p className="text-foreground text-xs leading-relaxed font-medium md:text-sm">
                    {item.what_happened}
                  </p>
                </div>

                {/* Right Column: What Jan Sathi Checked */}
                <div className="bg-muted/40 border-border/40 space-y-1.5 rounded-xl border p-3.5">
                  <div className="text-muted-foreground flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase">
                    <FileSearch className="h-3.5 w-3.5 text-teal-500" />
                    What Jan Sathi Checked / Explained
                  </div>
                  <p className="text-foreground text-xs leading-relaxed font-medium md:text-sm">
                    {item.what_checked}
                  </p>
                </div>
              </div>

              {/* Metadata Footer Row */}
              <div className="text-muted-foreground border-border/30 flex flex-wrap items-center justify-between gap-3 border-t pt-2 text-xs">
                <div className="flex flex-wrap items-center gap-4">
                  <span className="inline-flex items-center gap-1">
                    <User className="h-3.5 w-3.5 text-emerald-500" />
                    Caller: <strong className="text-foreground">{item.who_needs_help}</strong>
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <PhoneCall className="h-3.5 w-3.5 text-teal-500" />
                    Follow-up: <strong className="text-foreground">{item.follow_up_pref}</strong>
                  </span>
                  <span className="inline-flex items-center gap-1 uppercase">
                    Lang: <strong className="text-foreground">{item.language}</strong>
                  </span>
                </div>

                <div className="text-muted-foreground inline-flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {new Date(item.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
