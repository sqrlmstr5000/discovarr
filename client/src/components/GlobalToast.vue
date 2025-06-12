<script setup>
import { computed } from 'vue';
import { useToastStore } from '@/stores/toast'; // Adjust path if necessary

const toastStore = useToastStore();

const toastClasses = computed(() => {
  return {
    'bg-gray-600': toastStore.type === 'success',
    'bg-red-600': toastStore.type === 'error',
    'bg-blue-600': toastStore.type === 'info',
    'bg-amber-600': toastStore.type === 'warning',
  };
});
</script>

<template>
  <transition name="toast-fade">
    <div
      v-if="toastStore.isVisible"
      :class="[
        'fixed top-5 right-5 p-4 rounded-md shadow-lg text-white z-[1000]', // Ensure high z-index
        toastClasses
      ]"
      role="alert"
    >
      {{ toastStore.message }}
      <button
        @click="toastStore.hide()"
        class="ml-4 text-xl font-semibold leading-none opacity-75 hover:opacity-100 focus:outline-none"
        aria-label="Close"
      >
        &times;
      </button>
    </div>
  </transition>
</template>

<style scoped>
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}
</style>
