'use client';

import React from 'react';
import { MicOff, RefreshCw, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface ErrorDetails {
  title: string;
  description: string;
  type?: 'mic_blocked' | 'mic_unavailable' | 'connection_failed';
}

interface MicErrorModalProps {
  error: ErrorDetails;
  onRetry: () => void;
}

export function MicErrorModal({ error, onRetry }: MicErrorModalProps) {
  const isMicBlocked = error.type === 'mic_blocked';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md rounded-2xl border border-destructive/30 bg-card p-6 shadow-2xl space-y-5 text-center">
        {/* Header Icon */}
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 text-destructive ring-8 ring-destructive/5">
          {isMicBlocked ? <MicOff className="h-8 w-8" /> : <AlertTriangle className="h-8 w-8" />}
        </div>

        {/* Title & Description */}
        <div className="space-y-2">
          <h2 className="text-xl font-bold tracking-tight text-foreground">{error.title}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{error.description}</p>
        </div>

        {/* Browser Permission Guidance (if blocked) */}
        {isMicBlocked && (
          <div className="rounded-xl border border-border/60 bg-muted/40 p-3.5 text-left text-xs space-y-2">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Info className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>How to enable microphone in your browser:</span>
            </div>
            <ul className="space-y-1 text-muted-foreground pl-5 list-disc">
              <li>
                Click the <strong className="text-foreground">Lock / Tune icon</strong> next to the
                URL bar.
              </li>
              <li>
                Find <strong className="text-foreground">Microphone</strong> permissions and set it
                to <strong className="text-emerald-600 dark:text-emerald-400">Allow</strong>.
              </li>
              <li>
                Click <strong className="text-foreground">Try Again</strong> below to reconnect.
              </li>
            </ul>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-2">
          <Button
            size="lg"
            onClick={onRetry}
            className="w-full rounded-full font-semibold gap-2 shadow-lg hover:shadow-xl transition-all"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Try Again</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
