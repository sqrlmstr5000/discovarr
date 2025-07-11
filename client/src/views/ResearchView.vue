<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import { config } from '../config';
import { useToastStore } from '@/stores/toast';
import GlobalToast from '@/components/GlobalToast.vue';
import Markdown from '@/components/Markdown.vue'; // Adjust path if necessary
import { useSettingsStore } from '@/stores/settings'; // Adjust path if necessary
import BrainIcon from 'vue-material-design-icons/Brain.vue';
import DeleteIcon from 'vue-material-design-icons/Delete.vue'; // Import DeleteIcon

const settingsStore = useSettingsStore();

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
const isEditingPromptTemplate = ref(false);

const allResearchData = ref([]);
const researchListLoading = ref(false);
const researchListError = ref('');

const collapsedStates = ref({}); // To store collapsed state for each research item
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

const closeModal = () => {
  showPromptModal.value = false;
  isEditingPromptTemplate.value = false;
  // promptForModal.value = ''; // Optionally clear if needed
};

const handleDeleteResearch = async (researchId) => {
  if (!confirm(`Are you sure you want to delete this research item (ID: ${researchId})? This action cannot be undone.`)) {
    return;
  }
  try {
    const response = await fetch(`${config.apiUrl}/research/${researchId}`, {
      method: 'DELETE',
    });
    const result = await response.json();
    if (!response.ok || result.status !== 'success') {
      throw new Error(result.message || `Failed to delete research item ${researchId}. Status: ${response.status}`);
    }
    toastStore.show(`Research item ${researchId} deleted successfully.`, 'success');
    await fetchAllResearch(); // Refresh the list
  } catch (error) {
    console.error('Error deleting research item:', error);
    toastStore.show(`Error deleting research: ${error.message}`, 'error');
  }
};

const performSearch = async (query) => {
  if (!query || query.length < 2) { // Don't search for very short queries
    searchResults.value = [];
    searchError.value = '';
    showSearchResults.value = false; // Hide immediately if query is too short
    return;
  }
  searchError.value = '';
  searchResults.value = [];
  // Don't immediately show searchResults container.
  // It will be shown if loading takes time, or if there are results/errors.

  // Timer to delay showing the "Searching..." message
  const loadingTimer = setTimeout(() => {
    // Only show loading if the search for this query is still relevant
    // and we don't already have results or an error.
    if (mediaName.value === query && searchResults.value.length === 0 && !searchError.value) {
      searchLoading.value = true;
      showSearchResults.value = true; // Show dropdown for "Searching..."
    }
  }, 300); // 300ms delay

  try {
    const response = await fetch(`${config.apiUrl}/media/search?query=${encodeURIComponent(query)}`);
    clearTimeout(loadingTimer); // Clear timer as soon as response is received

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Search failed' }));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    const data = await response.json();
    if (data.length === 0) {
      searchResults.value = []; // Ensure searchResults is empty
      // The finally block will handle hiding if searchLoading was false
    } else {
      searchResults.value = data;
      showSearchResults.value = true; // Ensure it's shown if there are results
    }
  } catch (error) {
    console.error('Error searching media:', error);
    searchError.value = error.message || 'Failed to search media.';
    searchResults.value = [];
    clearTimeout(loadingTimer); // Also clear timer on error
    showSearchResults.value = true; // Show dropdown to display the error
  } finally {
    if (searchLoading.value) { // If the "Searching..." message was shown
      searchLoading.value = false;
    }
    // If, after everything, there are no results and no error, hide the dropdown.
    if (searchResults.value.length === 0 && !searchError.value) {
      showSearchResults.value = false;
    }
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
    if (newValue && newValue.length >= 2) {
      debouncedSearch(newValue);
    } else {
      // If query becomes too short, clear everything and hide results
      clearTimeout(debounceTimer); // Clear any pending debounced search
      searchResults.value = [];
      searchError.value = '';
      searchLoading.value = false; // Reset loading state
      showSearchResults.value = false;
    }
  } else if (!newValue) { // If mediaName is cleared programmatically (e.g. after selection)
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

const fetchAllResearch = async () => {
  researchListLoading.value = true;
  researchListError.value = '';
  try {
    const response = await fetch(`${config.apiUrl}/research`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to load research data' }));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    allResearchData.value = await response.json();
    // Initialize collapsed states for new data - all closed by default
    allResearchData.value.forEach(item => {
      if (collapsedStates.value[item.id] === undefined) collapsedStates.value[item.id] = true;
    });
  } catch (error) {
    console.error('Error fetching all research:', error);
    researchListError.value = error.message || 'Failed to load research data.';
    allResearchData.value = [];
  } finally {
    researchListLoading.value = false;
  }
};

const toggleCollapse = (itemId) => {
  collapsedStates.value[itemId] = !collapsedStates.value[itemId];
};

onMounted(async () => {
  if (route.query.mediaName) {
    mediaName.value = route.query.mediaName;
  }
  await fetchAllResearch(); // Fetch all research on mount
});

const handleResearch = async () => {
  if (!mediaName.value) {
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
    // Refresh the list of all research items
    await fetchAllResearch();
  } catch (error) {
    toastStore.show(`Research Error: ${error.message}`, 'error');
  } finally {
    researchLoading.value = false;
  }
};

const handleViewPrompt = async () => {
  isEditingPromptTemplate.value = false; // Ensure view mode
  if (!mediaName.value) {
    toastStore.show('Please enter or select a media name first.', 'warning');
    return;
  }
  promptForModal.value = 'Loading prompt...'; // Placeholder while fetching
  // isEditingPromptTemplate.value should be false here
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

const handleEditDefaultPrompt = () => {
  isEditingPromptTemplate.value = true;
  promptForModal.value = currentDefaultResearchPrompt.value;
  showPromptModal.value = true;
};

const saveDefaultPromptChanges = () => {
  if (!isEditingPromptTemplate.value) return;

  // Changes are local to promptForModal due to v-model.
  // Not saving to settingsStore as per the new requirement.
  closeModal();
};

const savePromptAsDefault = () => {
  if (!isEditingPromptTemplate.value) return;
  settingsStore.setSettingValue('app', 'default_research_prompt', promptForModal.value);
  toastStore.show('Default research prompt updated successfully!', 'success');
  closeModal();
};
</script>

<template>
  <div class="flex flex-col h-screen text-white">
    <GlobalToast />
    <!-- Top Row (25% height) -->
    <div class="h-1/5 p-6 md:p-8 flex flex-col relative">
      <div class="bg-gray-800 p-4 rounded-lg shadow-md border border-gray-700 flex-grow flex items-center justify-center relative overflow-hidden">
        <blockquote class="text-center">
          <p class="text-md italic text-gray-300 px-4">
             The goal of this research tool is to better understand why you like what you like. To do that we use the LLM to analyze a title based on a common template and save the resulting report.
             Right now that's about it. In the future I would like to expand on this. If we create an embedding for each report, we could then use that to perform a semantic search on your library like:
             "psycholocical thrillers set in the desert" or "sad movies with a happy ending" or "movies with a strong female lead". Then use that to create a Collection.
          </p>
        </blockquote>
        <div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 opacity-20">
          <BrainIcon :size="64" fillColor="#4A5568" /> 
        </div>
      </div>
    </div>

    <!-- Bottom Row (75% height) -->
    <div class="h-4/5 p-6 md:p-8 bg-gray-900/30 overflow-y-auto">
      <div class="mb-6 relative">
        <div class="flex items-end space-x-3">
          <div class="flex-grow">
            <label for="mediaNameInput" class="block text-sm font-medium text-gray-300 mb-1">
              Media Title to Research
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
            :disabled="!mediaName || researchLoading"
            class="px-4 py-3 bg-discovarr hover:bg-amber-500 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
            :title="!selectedMediaId ? 'Select a media item first' : 'Generate research...'"
          >
            <span v-if="researchLoading">Researching...</span>
            <span v-else>Research</span>
          </button>
          <button
            @click="handleViewPrompt"
            :disabled="!mediaName || researchLoading"
            class="px-4 py-3 bg-indigo-600 hover:bg-gray-600 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
            title="View the research prompt template"
          >
            Preview Prompt
          </button>
          <button
            @click="handleEditDefaultPrompt"
            :disabled="researchLoading"
            class="px-4 py-3 bg-gray-600 hover:bg-gray-500 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
            title="Edit the research prompt template"
          >
            Edit Prompt
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
      <!-- Research Results Section -->
      <div>
        <h2 class="text-2xl font-semibold mb-4">All Existing Research</h2>
        <div v-if="researchListLoading" class="text-center py-4 text-gray-400">
          Loading research data...
        </div>
        <div v-else-if="researchListError" class="text-center py-4 text-red-400">
          Error: {{ researchListError }}
        </div>
        <div v-else-if="allResearchData.length > 0" class="space-y-6">
          <div v-for="item in allResearchData" :key="item.id" class="bg-gray-800 p-4 rounded-lg shadow-md border border-gray-700">
            <h3
              @click="toggleCollapse(item.id)"
              class="text-xl font-semibold text-discovarr mb-2 cursor-pointer flex justify-between items-center"
            >
              <span>{{ item.media_title || 'Unknown Media' }}</span>
              <div class="flex items-center">
                <button
                  @click.stop="handleDeleteResearch(item.id)"
                  class="p-1 text-gray-400 hover:text-red-500 focus:outline-none rounded-full hover:bg-gray-700/80 mr-2"
                  title="Delete this research item"
                >
                  <DeleteIcon :size="20" />
                </button>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 transition-transform duration-200" :class="{'rotate-180': !collapsedStates[item.id]}">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </h3>
            <div v-if="!collapsedStates[item.id]" class="mt-3">
              <Markdown :mdstring="item.research" />
              <div class="text-xs text-gray-500 mt-3 pt-3 border-t border-gray-700/50">
                Created: {{ new Date(item.created_at).toLocaleString() }}
                <span v-if="item.created_at !== item.updated_at"> | Updated: {{ new Date(item.updated_at).toLocaleString() }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="text-center py-4 text-gray-500">
          No research data found.
        </div>
      </div>

    </div>
    <!-- Full Screen Prompt Modal using Teleport -->
    <Teleport to="body">
      <div v-if="showPromptModal" class="fixed inset-0 z-[9999] bg-black bg-opacity-90 flex flex-col p-4 sm:p-8">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-2xl font-semibold text-white">
            {{ isEditingPromptTemplate ? 'Edit Default Research Prompt' : 'Research Prompt Preview' }}
          </h3>
          <button @click="closeModal" class="text-gray-300 hover:text-white p-2 rounded-full hover:bg-gray-700">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-7 h-7">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <textarea
          v-model="promptForModal"
          :readonly="!isEditingPromptTemplate"
          class="flex-grow w-full p-3 bg-gray-800 text-gray-200 border border-gray-700 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-discovarr"
          placeholder="Loading prompt..."
        ></textarea>
        <div v-if="isEditingPromptTemplate" class="mt-4 flex justify-end">
          <button
            @click="savePromptAsDefault"
            title="Save this prompt as the default for future research. Saves to settings.app.default_research_prompt"
            class="px-4 py-2 mr-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
          >
            Save As Default
          </button>
          <button
            @click="saveDefaultPromptChanges"
            title="Save changes to the current prompt template for this research session only."
            class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white font-semibold rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 focus:ring-offset-gray-900 transition ease-in-out duration-150"
          >
            Confirm & Close
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>