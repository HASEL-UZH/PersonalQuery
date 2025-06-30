<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';

const expanded = ref(true);

const goals = [
  'Identify which applications you used the most last week and when you used them most intensively.',
  'Find out how often you switched between different applications or windows during work hours.',
  'See which websites you visited most frequently and how much time you spent on them.',
  'Check if the number of keystrokes relates to your self-reported productivity.',
  'Compare your productivity between your most and least productive day.',
  'Identify which activities or websites most often interrupted your focused work.',
  'Get an overview of your work patterns, most-used applications, and productivity trends.',
  'Check how much time you spent on work-related versus personal activities.',
  'Visualize how your productivity evolved across the week.',
  'Investigate how much you worked after 6pm.',
  'See how much time you spent in calls, chat apps, or email.',
  'Find which time blocks you were most productive.',
  'Check how consistent your total working hours were each day last week.',
  'See if your activity patterns differ at the beginning vs. end of the week.',
  'Find out if there are specific times or patterns when you tend to switch between applications or tasks most often.'
];

const selectedGoal = ref('');

// Utility to get today in YYYY-MM-DD format
function getTodayDate() {
  return new Date().toISOString().split('T')[0];
}

onMounted(() => {
  // Load expanded state
  const storedExpanded = localStorage.getItem('dailyGoalExpanded');
  if (storedExpanded !== null) {
    expanded.value = storedExpanded === 'true';
  }

  const today = getTodayDate();
  const stored = JSON.parse(localStorage.getItem('dailyGoal') || '{}');
  let usedIndices = stored.usedIndices || [];

  if (stored.date === today && stored.index !== undefined) {
    selectedGoal.value = goals[stored.index];
  } else {
    if (usedIndices.length >= goals.length) {
      usedIndices = [];
    }

    const availableIndices = goals.map((_, i) => i).filter((i) => !usedIndices.includes(i));

    const randomIndex = availableIndices[Math.floor(Math.random() * availableIndices.length)];

    usedIndices.push(randomIndex);

    localStorage.setItem(
      'dailyGoal',
      JSON.stringify({
        date: today,
        index: randomIndex,
        usedIndices: usedIndices
      })
    );

    selectedGoal.value = goals[randomIndex];
  }
});

// Watch and persist expanded state
watch(expanded, (newValue) => {
  localStorage.setItem('dailyGoalExpanded', String(newValue));
});
</script>

<template>
  <!-- Always visible toggle button (collapsed or expanded) -->
  <div class="fixed left-0 top-4 z-50 ml-[17rem]">
    <div
      v-if="expanded"
      class="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-4 shadow-lg transition-all duration-300"
    >
      <div class="flex items-start justify-between">
        <h2 class="text-lg font-semibold text-gray-800">🎯 Daily Goal</h2>
        <button
          @click="expanded = false"
          class="text-sm text-gray-500 transition hover:text-gray-700"
        >
          Hide
        </button>
      </div>
      <p class="mt-3 text-sm text-gray-700">
        {{ selectedGoal }}
      </p>
    </div>
    <button
      v-else
      @click="expanded = true"
      class="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1 text-sm text-gray-700 shadow-lg transition hover:bg-gray-50"
      aria-label="Expand"
    >
      🎯 Show Goal
    </button>
  </div>
</template>

<style scoped lang="less">
div > div {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
