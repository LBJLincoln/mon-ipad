import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Conversation, ChatMessage } from '@/types/chat'

interface ChatState {
  conversations: Record<string, Conversation[]>
  activeConversationId: string | null

  getOrCreateConversation: (sectorId: string) => Conversation
  addMessage: (sectorId: string, conversationId: string, message: ChatMessage) => void
  getConversation: (sectorId: string, conversationId: string) => Conversation | undefined
  getConversations: (sectorId: string) => Conversation[]
  setActiveConversation: (id: string | null) => void
  newConversation: (sectorId: string) => Conversation
}

function createConversation(sectorId: string): Conversation {
  return {
    id: crypto.randomUUID(),
    sectorId,
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: {},
      activeConversationId: null,

      getOrCreateConversation(sectorId: string) {
        const existing = get().conversations[sectorId]
        if (existing && existing.length > 0) {
          const last = existing[existing.length - 1]
          set({ activeConversationId: last.id })
          return last
        }
        const conv = createConversation(sectorId)
        set((state) => ({
          conversations: {
            ...state.conversations,
            [sectorId]: [...(state.conversations[sectorId] ?? []), conv],
          },
          activeConversationId: conv.id,
        }))
        return conv
      },

      addMessage(sectorId, conversationId, message) {
        set((state) => {
          const sectorConvs = state.conversations[sectorId] ?? []
          return {
            conversations: {
              ...state.conversations,
              [sectorId]: sectorConvs.map((c) =>
                c.id === conversationId
                  ? {
                      ...c,
                      messages: [...c.messages, message],
                      updatedAt: Date.now(),
                    }
                  : c
              ),
            },
          }
        })
      },

      getConversation(sectorId, conversationId) {
        return get().conversations[sectorId]?.find(
          (c) => c.id === conversationId
        )
      },

      getConversations(sectorId) {
        return get().conversations[sectorId] ?? []
      },

      setActiveConversation(id) {
        set({ activeConversationId: id })
      },

      newConversation(sectorId) {
        const conv = createConversation(sectorId)
        set((state) => ({
          conversations: {
            ...state.conversations,
            [sectorId]: [...(state.conversations[sectorId] ?? []), conv],
          },
          activeConversationId: conv.id,
        }))
        return conv
      },
    }),
    {
      name: 'multi-rag-chat',
      partialize: (state) => ({ conversations: state.conversations }),
    }
  )
)
