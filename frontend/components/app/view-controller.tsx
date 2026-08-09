'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { ConnectionState } from 'livekit-client';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { AgentSessionView_01 } from '@/components/agents-ui/blocks/agent-session-view-01';
import { WelcomeView } from '@/components/app/welcome-view';
import { MicErrorModal, type ErrorDetails } from '@/components/app/mic-error-modal';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(AgentSessionView_01);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear',
  },
};

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, connectionState, start } = useSessionContext();
  const { resolvedTheme } = useTheme();

  const [isConnecting, setIsConnecting] = useState(false);
  const [hasEnded, setHasEnded] = useState(false);
  const [wasConnected, setWasConnected] = useState(false);
  const [errorDetails, setErrorDetails] = useState<ErrorDetails | null>(null);

  // Track state transitions: connecting -> connected -> ended
  useEffect(() => {
    if (connectionState === ConnectionState.Connecting) {
      setIsConnecting(true);
    } else {
      setIsConnecting(false);
    }

    if (isConnected) {
      setWasConnected(true);
      setHasEnded(false);
      setErrorDetails(null);
    } else if (wasConnected && connectionState === ConnectionState.Disconnected) {
      setHasEnded(true);
    }
  }, [isConnected, connectionState, wasConnected]);

  const handleStartCall = useCallback(async () => {
    if (isConnecting || isConnected) {
      return;
    }
    setErrorDetails(null);
    setIsConnecting(true);

    // Pre-check microphone permission
    if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((track) => track.stop());
      } catch (micErr: any) {
        setIsConnecting(false);
        if (micErr.name === 'NotAllowedError' || micErr.name === 'PermissionDeniedError') {
          setErrorDetails({
            title: 'Microphone access is blocked',
            description:
              'Your browser is preventing this page from using your microphone. Allow microphone access in your browser settings and try again.',
            type: 'mic_blocked',
          });
          return;
        } else if (micErr.name === 'NotFoundError' || micErr.name === 'DevicesNotFoundError') {
          setErrorDetails({
            title: 'Microphone unavailable',
            description: 'No microphone input device was found. Please check your audio hardware and try again.',
            type: 'mic_unavailable',
          });
          return;
        }
      }
    }

    try {
      await start();
    } catch (err: any) {
      console.error('Failed to start LiveKit session:', err);
      setIsConnecting(false);
      setErrorDetails({
        title: 'Connection Failed',
        description:
          err?.message ||
          'Unable to connect to the AI voice agent. Please make sure the LiveKit server and python agent backend are running.',
        type: 'connection_failed',
      });
    }
  }, [start]);

  const handleStartAgain = useCallback(() => {
    setHasEnded(false);
    setWasConnected(false);
    setErrorDetails(null);
    handleStartCall();
  }, [handleStartCall]);

  return (
    <>
      <AnimatePresence mode="wait">
        {/* Welcome & Call Ended View */}
        {!isConnected && (
          <MotionWelcomeView
            key="welcome"
            {...VIEW_MOTION_PROPS}
            startButtonText={appConfig.startButtonText}
            isConnecting={isConnecting}
            hasEnded={hasEnded}
            onStartCall={handleStartCall}
            onStartAgain={handleStartAgain}
          />
        )}
        {/* Active Session View */}
        {isConnected && (
          <MotionSessionView
            key="session-view"
            {...VIEW_MOTION_PROPS}
            supportsChatInput={appConfig.supportsChatInput}
            supportsVideoInput={appConfig.supportsVideoInput}
            supportsScreenShare={appConfig.supportsScreenShare}
            isPreConnectBufferEnabled={appConfig.isPreConnectBufferEnabled}
            audioVisualizerType={appConfig.audioVisualizerType}
            audioVisualizerColor={
              resolvedTheme === 'dark'
                ? appConfig.audioVisualizerColorDark
                : appConfig.audioVisualizerColor
            }
            audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
            audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
            audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
            audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
            audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
            audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
            audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
            className="fixed inset-0"
          />
        )}
      </AnimatePresence>

      {/* Microphone / Connection Error Modal */}
      {errorDetails && (
        <MicErrorModal error={errorDetails} onRetry={handleStartCall} />
      )}
    </>
  );
}
