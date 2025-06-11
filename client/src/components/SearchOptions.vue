<script setup>
import { ref, onMounted, computed } from 'vue';
import { config } from '../config';
import { useSettingsStore } from '@/stores/settings';
import InformationOutline from 'vue-material-design-icons/InformationOutline.vue';

const props = defineProps({
  editableMediaName: String,
  // favoriteOption: String, // Removed
});

const emit = defineEmits([
  'update:editableMediaName',
  // 'update:favoriteOption', // Removed
]);

const settingsStore = useSettingsStore();
const currentLimit = computed(() => settingsStore.getSettingValue("app", "suggestion_limit"));
const jellyfinUsers = ref([]);

// Use computed properties for v-model to ensure reactivity with parent
const internalEditableMediaName = computed({
  get: () => props.editableMediaName,
  set: (value) => emit('update:editableMediaName', value),
});

// const internalFavoriteOption = computed({ // Removed
//   get: () => props.favoriteOption,
//   set: (value) => emit('update:favoriteOption', value),
// });

onMounted(() => {
  // fetchJellyfinUsers(); // Call if users are needed for other features in this component
});

</script>

<template>
  <div class="p-4 bg-gray-800 border border-gray-700 rounded-lg">
    <div class="flex items-center mb-2">
      <h4 class="text-lg text-white font-semibold">Template Variables</h4>
      <div class="relative flex flex-col items-center group ml-2">
        <InformationOutline :size="18" class="text-gray-400 cursor-pointer" />
        <div class="absolute bottom-0 flex-col items-center hidden mb-6 group-hover:flex w-auto">
          <span class="relative z-10 p-2 text-xs leading-none text-white whitespace-nowrap bg-gray-700 shadow-lg rounded-md">
            Use these variables within the prompt template above
          </span>
          <div class="w-3 h-3 -mt-2 rotate-45 bg-gray-700"></div>
        </div>
      </div>
    </div>
    <div class="flex flex-wrap gap-2 text-sm">
      <span class="bg-gray-700 text-gray-200 px-2 py-1 rounded-md font-mono">limit={{ currentLimit }}</span>
      <span class="bg-gray-700 text-gray-200 px-2 py-1 rounded-md font-mono">
        media_name="{{ editableMediaName }}"
      </span>
      <span class="bg-gray-700 text-gray-200 px-2 py-1 rounded-md font-mono">media_exclude=auto</span>
      <!-- <span class="bg-gray-700 text-gray-200 px-2 py-1 rounded-md font-mono">favorites=auto</span> Removed -->
    </div>
  </div>
</template>
