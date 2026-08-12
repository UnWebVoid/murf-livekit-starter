'use client';

import React from 'react';
import Link from 'next/link';
import { Mic, Sparkles, ShieldCheck, Landmark, Calculator, Lock, RotateCcw, LifeBuoy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AgentStatusBadge } from '@/components/app/agent-status-badge';
import { cn } from '@/lib/shadcn/utils';

interface WelcomeViewProps {
  startButtonText: string;
  isConnecting?: boolean;
  hasEnded?: boolean;
  onStartCall: () => void;
  onStartAgain?: () => void;
}

export const WelcomeView = ({
  startButtonText,
  isConnecting = false,
  hasEnded = false,
  onStartCall,
  onStartAgain,
  ref,
  className,
  ...props
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  const handleAction = () => {
    if (hasEnded && onStartAgain) {
      onStartAgain();
    } else {
      onStartCall();
    }
  };

  return (
    <div
      ref={ref}
      className={cn('flex flex-col items-center justify-center min-h-[85vh] px-4 py-8 max-w-2xl mx-auto w-full text-center', className)}
      {...props}
    >
      {/* Brand Header & Badge */}
      <div className="space-y-4 mb-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3.5 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
          <Sparkles className="h-3.5 w-3.5 text-emerald-500" />
          <span>Indian Financial Awareness AI</span>
        </div>

        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-foreground bg-gradient-to-r from-emerald-600 via-teal-600 to-amber-600 bg-clip-text text-transparent">
          Jan Sathi <span className="font-hindi font-normal text-3xl md:text-4xl">(जन साथी)</span>
        </h1>

        <p className="text-muted-foreground text-sm md:text-base max-w-lg mx-auto leading-relaxed">
          Your trusted voice AI guide for Indian government schemes, banking services, UPI payments, loan EMI calculation, and financial cyber safety.
        </p>

        <div className="pt-1">
          <Link href="/escalations">
            <Button
              variant="outline"
              size="sm"
              className="rounded-full text-xs font-semibold gap-1.5 border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-700 dark:text-amber-300 shadow-sm"
            >
              <LifeBuoy className="h-3.5 w-3.5 text-amber-500" />
              <span>Human Help Requests Dashboard</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Status & Interactive Action Container */}
      <div className="w-full max-w-md my-4 p-6 md:p-8 rounded-3xl border border-emerald-500/20 bg-card/60 backdrop-blur-xl shadow-xl space-y-6">
        {/* Status Indicator */}
        {hasEnded ? (
          <AgentStatusBadge state="ended" subtext="Click below to start a brand new conversation." />
        ) : isConnecting ? (
          <AgentStatusBadge state="connecting" subtext="Please wait while I connect you to the AI assistant." />
        ) : (
          <AgentStatusBadge state="ready" subtext="Mic access ready. Click start to begin speaking." />
        )}

        {/* Prominent Action Button */}
        <div className="pt-2">
          {hasEnded ? (
            <Button
              size="lg"
              onClick={handleAction}
              className="w-full rounded-full font-bold tracking-wide text-sm py-6 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg hover:shadow-emerald-500/25 transition-all flex items-center justify-center gap-2"
            >
              <RotateCcw className="h-5 w-5" />
              <span>Start Again</span>
            </Button>
          ) : (
            <Button
              size="lg"
              disabled={isConnecting}
              onClick={handleAction}
              className={cn(
                'w-full rounded-full font-bold tracking-wide text-sm py-6 text-white shadow-lg transition-all flex items-center justify-center gap-2',
                isConnecting
                  ? 'bg-muted text-muted-foreground opacity-75 cursor-not-allowed'
                  : 'bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20 hover:shadow-emerald-500/35 hover:scale-[1.02]'
              )}
            >
              <div className="relative flex items-center justify-center">
                <Mic className="h-5 w-5" />
                {!isConnecting && (
                  <span className="absolute -inset-1 rounded-full bg-white/20 animate-ping"></span>
                )}
              </div>
              <span>{isConnecting ? 'Connecting...' : startButtonText}</span>
            </Button>
          )}
        </div>
      </div>

      {/* Suggested Topic Pills */}
      <div className="mt-6 space-y-2.5 w-full max-w-lg">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          What you can ask Jan Sathi:
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-muted/50 px-3 py-1.5 font-medium text-foreground">
            <Landmark className="h-3.5 w-3.5 text-emerald-500" />
            PM Jan Dhan & Schemes
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-muted/50 px-3 py-1.5 font-medium text-foreground">
            <Calculator className="h-3.5 w-3.5 text-amber-500" />
            Calculate Loan EMI
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-muted/50 px-3 py-1.5 font-medium text-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-indigo-500" />
            Report UPI Fraud
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-muted/50 px-3 py-1.5 font-medium text-foreground">
            <Lock className="h-3.5 w-3.5 text-cyan-500" />
            Cyber Crime Helpline (1930)
          </span>
        </div>
      </div>

      {/* Footer Info */}
      <footer className="mt-8 text-xs text-muted-foreground">
        Powered by Murf AI & LiveKit | Hindi & English Voice Assistant
      </footer>
    </div>
  );
};
