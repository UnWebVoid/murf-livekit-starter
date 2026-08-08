'use client';

import React from 'react';
import { Mic, Volume2, Loader2, CircleAlert, PhoneOff, Brain } from 'lucide-react';
import { cn } from '@/lib/shadcn/utils';

export type DisplayAgentState =
  | 'ready'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'ended'
  | 'error';

interface AgentStatusBadgeProps {
  state: DisplayAgentState;
  className?: string;
  subtext?: string;
}

export function AgentStatusBadge({ state, className, subtext }: AgentStatusBadgeProps) {
  switch (state) {
    case 'ready':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 shadow-sm backdrop-blur-md">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
            </span>
            <span>Ready to talk</span>
          </div>
          {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
        </div>
      );

    case 'connecting':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400 shadow-sm backdrop-blur-md">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Connecting...</span>
          </div>
          <p className="text-xs text-muted-foreground animate-pulse">
            {subtext || 'Please wait while I connect you to the AI assistant.'}
          </p>
        </div>
      );

    case 'listening':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-5 py-2 text-sm font-bold text-emerald-700 dark:text-emerald-300 shadow-md backdrop-blur-md animate-pulse">
            <div className="relative flex items-center justify-center">
              <Mic className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              <span className="absolute -inset-1 rounded-full bg-emerald-500/20 animate-ping"></span>
            </div>
            <span className="tracking-wide">🎤 Listening to you</span>
          </div>
          <p className="text-xs text-muted-foreground font-medium">
            {subtext || 'Speak naturally in Hindi, English, or Hinglish...'}
          </p>
        </div>
      );

    case 'thinking':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 shadow-sm backdrop-blur-md">
            <Brain className="h-3.5 w-3.5 animate-bounce text-indigo-500" />
            <span>Jan Sathi is thinking...</span>
          </div>
          <p className="text-xs text-muted-foreground">{subtext || 'Processing your request...'}</p>
        </div>
      );

    case 'speaking':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2.5 rounded-full border border-cyan-500/40 bg-cyan-500/15 px-5 py-2 text-sm font-bold text-cyan-700 dark:text-cyan-300 shadow-md backdrop-blur-md">
            <Volume2 className="h-4 w-4 animate-bounce text-cyan-500" />
            <span className="tracking-wide">🔊 Agent is speaking</span>
            <div className="flex items-end gap-0.5 h-3.5 ml-1">
              <span className="w-0.5 bg-cyan-500 h-full animate-[pulse_0.6s_ease-in-out_infinite]"></span>
              <span className="w-0.5 bg-cyan-500 h-2/3 animate-[pulse_0.4s_ease-in-out_infinite_0.1s]"></span>
              <span className="w-0.5 bg-cyan-500 h-5/6 animate-[pulse_0.5s_ease-in-out_infinite_0.2s]"></span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground font-medium">
            {subtext || 'Jan Sathi is responding...'}
          </p>
        </div>
      );

    case 'ended':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/10 px-4 py-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400 shadow-sm backdrop-blur-md">
            <PhoneOff className="h-3.5 w-3.5 text-rose-500" />
            <span>Conversation ended</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {subtext || 'Thank you for talking with Jan Sathi!'}
          </p>
        </div>
      );

    case 'error':
      return (
        <div className={cn('flex flex-col items-center gap-1.5 text-center', className)}>
          <div className="inline-flex items-center gap-2 rounded-full border border-destructive/40 bg-destructive/10 px-4 py-1.5 text-xs font-semibold text-destructive shadow-sm">
            <CircleAlert className="h-3.5 w-3.5" />
            <span>Connection or Microphone Issue</span>
          </div>
          {subtext && <p className="text-xs text-destructive/80">{subtext}</p>}
        </div>
      );

    default:
      return null;
  }
}
