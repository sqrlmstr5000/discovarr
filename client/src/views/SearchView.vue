<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue';
// import { useRouter, useRoute } from 'vue-router'; // No longer needed for navigation
import { config } from '../config';
import Close from 'vue-material-design-icons/Close.vue';
import Delete from 'vue-material-design-icons/Delete.vue';
import ChevronDown from 'vue-material-design-icons/ChevronDown.vue';
import ChevronUp from 'vue-material-design-icons/ChevronUp.vue';
import Edit from 'vue-material-design-icons/Pencil.vue';
import Run from 'vue-material-design-icons/Run.vue';
import CalendarClock from 'vue-material-design-icons/CalendarClock.vue';
import InformationOutline from 'vue-material-design-icons/InformationOutline.vue';
import Send from 'vue-material-design-icons/Send.vue'; // Icon for request button
import SearchScheduleModal from '../components/SearchScheduleModal.vue'; // Import SearchScheduleModal
import SearchOptions from '../components/SearchOptions.vue'; 
import RequestModal from '../components/RequestModal.vue'; 
import { useRouter, useRoute } from 'vue-router';
import { useSettingsStore } from '@/stores/settings'; // Adjust path if necessary
const settingsStore = useSettingsStore();
import { useToastStore } from '@/stores/toast';
const toastStore = useToastStore();

// Access a specific setting's value directly
const currentLimit = computed(() => settingsStore.getSettingValue("app", "suggestion_limit"));
const currentDefaultPrompt = computed(() => settingsStore.getSettingValue("app", "default_prompt"));

const props = defineProps({
  searchId: {
    type: [String, Number],
    default: null
  }
});
const route = useRoute();

const initialPrompt = computed(() => route.query.initialPrompt || '');
const initialMediaName = computed(() => route.query.initialMediaName || null);
const currentLoadedSearchId = ref(props.searchId); // Local ref for the active search ID
const searchName = ref('');
const searchText = ref('');
const searchResults = ref(null);
const loading = ref(false);
const saving = ref(false); // Track if the current search is the default one (ID=1)
const isCurrentSearchDefault = computed(() => currentLoadedSearchId.value === 1 || currentLoadedSearchId.value === '1');
const initialLoadingDone = ref(false); // To track if initial data load is complete
const searchInput = ref(null);
const searchNameInputRef = ref(null); // Ref for the search name input
const searchModalContentRef = ref(null); // Ref for the main scrollable content
const isSearchesExpanded = ref(true);
const selectedSearch = ref(null);
const showEditModal = ref(false);
const showRawJson = ref(false); // Added for toggling raw JSON view
const expandedResults = ref({}); // To track expanded state of accordion items
const previewResult = ref('');
const loadingPreview = ref(false);
const previewError = ref('');

// Saved Searches State
const savedSearches = ref([]);
const loadingSavedSearches = ref(false);
const showRequestModal = ref(false);
const isPreviewExpanded = ref(false); // For collapsible preview
const selectedMediaForRequest = ref(null);
const favoriteOption = ref(''); // For favorite media option

const editableMediaName = ref('');

const emit = defineEmits(['close', 'refresh']);

const loadSearchById = async (id) => {
  try {
    const response = await fetch(`${config.apiUrl}/search/${id}`);
    if (!response.ok) {
      throw new Error(`Failed to load search with ID ${id}. Status: ${response.status}`);
    }
    const searchData = await response.json();
    if (searchData) {
      currentLoadedSearchId.value = id; // Update local ref
      searchName.value = searchData.name || '';
      searchText.value = searchData.prompt || '';
      favoriteOption.value = searchData.favorites_option || '';
      // editableMediaName is typically a runtime parameter, not stored with the search prompt itself.
      // It will be set by initialMediaName if provided.
      console.log(`Loaded search ${id}:`, searchData);
    } else {
      console.warn(`Search data for ID ${id} was empty or null.`);
      // Fallback to defaults if search data is not sufficient
      searchText.value = initialPrompt || currentDefaultPrompt.value;
      searchName.value = ''; // Clear name for fallback
      currentLoadedSearchId.value = null; // Clear if search not found
    }
  } catch (error) {
    console.error('Failed to load search by ID:', error);
    // Fallback to defaults on error
    searchText.value = initialPrompt || currentDefaultPrompt.value;
  } finally {
    initialLoadingDone.value = true;
  }
};

const loadSavedSearches = async () => {
  loadingSavedSearches.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/search`);
    if (!response.ok) {
      throw new Error(`Failed to load saved searches. Status: ${response.status}`);
    }
    savedSearches.value = await response.json();
  } catch (error) {
    console.error('Failed to load saved searches:', error);
  } finally {
    loadingSavedSearches.value = false;
  }
};

onMounted(async () => {
  console.log("Search.vue Initial Props:", props);

  // Determine if we are loading a specific search or starting fresh/default
  currentLoadedSearchId.value = props.searchId; // Initialize local ref with prop
  console.log(`props.searchId: ${props.searchId}`)
  console.log(`initialPrompt: ${initialPrompt.value}`)
  if (props.searchId) {
    console.log("Loading specific search by searchId")
    await loadSearchById(props.searchId);
  } else if (initialPrompt.value) {
    console.log("Using prompt from query params")
    searchText.value = initialPrompt.value;
  } else {
    // No searchId and no initialPrompt from query. Use default prompt.
    // Handle potential async loading of currentDefaultPrompt from settings store.
    if (currentDefaultPrompt.value) {
      searchText.value = currentDefaultPrompt.value;
      console.log("Using default prompt (immediately available):", searchText.value);
    } else {
      searchText.value = ''; // Ensure searchText is empty while waiting for default prompt
      console.log("Default prompt not immediately available or is empty. currentDefaultPrompt:", currentDefaultPrompt.value, ". Setting up watcher.");
      const unwatchDefaultPrompt = watch(currentDefaultPrompt, (newDefaultVal) => {
        if (newDefaultVal) { // When currentDefaultPrompt gets a truthy value
          // Only update if searchText is still empty, implying it hasn't been
          // set by user input or other logic in the interim.
          if (searchText.value === '') {
            searchText.value = newDefaultVal;
            console.log("Default prompt applied via watcher:", searchText.value);
          } else {
            console.log("Default prompt became available via watcher, but searchText was already modified. Current searchText:", searchText.value, "New default:", newDefaultVal);
          }
          unwatchDefaultPrompt(); // Important: Stop watching after the first valid update
        }
      }, { immediate: false }); // immediate: false ensures we only react to changes after this setup
    }
  }
  console.log(`searchText: ${searchText.value}`)
  console.log(`initialMediaName: ${initialMediaName.value}`)

  // If no searchId was provided, it's either a new search or the default state
  if (!currentLoadedSearchId.value) { 
    initialLoadingDone.value = true; // If no searchId, initial loading is effectively done
  }

  nextTick(() => {
    // editableMediaName should be set after searchText logic,
    // as its presence doesn't dictate the prompt source.
    if (initialMediaName.value) {
      editableMediaName.value = initialMediaName.value || '';
    }
    searchInput.value?.focus();
  });
  loadSavedSearches();
});


onBeforeUnmount(() => {
});

const handleSubmit = async () => {
  if (!searchText.value.trim()) return;
  loading.value = true;
  
  try {
    console.log(`searchText.value: ${searchText.value}`)
    console.log(`editableMediaName.value: ${editableMediaName.value}`)
    console.log(`favoriteOption.value: ${favoriteOption.value}`)
    const response = await fetch(`${config.apiUrl}/gemini/similar_media_custom`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        prompt: searchText.value, 
        media_name: editableMediaName.value || null, // This is the media_name for the prompt template
        favorites_option: favoriteOption.value || null
      })
    });
    
    searchResults.value = await response.json();
  } catch (error) {
    console.error('Search failed:', error);
  } finally {
    loading.value = false;
  }
};

const handlePreview = async () => {
  if (!searchText.value.trim()) {
    previewError.value = 'Prompt cannot be empty for preview.';
    previewResult.value = '';
    return;
  }
  loadingPreview.value = true;
  previewError.value = '';
  previewResult.value = ''; // Clear previous result

  try {
    const payload = {
      prompt: searchText.value,
      limit: Number(currentLimit.value) || 5, // Ensure number and provide default
      media_name: editableMediaName.value || null,
      favorite_option: favoriteOption.value || null // Include favorite option if set
    };

    const response = await fetch(`${config.apiUrl}/search/prompt/preview`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const responseText = JSON.parse(await response.text());

    if (!response.ok) {
      let errorMessage = `HTTP error ${response.status}`;
      try {
        const errorJson = responseText;
        errorMessage = errorJson.detail || `${errorMessage}: ${responseText}`;
      } catch (e) {
        errorMessage += `: ${responseText}`;
      }
      throw new Error(errorMessage);
    }
    previewResult.value = responseText.result;
    isPreviewExpanded.value = true; // Expand on successful preview
  } catch (error) {
    console.error('Preview failed:', error);
    previewError.value = error.message || 'Failed to generate preview.';
  } finally {
    loadingPreview.value = false;
  }
};

const handleSave = async () => {
  // Ensure prompt is not empty
  if (!searchText.value.trim()) {
    toastStore.show('Prompt cannot be empty.');
    return;
  }
  // Ensure searchName is provided if it's not the default search (which is readonly)
  if (!isCurrentSearchDefault.value && !searchName.value.trim()) {
     toastStore.show('Please provide a name for the search.');
     return;
  }

  saving.value = true;
  try {
    const payload = {
      prompt: searchText.value.trim(),
      name: searchName.value.trim() || null, // Use the name from the input
      favorites_option: favoriteOption.value || null,
    };

    let response;
    if (currentLoadedSearchId.value) {
      // Update existing search
      response = await fetch(`${config.apiUrl}/search/${currentLoadedSearchId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      // Save as a new search
      response = await fetch(`${config.apiUrl}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    if (!response.ok) {
      throw new Error(`Failed to save search. Status: ${response.status}`);
    }
    const savedSearchData = await response.json();
    if (!currentLoadedSearchId.value && savedSearchData && savedSearchData.id) {
      currentLoadedSearchId.value = savedSearchData.id; // Update current ID if it was a new save
    }
    toastStore.show(`Search "${payload.name || 'Unnamed Search'}" saved successfully!`);
    await loadSavedSearches(); // Reload the list after saving
  } catch (error) {
    console.error('Failed to save search:', error);
    toastStore.show(`Failed to save search: ${error.message}. Please try again.`);
  } finally {
    saving.value = false;
  }
};

const handleDelete = async (id) => { // Keep this method for deleting from the list
  try {
    const response = await fetch(`${config.apiUrl}/search/${id}`, {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      throw new Error('Failed to delete search');
    }
    
    await loadSavedSearches(); // Reload saved searches after deletion
  } catch (error) {
    console.error('Failed to delete search:', error);
    toastStore.show('Failed to delete search. Please try again.', 'error');
  }
};

const handleCancel = () => {
  searchName.value = '';
  // Reset searchText to the current default prompt or empty if not available
  searchText.value = currentDefaultPrompt.value || '';
  editableMediaName.value = '';
  favoriteOption.value = '';
  
  searchResults.value = null;
  previewResult.value = '';
  previewError.value = '';
  isPreviewExpanded.value = false; // Collapse preview section
  
  currentLoadedSearchId.value = null; // Clear the loaded search ID
  
  // Ensure the form is considered ready and buttons are enabled
  initialLoadingDone.value = true; 

  nextTick(() => {
    searchInput.value?.focus(); // Focus on the prompt input
  });
  toastStore.show('Search form has been cleared.', 'info');
};

const rerunSearch = async (search) => {
  loading.value = true;
  try {
    let endpoint = `${config.apiUrl}/gemini/similar_media/search/${search.id}`;
    if (search.id === 1) {
      endpoint = `${config.apiUrl}/process`;
    }

    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error('Failed to run search');
    }
    searchResults.value = await response.json();
    emit('refresh');
  } catch (error) {
    console.error('Failed to run search:', error);
    toastStore.show('Failed to run search. Please try again.');
  } finally {
    loading.value = false;
  }
};

const toggleSearches = () => {
  isSearchesExpanded.value = !isSearchesExpanded.value;
};

const handleEdit = async (search) => {
  try {
    await loadSearchById(search.id); // Load the selected search into the main form fields
    // Clear previous state
    // searchResults.value = null; // Clear existing search results
    isPreviewExpanded.value = false; // Close the prompt preview section
    nextTick(() => {
      // Highlight fields
      searchInput.value.focus();
    });
  } finally {
  }
};

const openEditModalForSchedule = (search) => {
  // selectedSearch is used by EditSearchModal
  selectedSearch.value = { ...search, isNew: false }; // Treat as existing search
  showEditModal.value = true;
};

const handleEditComplete = () => {
  loadSavedSearches(); // Reload the list after edit
};

const openRequestModalForItem = (item) => {
  // Ensure the item has necessary details for the RequestModal
  selectedMediaForRequest.value = item; // Adapt if tmdb_id is named differently
  showRequestModal.value = true;
};

const parseJsonString = (jsonString) => {
  if (!jsonString || typeof jsonString !== 'string') {
    return [];
  }
  // Assuming networks might be a comma-delimited string or a JSON array string
  if (jsonString.startsWith('[') && jsonString.endsWith(']')) {
    try {
      return JSON.parse(jsonString);
    } catch (e) {
      // Fallback for malformed JSON array string, treat as comma-delimited
    }
  }
  return jsonString.split(',').map(s => s.trim()).filter(s => s.length > 0);
};
</script>

<template>
  <div ref="searchModalContentRef" class="flex flex-col relative h-full overflow-y-auto md:overflow-hidden">
    <form class="flex flex-col h-full"> <!-- Changed flex-grow to h-full -->
    <!-- Two-column layout for main content -->
    <div class="flex flex-col md:flex-row h-full"> <!-- Changed flex-grow to h-full -->
      <!-- Left Column: Form and Preview -->
      <div class="pl-6 md:pl-8 gap-6 w-full md:w-5/12 flex flex-col py-6 md:py-8 md:border-r md:border-gray-700 md:pr-6 md:h-full md:overflow-y-auto">
        <h2 class="text-white text-2xl md:text-3xl font-semibold">Search Movies & TV Shows</h2>
            <div>
                <label class="block text-gray-400 mb-2">Name</label>
                <input 
                    ref="searchNameInputRef"
                    v-model="searchName" 
                    type="text" 
                    placeholder="Give your search a name" 
                    class="w-full p-3 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 disabled:opacity-50 disabled:bg-gray-700 disabled:text-gray-400 disabled:border-gray-600 disabled:cursor-not-allowed"
                    :readonly="isCurrentSearchDefault"
                /> 
                </div>
            <div>
                <label class="block text-gray-400 mb-2">Prompt</label>
                <textarea
                ref="searchInput"
                v-model="searchText"
                type="text"
                placeholder="Describe the movies or TV shows you're looking for..."
                class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 min-h-[80px] resize-y"
                rows="5"
                required
                />
            </div>
            <!-- Template Variables Section -->
            <SearchOptions
                v-model:editableMediaName="editableMediaName"
                v-model:favoriteOption="favoriteOption"
            /> 

          <!-- Prompt Preview Section -->
          <div v-if="loadingPreview || previewError || previewResult" class="p-4 bg-gray-800 border border-gray-700 rounded-lg">
            <button
                type="button"
                @click="isPreviewExpanded = !isPreviewExpanded"
                class="w-full flex justify-between items-center text-left text-lg text-white font-semibold focus:outline-none hover:text-gray-300"
            >
                <span>Prompt Preview</span>
                <ChevronDown v-if="!isPreviewExpanded" :size="20" />
                <ChevronUp v-else :size="20" />
            </button>
            <transition name="fade">
                <div v-if="isPreviewExpanded">
                  <div v-if="loadingPreview" class="text-gray-400 pt-2">Generating preview...</div>
                  <div v-if="previewError" class="text-red-400 whitespace-pre-wrap pt-2">{{ previewError }}</div>
                  <pre v-if="previewResult && !previewError" class="text-gray-300 text-sm whitespace-pre-wrap overflow-x-auto max-h-60 pt-2">{{ previewResult }}</pre>
                </div>
            </transition>
          </div>

          <!-- Saved Search Section -->
          <div v-if="savedSearches.length > 0" class="mb-6">
          <div class="border border-gray-700 rounded-lg overflow-hidden bg-black">
              <h3 
              @click="toggleSearches"
              class="text-white text-xl p-4 flex items-center justify-between cursor-pointer hover:bg-gray-900">
              <span>Saved Searches</span>
              <button 
                  type="button"
                  class="text-gray-400 hover:text-white focus:outline-none"
                  title="Toggle saved searches"
              >
                  <ChevronUp v-if="isSearchesExpanded" :size="20"/>
                  <ChevronDown v-else :size="20"/>
              </button>
              </h3>
              <transition name="fade">
              <div v-if="isSearchesExpanded" class="border-t border-gray-700">
                  <div v-for="search in savedSearches" :key="search.id"
                      class="flex items-center justify-between p-4 hover:bg-gray-900 border-b border-gray-700 last:border-b-0"
                      :class="{ 'bg-gray-800/30': search.name === 'default' }"
                      :title="search.name === 'default' ? 'This is the default search and cannot be deleted.' : ''"
                  >
                      
                      <!-- Name, Prompt, and Date for Saved Search Item -->
                      <div class="flex-1 min-w-0 mx-3">
                          <div class="flex justify-between items-baseline">
                              <p class="text-md font-medium text-white truncate" :title="search.name || 'Unnamed Search'">
                              {{ search.name || 'Unnamed Search' }}
                              <span v-if="search.name === 'default'" class="ml-2 text-xs bg-sky-700 text-sky-200 px-1.5 py-0.5 rounded-full align-middle">Default</span>
                              </p>
                              <span v-if="search.last_run_date" title="Last Run Date" class="text-xs text-gray-500 hidden md:inline whitespace-nowrap flex-shrink-0">
                              {{ new Date(search.last_run_date).toLocaleString() }}
                              </span>
                          </div>
                          <p class="text-sm text-gray-400 truncate" :title="search.prompt">
                          {{ search.prompt }}
                          </p>
                      </div>

                      <!-- Action Buttons for Saved Search Item -->
                      <div class="flex items-center space-x-3 flex-shrink-0">
                          <div v-if="search.name === 'default'" class="p-1 text-gray-600 cursor-not-allowed" title="Default search cannot be deleted">
                              <Delete :size="20" />
                          </div>
                          <button
                            v-else
                            type="button"
                            @click="handleDelete(search.id)"
                            class="p-1 text-gray-400 hover:text-discovarr focus:outline-none rounded-full hover:bg-gray-800"
                            title="Delete this search"
                            >
                            <Delete :size="20" />
                          </button>
                          <button
                            type="button"
                            @click="openEditModalForSchedule(search)"
                            class="p-1 focus:outline-none rounded-full hover:bg-gray-800"
                            title="Edit search schedule"
                            >
                            <CalendarClock 
                                :size="20" 
                                :class="search.schedule?.enabled ? 'text-yellow-500' : 'text-gray-400'" 
                            />
                          </button>
                          <button 
                            type="button"
                            @click="rerunSearch(search)"
                            class="p-1 text-gray-400 hover:text-green-500 focus:outline-none rounded-full hover:bg-gray-800"
                            :title="'Run search: ' + (search.name || `Search #${search.id}`)"
                            >
                            <Run :size="20" />
                          </button>
                          <button 
                            type="button"
                            @click="handleEdit(search)"
                            class="p-1 text-gray-400 hover:text-yellow-500 focus:outline-none rounded-full hover:bg-gray-800"
                            :title="'Edit search #' + search.id"
                            >
                            <Edit :size="20" />
                          </button>
                      </div>
                  </div>
              </div>
              </transition>
              </div>
          </div>
          <!-- Form buttons -->
          <div class="flex gap-4 justify-end">
              <button
                type="button"
                @click="handleCancel"
                title="Clear the form and reset"
                class="px-6 py-2.5 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none"
              >
                Cancel
              </button>
              <button
              type="button"
              @click="handlePreview"
              title="Preview the rendered prompt"
              class="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="loadingPreview || !searchText"
              >
              {{ loadingPreview ? 'Previewing...' : 'Preview' }}
              </button>
              <button
              type="button"
              class="px-6 py-2.5 bg-discovarr text-white rounded-lg hover:opacity-90 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              @click="handleSubmit"
              :disabled="loading || !searchText || !initialLoadingDone"
              >
              {{ loading ? 'Searching...' : 'Search' }}
              </button>
              <button
              type="button"
              @click="handleSave"
              class="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="saving || !searchText || !initialLoadingDone"
              >
              {{ saving ? 'Saving...' : 'Save' }}
              </button>
          </div>
        </div>

      <!-- Right Column: Saved Searches and Results -->
      <div class="w-full md:w-7/12 flex flex-col md:h-full md:overflow-y-auto">
        <!-- Loading Indicator -->
        <div v-if="loading" class="flex flex-col justify-center items-center py-10 text-white">
        <svg class="animate-spin h-10 w-10 text-discovarr mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="text-lg">Loading...</p>
        </div>
        <!-- Search Results Section -->
        <div v-if="searchResults" class="space-y-4"> 
          <!-- Actual Results & Raw JSON Panel -->
          <div>
            <!-- Table Display for Search Results -->
            <div class="overflow-hidden border border-gray-700 shadow-md">
              <table class="min-w-full">
                <tbody class="bg-gray-800 divide-y divide-gray-700">
                  <template v-if="Array.isArray(searchResults) && searchResults.length > 0">
                    <tr v-for="(item, index) in searchResults" :key="item.tmdb_id || item.id || index">
                      <td class="p-4 align-top">
                        <div class="text-white font-medium mb-3">
                          <span :class="item.title ? 'text-white' : 'text-gray-500 italic'">{{ item.title || 'N/A' }}</span>
                        </div>
                        <div class="text-sm text-gray-300 space-y-3">
                          <div v-if="item.description">
                            <strong class="text-gray-200">Description:</strong> {{ item.description }}
                          </div>
                          <div v-if="item.similarity">
                            <strong class="text-gray-200">Similarity:</strong> {{ item.similarity }}
                          </div>
                          <!-- Inline Tag Display -->
                          <div class="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-2 text-xs">
                            <div v-if="item.media_type" class="inline-flex items-baseline">
                              <strong class="text-gray-400 font-medium mr-1.5">Type:</strong>
                              <span class="bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full">{{ (item.media_type || item.type || 'N/A').toUpperCase() }}</span>
                            </div>
                            <div v-if="item.rt_score" class="inline-flex items-baseline">
                              <strong class="text-gray-400 font-medium mr-1.5">Rotten Tomatoes:</strong>
                              <a v-if="item.rt_url" :href="item.rt_url" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:text-blue-300">
                              {{ item.rt_score }}%
                            </a>
                            <span v-else>{{ item.rt_score }}%</span>
                            </div>
                            <div v-if="item.release_date" class="inline-flex items-baseline">
                              <strong class="text-gray-400 font-medium mr-1.5">Released:</strong>
                              <span class="bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full">{{ new Date(item.release_date).toLocaleDateString() }}</span>
                            </div>
                            <div v-if="item.media_status" class="inline-flex items-baseline">
                              <strong class="text-gray-400 font-medium mr-1.5">Status:</strong>
                              <span class="bg-teal-700 text-teal-200 px-2 py-0.5 rounded-full">{{ item.media_status }}</span>
                            </div>
                            <div v-if="item.original_language" class="inline-flex items-baseline">
                              <strong class="text-gray-400 font-medium mr-1.5">Language:</strong>
                              <span class="bg-indigo-700 text-indigo-200 px-2 py-0.5 rounded-full">{{ item.original_language.toUpperCase() }}</span>
                            </div>
                            <div v-if="item.networks && ( (typeof item.networks === 'string' && item.networks.trim().length > 0) || (Array.isArray(item.networks) && item.networks.length > 0) )" 
                                class="inline-flex items-baseline flex-wrap">
                              <strong class="text-gray-400 font-medium mr-1.5 shrink-0">Networks:</strong>
                              <span 
                                v-for="network in (Array.isArray(item.networks) ? item.networks : parseJsonString(item.networks))" 
                                :key="network" 
                                class="bg-purple-700 text-purple-200 px-2 py-0.5 rounded-full mr-1 mb-1"
                              >
                                {{ network }}
                              </span>
                            </div>
                          </div>
                          <div v-if="!item.description && !item.similarity && !item.rt_score && !item.release_date && !item.media_status && !item.networks && !item.original_language" class="text-gray-500 italic mt-2">
                            No additional details available.
                          </div>
                          <!-- Request Button -->
                          <div class="flex justify-end mt-4">
                            <button
                              type="button"
                              @click="openRequestModalForItem(item)"
                              class="flex items-center px-4 py-2 bg-discovarr text-white text-sm rounded-lg hover:opacity-90 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                              :disabled="!item.tmdb_id" 
                            >
                              <Send :size="18" class="mr-2" /> Request
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </template>
                  <tr v-else-if="searchResults && searchResults.length === 0">
                    <td class="p-6 text-center text-gray-400">
                      No results found.
                    </td>
                  </tr>
                  <tr v-else-if="searchResults && !Array.isArray(searchResults)">
                    <td class="p-6 text-center text-gray-400">
                      Results are not in the expected list format. Toggle Raw JSON for details.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Collapsible Raw JSON Panel -->
            <div>
              <button
                type="button"
                @click="showRawJson = !showRawJson"
                class="m-4 px-3 py-1.5 text-xs bg-gray-700 text-white rounded-md hover:bg-gray-600 focus:outline-none flex items-center"
                      >
                {{ showRawJson ? 'Hide' : 'Show' }} Raw JSON
                <ChevronDown v-if="!showRawJson" class="ml-2" :size="18" />
                <ChevronUp v-if="showRawJson" class="ml-2" :size="18" />
              </button>
              <transition name="fade">
                <div v-if="showRawJson" class="mt-2 p-4 bg-gray-900 border border-gray-700 rounded-lg">
                  <pre class="text-gray-300 text-xs overflow-x-auto max-h-96">{{ JSON.stringify(searchResults, null, 2) }}</pre>
                </div>
              </transition>
            </div>
          </div>
        </div>
      </div>
    </div>

    <RequestModal
      v-model:show="showRequestModal"
      :media="selectedMediaForRequest"
      @close="showRequestModal = false"
      @request-complete="emit('refresh'); showRequestModal = false;" 
    />
    <!-- Modal for Editing Search Schedule -->
    <SearchScheduleModal
      v-if="showEditModal"
      :search-id="selectedSearch?.id"
      :prompt="selectedSearch?.prompt"
      :is-default-search="isCurrentSearchDefault"
      @close="showEditModal = false"
      @save="handleEditComplete"
    />
    </form>
  </div>
</template>

<style scoped>
/* Ensure smooth transitions for collapsible sections */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s;
}
.fade-enter, .fade-leave-to /* .fade-leave-active in <2.1.8 */ {
  opacity: 0;
}
</style>
