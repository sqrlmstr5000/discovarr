<script setup>
import { ref, onMounted, computed } from 'vue';
import { config } from '../config';
import { useSettingsStore } from '@/stores/settings';
import InformationOutline from 'vue-material-design-icons/InformationOutline.vue';

const props = defineProps({
  editableMediaName: String,
  favoriteOption: String,
});

const emit = defineEmits([
  'update:editableMediaName',
  'update:favoriteOption',
]);

const settingsStore = useSettingsStore();
const currentLimit = computed(() => settingsStore.getSettingValue("app", "suggestion_limit"));
const jellyfinUsers = ref([]);

// Use computed properties for v-model to ensure reactivity with parent
const internalEditableMediaName = computed({
  get: () => props.editableMediaName,
  set: (value) => emit('update:editableMediaName', value),
});

const internalFavoriteOption = computed({
  get: () => props.favoriteOption,
  set: (value) => emit('update:favoriteOption', value),
});

const fetchJellyfinUsers = async () => {
  try {
    const response = await fetch(`${config.apiUrl}/users`);
    if (!response.ok) {
      throw new Error('Failed to load Jellyfin users');
    }
    const users = await response.json();
    jellyfinUsers.value = users.map(user => ({ id: user.Id, name: user.Name }));
  } catch (error) {
    console.error('Failed to load Jellyfin users:', error);
    // Optionally, set an error state or notify the user
  }
};

onMounted(() => {
  fetchJellyfinUsers();
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
      <span class="bg-gray-700 text-gray-200 px-2 py-1 rounded-md font-mono">favorites=auto</span>
    </div>
    <h4 class="text-lg text-white font-semibold my-3">Search Options</h4>
    <label class="text-gray-200">
      Include Favorites From:
      <select
        v-model="internalFavoriteOption"
        class="bg-gray-700 text-gray-200 px-2 py-1 font-mono focus:ring-1 focus:ring-aiarr rounded-md w-auto"
        title="Select favorite option: 'all' or a specific username"
      >
        <option value="">None</option>
        <option value="all">All Users</option>
        <option v-for="user in jellyfinUsers" :key="user.id" :value="user.name">
          {{ user.name }}
        </option>
      </select>
    </label>
  </div>
</template>
