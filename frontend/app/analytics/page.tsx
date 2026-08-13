'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  FileCheck,
  LifeBuoy,
  PhoneCall,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

interface CallRecord {
  call_id: string;
  room_name: string;
  user_id: string;
  user_id_safe?: string;
  channel: string;
  start_time: string;
  end_time: string | null;
  duration_seconds: number;
  outcome: 'success' | 'failed';
  success_type: 'eligibility_check' | 'scheme_or_doc_info' | 'escalation_created' | null;
}

interface AnalyticsSummary {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  success_rate: number;
  by_success_type: Record<string, number>;
  by_channel: Record<string, number>;
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary>({
    total_calls: 0,
    successful_calls: 0,
    failed_calls: 0,
    success_rate: 0.0,
    by_success_type: {},
    by_channel: {},
  });
  const [recentCalls, setRecentCalls] = useState<CallRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/analytics');
      const data = await res.json();
      if (data.success) {
        setSummary(data.summary || {});
        setRecentCalls(data.recent_calls || []);
      } else {
        setError(data.error || 'Failed to load call analytics.');
      }
    } catch (err: unknown) {
      console.error('Error fetching analytics:', err);
      setError('Network error loading call analytics.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const formatDuration = (seconds: number) => {
    if (!seconds || seconds <= 0) return '< 1s';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins === 0) return `${secs}s`;
    return `${mins}m ${secs}s`;
  };

  const formatDate = (isoString: string) => {
    if (!isoString) return '—';
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-IN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  const getSuccessTypeBadge = (type: string | null) => {
    switch (type) {
      case 'eligibility_check':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <FileCheck className="h-3 w-3" />
            Eligibility Check
          </span>
        );
      case 'scheme_or_doc_info':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-0.5 text-xs font-semibold text-cyan-600 dark:text-cyan-400">
            <Sparkles className="h-3 w-3" />
            Scheme / Doc Info
          </span>
        );
      case 'escalation_created':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
            <LifeBuoy className="h-3 w-3" />
            Escalation Created
          </span>
        );
      default:
        return (
          <span className="bg-muted text-muted-foreground inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium">
            Incomplete
          </span>
        );
    }
  };

  return (
    <div className="bg-background text-foreground mx-auto min-h-screen max-w-6xl space-y-8 px-4 py-8">
      {/* Top Header */}
      <div className="flex flex-col items-start justify-between gap-4 border-b border-emerald-500/20 pb-4 md:flex-row md:items-center">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <Link href="/">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground gap-1.5 text-xs"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Voice Assistant
              </Button>
            </Link>
            <span className="text-muted-foreground text-xs">/</span>
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              Day 8 Analytics
            </span>
          </div>
          <h1 className="bg-gradient-to-r from-emerald-600 via-teal-600 to-amber-600 bg-clip-text text-3xl font-extrabold tracking-tight text-transparent">
            Call Analytics Dashboard
          </h1>
          <p className="text-muted-foreground text-sm">
            Real-time call session metrics, success rates, and safe metadata logging for Jan Sathi.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={fetchAnalytics}
            disabled={isLoading}
            variant="outline"
            size="sm"
            className="gap-2 rounded-full border-emerald-500/30 text-xs font-semibold hover:bg-emerald-500/10"
          >
            <RefreshCw
              className={cn('h-3.5 w-3.5 text-emerald-500', isLoading && 'animate-spin')}
            />
            Refresh Data
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-600 dark:text-rose-400">
          {error}
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Calls */}
        <div className="bg-card/60 space-y-2 rounded-2xl border border-emerald-500/20 p-5 shadow-sm backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">
              Total Calls
            </span>
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-600 dark:text-emerald-400">
              <PhoneCall className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-black">{summary.total_calls}</div>
          <div className="text-muted-foreground flex items-center gap-1.5 text-xs">
            <span>Browser: {summary.by_channel['Browser'] || 0}</span>
            <span>•</span>
            <span>SIP Outbound: {summary.by_channel['SIP Outbound'] || 0}</span>
          </div>
        </div>

        {/* Successful Calls */}
        <div className="bg-card/60 space-y-2 rounded-2xl border border-teal-500/20 p-5 shadow-sm backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">
              Successful Calls
            </span>
            <div className="rounded-xl bg-teal-500/10 p-2 text-teal-600 dark:text-teal-400">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-black text-teal-600 dark:text-teal-400">
            {summary.successful_calls}
          </div>
          <div className="text-muted-foreground text-xs">Reached an explicit success condition</div>
        </div>

        {/* Failed Calls */}
        <div className="bg-card/60 space-y-2 rounded-2xl border border-rose-500/20 p-5 shadow-sm backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">
              Failed Calls
            </span>
            <div className="rounded-xl bg-rose-500/10 p-2 text-rose-600 dark:text-rose-400">
              <XCircle className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-black text-rose-600 dark:text-rose-400">
            {summary.failed_calls}
          </div>
          <div className="text-muted-foreground text-xs">Disconnected prior to completion</div>
        </div>

        {/* Success Rate */}
        <div className="bg-card/60 space-y-2 rounded-2xl border border-indigo-500/20 p-5 shadow-sm backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">
              Success Rate
            </span>
            <div className="rounded-xl bg-indigo-500/10 p-2 text-indigo-600 dark:text-indigo-400">
              <TrendingUp className="h-5 w-5" />
            </div>
          </div>
          <div className="text-3xl font-black text-indigo-600 dark:text-indigo-400">
            {summary.success_rate}%
          </div>
          {/* Visual progress bar */}
          <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
            <div
              className="h-1.5 rounded-full bg-indigo-500 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, summary.success_rate))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Success Trigger Breakdown Banner */}
      <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-5 text-xs md:flex-row md:items-center">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 flex-shrink-0 text-emerald-500" />
          <span className="font-medium">
            <strong>Privacy & Integrity Enforced:</strong> All analytics use real session data. No
            conversation transcripts, PINs, OTPs, or passwords are stored.
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 font-semibold">
          <span>
            Eligibility Checks: <strong>{summary.by_success_type['eligibility_check'] || 0}</strong>
          </span>
          <span>•</span>
          <span>
            Scheme Info: <strong>{summary.by_success_type['scheme_or_doc_info'] || 0}</strong>
          </span>
          <span>•</span>
          <span>
            Escalations: <strong>{summary.by_success_type['escalation_created'] || 0}</strong>
          </span>
        </div>
      </div>

      {/* Recent Call History Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-xl font-bold tracking-tight">
            <Clock className="h-5 w-5 text-emerald-500" />
            Recent Call History ({recentCalls.length})
          </h2>
        </div>

        <div className="bg-card/60 overflow-x-auto rounded-2xl border border-emerald-500/20 shadow-sm backdrop-blur-xl">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-border bg-muted/40 text-muted-foreground border-b text-xs font-semibold uppercase">
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3">Outcome</th>
                <th className="px-4 py-3">Success Condition Triggered</th>
                <th className="px-4 py-3 text-right">Unique Session ID</th>
              </tr>
            </thead>
            <tbody className="divide-border divide-y text-sm">
              {recentCalls.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-muted-foreground py-8 text-center text-sm">
                    No calls recorded yet. Start a conversation with Jan Sathi to generate real
                    analytics data.
                  </td>
                </tr>
              ) : (
                recentCalls.map((call) => (
                  <tr key={call.call_id} className="hover:bg-muted/30 transition-colors">
                    <td className="text-muted-foreground px-4 py-3 font-mono text-xs whitespace-nowrap">
                      {formatDate(call.start_time)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'rounded-full border px-2 py-0.5 text-xs font-semibold',
                          call.channel === 'SIP Outbound'
                            ? 'border-amber-500/20 bg-amber-500/10 text-amber-600'
                            : 'border-blue-500/20 bg-blue-500/10 text-blue-600'
                        )}
                      >
                        {call.channel}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">
                      {formatDuration(call.duration_seconds)}
                    </td>
                    <td className="px-4 py-3">
                      {call.outcome === 'success' ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="h-3 w-3" />
                          Successful
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-0.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
                          <XCircle className="h-3 w-3" />
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">{getSuccessTypeBadge(call.success_type)}</td>
                    <td className="text-muted-foreground px-4 py-3 text-right font-mono text-xs whitespace-nowrap">
                      {call.call_id.substring(0, 16)}...
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
