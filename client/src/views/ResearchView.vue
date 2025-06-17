<template>
  <div class="flex flex-col h-screen text-white">
    <GlobalToast />
    <!-- Top Row (25% height) -->
    <div class="h-1/4 p-6 md:p-8 flex flex-col">
      <div class="bg-gray-800 p-4 rounded-lg shadow-md border border-gray-700 flex-grow flex items-center justify-center">
        <blockquote class="text-center">
          <p class="text-xl italic text-gray-300">
            "The only source of knowledge is experience."
          </p>
          <footer class="mt-2 text-sm text-gray-500">- Albert Einstein (Placeholder)</footer>
        </blockquote>
      </div>
    </div>

    <!-- Bottom Row (75% height) -->
    <div class="h-3/4 p-6 md:p-8 bg-gray-900/30 overflow-y-auto">
      <div class="mb-6 relative">
        <div class="flex items-end space-x-3">
          <div class="flex-grow">
            <label for="mediaNameInput" class="block text-sm font-medium text-gray-300 mb-1">
              Media Name for Research
            </label>
            <input
              ref="mediaNameInputRef"
              type="text"
              id="mediaNameInput"
              v-model="mediaName"
              placeholder="Enter media name (e.g., from query string)"
              class="w-full p-3 bg-gray-800 border border-gray-700 rounded-md focus:ring-discovarr focus:border-discovarr placeholder-gray-500"
              @focus="showSearchResults = true"
              @blur="handleInputBlur"
            />
          </div>
          <button
            @click="handleResearch"
            :disabled="!selectedMediaId || researchLoading"
            class="px-4 py-3 bg-discovarr hover:bg-amber-500 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
            :title="!selectedMediaId ? 'Select a media item first' : 'Generate research for selected media'"
          >
            <span v-if="researchLoading">Researching...</span>
            <span v-else>Research</span>
          </button>
          <button
            @click="handleViewPrompt"
            :disabled="!mediaName"
            class="px-4 py-3 bg-indigo-600 hover:bg-gray-600 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
            title="View the research prompt template"
          >
            Preview Prompt
          </button>
        </div>
        <!-- Search Results Dropdown -->
        <div
          v-if="showSearchResults && (searchResults.length > 0 || searchLoading || searchError)"
          ref="searchResultsContainerRef"
          class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-md shadow-lg max-h-60 overflow-y-auto"
        >
          <div v-if="searchLoading" class="p-3 text-gray-400">Searching...</div>
          <div v-else-if="searchError" class="p-3 text-red-400">{{ searchError }}</div>
          <ul v-else-if="searchResults.length > 0">
            <li
              v-for="result in searchResults"
              :key="result.media_id || result.title"
              @mousedown="selectMedia(result)"
              class="p-3 hover:bg-gray-700 cursor-pointer text-gray-300"
            >
              {{ result.title }} ({{ result.media_type }})
            </li>
          </ul>
        </div>
      </div>
      <div>
        <h2 class="text-2xl font-semibold mb-4">Research Details for: {{ mediaName || '...' }}</h2>
        <p>Further research content and components will go here.</p>
        <!-- Add your research-specific components and layout here -->
      </div>

    </div>
    <!-- Full Screen Prompt Modal using Teleport -->
    <Teleport to="body">
      <div v-if="showPromptModal" class="fixed inset-0 z-[9999] bg-black bg-opacity-90 flex flex-col p-4 sm:p-8">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-2xl font-semibold text-white">Research Prompt Preview</h3>
          <button @click="showPromptModal = false" class="text-gray-300 hover:text-white p-2 rounded-full hover:bg-gray-700">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-7 h-7">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <textarea
          :value="promptForModal"
          readonly
          class="flex-grow w-full p-3 bg-gray-800 text-gray-200 border border-gray-700 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-discovarr"
          placeholder="Loading prompt..."
        ></textarea>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import { config } from '../config';
import { useToastStore } from '@/stores/toast';
import GlobalToast from '@/components/GlobalToast.vue';
import { useSettingsStore } from '@/stores/settings'; // Adjust path if necessary
const settingsStore = useSettingsStore();

const quote = ref("The only true wisdom is in knowing you know nothing.");
const quoteAuthor = ref("Socrates (Placeholder)");

const route = useRoute();
const toastStore = useToastStore();

const mediaName = ref('');
const selectedMediaId = ref(null); // To store tmdb_id
const selectedMediaType = ref(null);

const searchResults = ref([]);
const searchLoading = ref(false);
const searchError = ref('');
const showSearchResults = ref(false);
const researchLoading = ref(false);

const mediaNameInputRef = ref(null); // Ref for the input element
const searchResultsContainerRef = ref(null); // Ref for the search results container

const showPromptModal = ref(false);
const promptForModal = ref('');

const currentDefaultResearchPrompt = computed(() => settingsStore.getSettingValue("app", "default_research_prompt"));

let debounceTimer = null;
let isSelectingMedia = false; // Flag to manage selection state

const debounce = (func, delay) => {
  return (...args) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      func.apply(this, args);
    }, delay);
  };
};

const performSearch = async (query) => {
  if (!query || query.length < 2) { // Don't search for very short queries
    searchResults.value = [];
    searchError.value = '';
    showSearchResults.value = query.length > 0; // Show if there's some text, even if no results yet
    return;
  }
  searchLoading.value = true;
  searchError.value = '';
  searchResults.value = [];
  showSearchResults.value = true;

  try {
    const response = await fetch(`${config.apiUrl}/media/search?query=${encodeURIComponent(query)}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Search failed' }));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    const data = await response.json();
    searchResults.value = data;
    if (data.length === 0) {
      searchError.value = 'No media found matching your query.';
    }
  } catch (error) {
    console.error('Error searching media:', error);
    searchError.value = error.message || 'Failed to search media.';
    searchResults.value = [];
  } finally {
    searchLoading.value = false;
  }
};

const debouncedSearch = debounce(performSearch, 300);

watch(mediaName, (newValue) => {
  if (isSelectingMedia) {
    // If mediaName is changing due to a selection, don't reset selectedMediaId
    return;
  }
  if (document.activeElement === mediaNameInputRef.value) { // Only search if input is focused
    selectedMediaId.value = null; // Clear selected ID if user types again
    selectedMediaType.value = null;
    debouncedSearch(newValue);
  } else if (!newValue) { // If mediaName is cleared programmatically (e.g. after selection)
    // This case might also need to be careful if isSelectingMedia is true,
    // but selectMedia already handles clearing searchResults and showSearchResults.
    searchResults.value = [];
    showSearchResults.value = false;
  }
});

const selectMedia = (media) => {
  isSelectingMedia = true; // Set flag before reactive changes

  mediaName.value = media.title;
  selectedMediaId.value = media.media_id; 
  selectedMediaType.value = media.media_type;
  searchResults.value = [];
  showSearchResults.value = false;
  console.log('Selected Media for research:', mediaName.value, 'PK:', selectedMediaId.value, 'Type:', selectedMediaType.value, 'TMDB ID:', media.tmdb_id);

  nextTick(() => {
    isSelectingMedia = false; // Reset flag after reactive updates have propagated
  });
};

const handleInputBlur = (event) => {
  // Delay hiding results to allow click on results to register
  setTimeout(() => {
    // Check if the new focused element is part of the search results container
    if (!searchResultsContainerRef.value || !searchResultsContainerRef.value.contains(document.activeElement)) {
      showSearchResults.value = false;
    }
  }, 150);
};

onMounted(() => {
  if (route.query.mediaName) {
    mediaName.value = route.query.mediaName;
    // Optionally, perform an initial search if mediaName is pre-filled
    // debouncedSearch(mediaName.value); 
  }
});

const handleResearch = async () => {
  if (!selectedMediaId.value || !mediaName.value) {
    toastStore.show('Please select a media item from the search results first.', 'warning');
    return;
  }
  researchLoading.value = true;
  console.log('Researching:', mediaName.value, selectedMediaId.value, selectedMediaType.value);
  try {
    const response = await fetch(`${config.apiUrl}/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ media_name: mediaName.value, media_id: selectedMediaId.value, prompt: currentDefaultResearchPrompt.value })
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.message || 'Failed to initiate research.');
    }
    toastStore.show(`Research started for ${mediaName.value}: ${result.message}`, 'success');
    // TODO: Display research_text or navigate, or update a component with the result.research_text
  } catch (error) {
    toastStore.show(`Research Error: ${error.message}`, 'error');
  } finally {
    researchLoading.value = false;
  }
};

const handleViewPrompt = async () => {
  if (!mediaName.value) {
    toastStore.show('Please enter or select a media name first.', 'warning');
    return;
  }
  promptForModal.value = 'Loading prompt...'; // Placeholder while fetching
  showPromptModal.value = true;

  try {
    const response = await fetch(`${config.apiUrl}/research/prompt/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ media_name: mediaName.value, prompt: currentDefaultResearchPrompt.value })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to fetch prompt preview.');
    }
    promptForModal.value = data.result;
  } catch (error) {
    toastStore.show(`Error fetching prompt: ${error.message}`, 'error');
    promptForModal.value = `Error loading prompt: ${error.message}`;
  }
};
</script>