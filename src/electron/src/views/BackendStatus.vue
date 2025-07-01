<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';

const backendReady = ref(false);
const backendMessage = ref('');
let healthInterval: ReturnType<typeof setInterval> | null = null;

async function checkBackendHealth() {
  try {
    const res = await fetch('http://localhost:8000/health');
    backendReady.value = res.ok;
  } catch (e) {
    backendReady.value = false;
  }

  backendMessage.value = backendReady.value ? '' : 'Backend is starting up, please wait...';
}

function dispatchBackendReady() {
  const event = new Event('backendReady');
  window.dispatchEvent(event);
}

function startHealthPolling() {
  healthInterval = setInterval(async () => {
    await checkBackendHealth();
    if (backendReady.value) {
      if (healthInterval) {
        clearInterval(healthInterval);
        healthInterval = null;
      }
      dispatchBackendReady();
    }
  }, 3000);
}

onMounted(async () => {
  await checkBackendHealth();
  if (!backendReady.value) {
    startHealthPolling();
  } else {
    dispatchBackendReady();
  }
});

onBeforeUnmount(() => {
  if (healthInterval) {
    clearInterval(healthInterval);
  }
});
</script>

<template>
  <div
    v-if="!backendReady"
    class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-base-100"
  >
    <div class="loading loading-spinner loading-lg mb-4"></div>
    <p class="text-lg">{{ backendMessage }}</p>
  </div>
</template>
