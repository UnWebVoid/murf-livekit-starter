'use client';

import { type ComponentProps } from 'react';
import { AnimatePresence } from 'motion/react';
import { type AgentState, type ReceivedMessage } from '@livekit/components-react';
import { AgentChatIndicator } from '@/components/agents-ui/agent-chat-indicator';
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation';
import { Message, MessageContent, MessageResponse } from '@/components/ai-elements/message';
import { cn } from '@/lib/shadcn/utils';

/**
 * Props for the AgentChatTranscript component.
 */
export interface AgentChatTranscriptProps extends ComponentProps<'div'> {
  /**
   * The current state of the agent. When 'thinking', displays a loading indicator.
   */
  agentState?: AgentState;
  /**
   * Array of messages to display in the transcript.
   * @defaultValue []
   */
  messages?: ReceivedMessage[];
  /**
   * Additional CSS class names to apply to the conversation container.
   */
  className?: string;
}

/**
 * A chat transcript component that displays a conversation between the user and agent.
 * Shows messages with timestamps and origin indicators, plus a thinking indicator
 * when the agent is processing.
 *
 * @extends ComponentProps<'div'>
 *
 * @example
 * ```tsx
 * <AgentChatTranscript
 *   agentState={agentState}
 *   messages={chatMessages}
 * />
 * ```
 */
/**
 * Groups consecutive user transcript segments belonging to the same spoken turn
 * into a single updating message bubble. Starts a new user bubble when an assistant
 * response intervenes or a new turn begins.
 */
function groupMessages(messages: ReceivedMessage[]): ReceivedMessage[] {
  if (!messages || messages.length === 0) return [];

  const grouped: ReceivedMessage[] = [];

  for (const msg of messages) {
    const isUser = msg.from?.isLocal === true || msg.type === 'userTranscript';

    if (!isUser) {
      // Assistant messages stay 100% separate
      grouped.push(msg);
    } else {
      const last = grouped.at(-1);
      const lastIsUser = last && (last.from?.isLocal === true || last.type === 'userTranscript');

      if (lastIsUser && last) {
        // Merge consecutive user transcript segments within the same spoken turn
        const prevText = last.message.trim();
        const currText = msg.message.trim();

        let newText = currText;
        if (currText.startsWith(prevText)) {
          newText = currText;
        } else if (prevText.endsWith(currText)) {
          newText = prevText;
        } else if (prevText && currText) {
          newText = `${prevText} ${currText}`;
        } else {
          newText = currText || prevText;
        }

        grouped[grouped.length - 1] = {
          ...last,
          message: newText,
          timestamp: msg.timestamp || last.timestamp,
        };
      } else {
        // Start a brand-new user message bubble for this turn
        grouped.push({ ...msg });
      }
    }
  }

  return grouped;
}

export function AgentChatTranscript({
  agentState,
  messages = [],
  className,
  ...props
}: AgentChatTranscriptProps) {
  const displayMessages = groupMessages(messages);

  return (
    <Conversation className={className} {...props}>
      <ConversationContent>
        {displayMessages.map((receivedMessage) => {
          const { id, timestamp, from, message } = receivedMessage;
          const locale = navigator?.language ?? 'en-US';
          const isUser = from?.isLocal;
          const messageOrigin = isUser ? 'user' : 'assistant';
          const speakerName = isUser ? 'You' : 'Jan Sathi (जन साथी)';
          const time = new Date(timestamp);
          const title = `${speakerName} • ${time.toLocaleTimeString(locale, { timeStyle: 'short' })}`;

          return (
            <Message key={id} title={title} from={messageOrigin}>
              <div
                className={cn(
                  'text-[11px] font-bold tracking-wide mb-0.5 px-1 opacity-80',
                  isUser
                    ? 'text-right text-emerald-600 dark:text-emerald-400'
                    : 'text-left text-cyan-600 dark:text-cyan-400'
                )}
              >
                {speakerName}
              </div>
              <MessageContent>
                <MessageResponse>{message}</MessageResponse>
              </MessageContent>
            </Message>
          );
        })}
        <AnimatePresence>
          {agentState === 'thinking' && <AgentChatIndicator size="sm" />}
        </AnimatePresence>
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>
  );
}
