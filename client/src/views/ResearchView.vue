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
          >
            <span v-if="researchLoading">Researching...</span>
            <span v-else>Research</span>
          </button>
          <button
            @click="handleViewPrompt"
            :disabled="!mediaName"
            class="px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
          >
            View Prompt
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
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { config } from '../config';
import { useToastStore } from '@/stores/toast';
import GlobalToast from '@/components/GlobalToast.vue';

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

let debounceTimer = null;

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
  if (document.activeElement === mediaNameInputRef.value) { // Only search if input is focused
    selectedMediaId.value = null; // Clear selected ID if user types again
    selectedMediaType.value = null;
    debouncedSearch(newValue);
  } else if (!newValue) { // If mediaName is cleared programmatically (e.g. after selection)
    searchResults.value = [];
    showSearchResults.value = false;
  }
});

const selectMedia = (media) => {
  mediaName.value = media.title;
  selectedMediaId.value = media.media_id; // Assuming media_id from search is tmdb_id
  selectedMediaType.value = media.media_type;
  searchResults.value = [];
  showSearchResults.value = false;
  console.log('Selected Media:', mediaName.value, selectedMediaId.value, selectedMediaType.value);
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
      body: JSON.stringify({ media_name: mediaName.value, media_id: selectedMediaId.value })
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

const handleViewPrompt = () => {
  // Placeholder for viewing prompt functionality
  console.log('View Prompt button clicked for:', mediaName.value);
  // This might open a modal or display the prompt by calling /research/prompt/preview
};
</script>