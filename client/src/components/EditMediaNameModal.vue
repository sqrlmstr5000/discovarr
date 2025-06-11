<template>
  <div v-if="show" class="fixed inset-0 z-50 bg-black bg-opacity-75 flex items-center justify-center p-4" @click.self="closeModal">
    <div class="bg-gray-800 p-6 rounded-lg shadow-xl w-full max-w-md">
      <h3 class="text-xl font-semibold text-white mb-4">Edit Media Name</h3>
      <input
        type="text"
        v-model="internalMediaName"
        @keyup.enter="save"
        class="w-full p-3 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 mb-4"
        placeholder="Enter media name"
      />
      <div class="flex justify-end space-x-3">
        <button
          @click="closeModal"
          class="px-4 py-2 text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-lg focus:outline-none"
        >
          Cancel
        </button>
        <button
          @click="save"
          class="px-4 py-2 text-white bg-blue-600 hover:bg-blue-700 rounded-lg focus:outline-none"
        >
          Save
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  show: Boolean,
  currentMediaName: String,
});

const emit = defineEmits(['close', 'update:mediaName']);

const internalMediaName = ref('');

watch(() => props.currentMediaName, (newValue) => {
  internalMediaName.value = newValue || '';
}, { immediate: true });

const closeModal = () => {
  emit('close');
};

const save = () => {
  emit('update:mediaName', internalMediaName.value);
  closeModal();
};
</script>