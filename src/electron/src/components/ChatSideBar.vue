<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';

interface ChatEntry {
  id: string;
  title: string;
  last_activity: string | null;
}

const chats = ref<ChatEntry[]>([]);
const openMenuId = ref<string | null>(null);
const router = useRouter();

const renameChatId = ref<string | null>(null);
const renameTitle = ref('');

function toggleMenu(chatId: string) {
  openMenuId.value = openMenuId.value === chatId ? null : chatId;
}

function closeMenu() {
  openMenuId.value = null;
}

function sortChatsByLastActivity(chatsToSort: ChatEntry[]): ChatEntry[] {
  return chatsToSort.sort((a: ChatEntry, b: ChatEntry) => {
    if (!a.last_activity) return 1;
    if (!b.last_activity) return -1;
    return new Date(b.last_activity).getTime() - new Date(a.last_activity).getTime();
  });
}

async function fetchChats() {
  const res = await fetch('http://localhost:8000/chats');
  const data = await res.json();
  chats.value = sortChatsByLastActivity(data.chats);
}

async function createNewChat() {
  const res = await fetch('http://localhost:8000/chats', {
    method: 'POST'
  });
  const data = await res.json();

  await router.push(`/chat/${data.chat_id}`);
  window.dispatchEvent(new CustomEvent('newChatCreated'));
  await fetchChats();
}

async function deleteChat(chatId: string) {
  closeMenu();
  if (!confirm('Are you sure you want to delete this chat?')) return;

  try {
    const response = await fetch(`http://localhost:8000/chats/${chatId}`, {
      method: 'DELETE'
    });

    const result = await response.json();
    if (!response.ok) {
      console.error('Failed to delete chat:', result.error || response.statusText);
      alert('Failed to delete chat.');
      return;
    }

    await fetchChats();
    if (chatId === router.currentRoute.value.params.chatId) {
      router.push('/');
    }
  } catch (error) {
    console.error('Error deleting chat:', error);
    alert('Error deleting chat.');
  }
}

function startRename(chatId: string, currentTitle: string) {
  renameChatId.value = chatId;
  renameTitle.value = currentTitle;
}

async function submitRename() {
  if (!renameChatId.value || !renameTitle.value.trim()) return;
  await fetch(`http://localhost:8000/chats/${renameChatId.value}/rename`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_title: renameTitle.value.trim() })
  });
  renameChatId.value = null;
  renameTitle.value = '';
  await fetchChats();
}

function cancelRename() {
  renameChatId.value = null;
  renameTitle.value = '';
}

// Global click listener to close dropdown
function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement;
  const dropdowns = document.querySelectorAll('.chat-dropdown');

  let clickedInsideDropdown = false;
  dropdowns.forEach((dropdown) => {
    if (dropdown.contains(target)) {
      clickedInsideDropdown = true;
    }
  });

  if (!clickedInsideDropdown) {
    closeMenu();
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
  window.addEventListener('refreshSidebar', (e: any) => {
    chats.value = sortChatsByLastActivity(e.detail);
  });

  window.addEventListener('backendReady', async () => {
    await fetchChats();
  });
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <div class="flex h-screen w-64 flex-col gap-2 bg-base-200 p-4">
    <button class="btn btn-primary mb-2 w-full" @click="createNewChat">+ New Chat</button>
    <div class="flex-1 space-y-2 overflow-y-auto">
      <div v-for="chat in chats" :key="chat.id" class="group relative flex items-center">
        <!-- Chat title button -->
        <router-link
          :to="`/chat/${chat.id}`"
          class="btn btn-sm flex-1 justify-start truncate"
          :class="{
            'btn-primary': chat.id === $route.params.chatId,
            'btn-ghost': chat.id !== $route.params.chatId
          }"
        >
          {{ chat.title }}
        </router-link>

        <!-- Kebab icon and dropdown menu -->
        <div
          class="relative ml-1 transition-opacity"
          :class="{
            'opacity-0 group-hover:opacity-100': openMenuId !== chat.id,
            'opacity-100': openMenuId === chat.id
          }"
        >
          <!-- Kebab button -->
          <button
            class="btn btn-ghost btn-xs"
            @click.stop="toggleMenu(chat.id)"
            title="Chat options"
          >
            ⋮
          </button>

          <!-- Dropdown -->
          <div
            v-if="openMenuId === chat.id"
            class="chat-dropdown absolute right-0 z-10 mt-1 w-28 rounded border border-base-300 bg-base-100 shadow"
            @click.stop
          >
            <button
              class="block w-full px-3 py-2 text-left hover:bg-base-200"
              @click="startRename(chat.id, chat.title)"
            >
              Rename
            </button>
            <button
              class="block w-full px-3 py-2 text-left text-error hover:bg-base-200"
              @click="deleteChat(chat.id)"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Rename Modal -->
    <dialog v-if="renameChatId" class="modal" open>
      <form @submit.prevent="submitRename" class="modal-box">
        <h3 class="text-lg font-bold">Rename Chat</h3>
        <input
          v-model="renameTitle"
          placeholder="New title"
          class="input input-bordered my-4 w-full"
          required
        />
        <div class="modal-action">
          <button type="submit" class="btn btn-primary">Rename</button>
          <button type="button" @click="cancelRename" class="btn">Cancel</button>
        </div>
      </form>
    </dialog>
  </div>
</template>

<style scoped lang="less"></style>
