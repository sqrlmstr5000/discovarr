<script setup>
import { onMounted, onBeforeUnmount, ref, computed, inject, watch, nextTick } from 'vue'; // Added watch, nextTick
import MediaDetailsModal from '../components/MediaDetailsModal.vue';
// Removed MovieList import
import { useMovieStore } from '../stores/movie'
import { config } from '../config';
import RequestModal from '../components/RequestModal.vue'; // Added RequestModal import
import Send from 'vue-material-design-icons/Send.vue'; // Added icon imports
import MagnifyIcon from 'vue-material-design-icons/Magnify.vue';
import Edit from 'vue-material-design-icons/Pencil.vue';
import DeleteIcon from 'vue-material-design-icons/Delete.vue';
import PencilIcon from 'vue-material-design-icons/Pencil.vue';
import CheckIcon from 'vue-material-design-icons/Check.vue';
import CloseIcon from 'vue-material-design-icons/Close.vue';
import { useSettingsStore } from '@/stores/settings'; // Added settings store import
import { useRouter } from 'vue-router'; // Added router import

// No longer need props for activeMedia as it's managed internally
// const props = defineProps({
//   activeMedia: {
//     type: Array,
//     required: true
//   }
// })

// No longer need to emit refresh, will call internal refreshMedia
// const emit = defineEmits(['refresh'])

const settingsStore = useSettingsStore(); // Initialize settings store
const router = useRouter(); // Initialize router

const movieStore = useMovieStore()
const movie = computed(() => movieStore.currentMovie)
const isMobile = inject('isMobile');

// State from MovieList.vue
let activeMedia = ref([]);
const showRequestModal = ref(false);
const selectedMedia = ref(null);
const selectedItems = ref(new Set());
const showDetailsModal = ref(false);
const movieForModal = ref(null);
const isBulkProcessing = ref(false);

// Sorting state from MovieList.vue
const sortColumn = ref(null); // Initialize to null for no default sort
const sortDirection = ref(null); // Initialize to null

// Filter state from MovieList.vue
const filters = ref({
  source: [], // Changed to array for multi-select
  tmdb_id: '',
  title: '',
  type: '', // Keep as string for single select or text input
  release_date: '',
  networks: [], // Change to array for multi-select
  genres: [],   // Change to array for multi-select
  media_status: [], // Changed to array for multi-select
  original_language: [] // Changed to array for multi-select
});

// Watch for filter/sort changes to clear selection (from MovieList.vue)
watch(
  [
    () => filters.value.source,
    () => [...filters.value.source], // Watch for changes in array content
    () => filters.value.title,
    () => filters.value.tmdb_id,
    () => filters.value.type,
    () => filters.value.release_date, // Keep as is
    () => [...filters.value.networks], // Watch for changes in array content
    () => [...filters.value.genres],   // Watch for changes in array content
    () => [...filters.value.media_status], // Watch for changes in array content
    () => [...filters.value.original_language], // Watch for changes in array content
    sortColumn,
    sortDirection
  ],
  () => {
    selectedItems.value.clear();
  }
);

// Computed property for select all checkbox (from MovieList.vue)
const isAllSelected = computed(() => {
  const visibleItems = filteredAndSortedMedia.value;
  if (visibleItems.length === 0) return false;
  return visibleItems.every(item => selectedItems.value.has(item.id));
});

// Toggle item selection (from MovieList.vue)
const toggleSelectItem = (itemId) => {
  if (selectedItems.value.has(itemId)) {
    selectedItems.value.delete(itemId);
  } else {
    selectedItems.value.add(itemId);
  }
};

// Sort function (from MovieList.vue)
const sort = (column) => {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortColumn.value = column;
    sortDirection.value = 'asc';
  }
};

// Clear sort function
const clearSort = () => {
  sortColumn.value = null;
  sortDirection.value = null;
};

// Toggle select all (from MovieList.vue)
const toggleSelectAll = () => {
  const visibleItemIds = filteredAndSortedMedia.value.map(item => item.id);
  if (isAllSelected.value) {
    visibleItemIds.forEach(id => selectedItems.value.delete(id));
  } else {
    visibleItemIds.forEach(id => selectedItems.value.add(id));
  }
};

// Helper to parse comma-separated string to array of trimmed strings
const parseCommaSeparatedString = (str) => {
  if (!str || typeof str !== 'string') return [];
  return str.split(',').map(s => s.trim()).filter(s => s.length > 0);
};

// Computed property for filtered and sorted media (from MovieList.vue)
const filteredAndSortedMedia = computed(() => {
  // Use the local activeMedia ref instead of props.media
  let result = [...activeMedia.value];

  // Apply filters
  result = result.filter(item => {
    const itemNetworksArray = parseCommaSeparatedString(item.networks);
    const networkMatch = filters.value.networks.length === 0 || 
                         filters.value.networks.some(selectedNetwork => itemNetworksArray.includes(selectedNetwork));

    const itemGenresArray = parseCommaSeparatedString(item.genres);
    const genreMatch = filters.value.genres.length === 0 || 
                       filters.value.genres.some(selectedGenre => itemGenresArray.includes(selectedGenre));
    
    const itemSourceTitle = item.source_title || '';
    const sourceMatch = filters.value.source.length === 0 || 
                        filters.value.source.includes(itemSourceTitle);

    const itemMediaStatus = item.media_status || '';
    const mediaStatusMatch = filters.value.media_status.length === 0 || 
                             filters.value.media_status.includes(itemMediaStatus);

    const itemOriginalLanguage = item.original_language || '';
    const originalLanguageMatch = filters.value.original_language.length === 0 || 
                                  filters.value.original_language.includes(itemOriginalLanguage);

    return (
      !item.ignore && // Filter out ignored items
      sourceMatch && // Replaced old source filter
      (item.title || '').toLowerCase().includes(filters.value.title.toLowerCase()) &&
      (String(item.tmdb_id || '')).toLowerCase().includes(filters.value.tmdb_id.toLowerCase()) &&
      (item.media_type || '').toLowerCase().includes(filters.value.type.toLowerCase()) &&
      (item.release_date || '').toLowerCase().includes(filters.value.release_date.toLowerCase()) &&
      networkMatch &&
      genreMatch &&
      mediaStatusMatch && // Replaced old media_status filter
      originalLanguageMatch // Replaced old original_language filter
    );
  });

  // Apply sorting
  // Only sort if a sortColumn is defined
  if (sortColumn.value && sortDirection.value) {
    result.sort((a, b) => {
      const aVal = a[sortColumn.value];
      const bVal = b[sortColumn.value];

      // Handle null/undefined values
      if (!aVal && aVal !== 0) return sortDirection.value === 'asc' ? 1 : -1;
      if (!bVal && bVal !== 0) return sortDirection.value === 'asc' ? -1 : 1;

      // Handle numeric values (like imdb_score, rt_score)
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDirection.value === 'asc' ? aVal - bVal : bVal - aVal;
      }

      // Handle string values
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();

      if (sortDirection.value === 'asc') {
        return aStr.localeCompare(bStr);
      } else {
        return bStr.localeCompare(aStr);
      }
    });
  }
  
  return result;
});

const requesting = ref({}); // From MovieList.vue

// API helper to toggle ignore status (from MovieList.vue)
const toggleIgnore = async (mediaId) => {
  const response = await fetch(`${config.apiUrl}/media/${mediaId}/toggle-ignore`, {
    method: 'POST'
  });
  if (!response.ok) {
    let errorMsg = `Failed to toggle ignore status for media ID ${mediaId}. Status: ${response.status}`;
    try {
      const errorBody = await response.json(); // Or .text() if not always JSON
      errorMsg += ` - ${errorBody.message || JSON.stringify(errorBody)}`;
    } catch (e) {
      // Failed to parse error body, try text
      try {
        const errorText = await response.text();
        errorMsg += ` - ${errorText}`;
      } catch (textErr) {
        errorMsg += ` - Could not parse error response.`;
      }
    }
    throw new Error(errorMsg);
  }
  return response.json();
};

// Request media helper (from MovieList.vue)
const requestMediaForItem = async (item) => {
  if (!item || !item.tmdb_id || !item.media_type) {
    console.error('Invalid item for request:', item);
    throw new Error('Invalid media item for request.');
  }

  const requestPayload = {
    media_type: item.media_type,
    quality_profile_id: null, // For bulk, use default on backend by sending null
    save_default: false       // For bulk, don't save as default
  };

  const response = await fetch(
    `${config.apiUrl}/request/${item.tmdb_id}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestPayload)
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to request media ${item.title} (TMDB ID: ${item.tmdb_id}): ${response.status} - ${errorText}`);
  }
  return response.json();
};

// Delete media helper
const deleteMediaItem = async (mediaId) => {
  const response = await fetch(`${config.apiUrl}/media/${mediaId}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    throw new Error(`Failed to delete media ${mediaId}`);
  }
  return response.json();
};

// Handle toggle ignore 
const handleToggleIgnore = async (mediaId) => {
  try {
    await toggleIgnore(mediaId); // Call the API helper
  } catch (error) {
    console.error(`Error handling toggle ignore for ${mediaId}:`, error);
    alert(error.message || 'Failed to update ignore status. Please try again.'); // Inform the user about the error
  } finally {
    refreshMedia(); // Call local refresh function
  }
};

// Handle single delete 
const handleSingleDelete = async (mediaId) => {
  try {
    await deleteMediaItem(mediaId);
  } catch (error) {
    console.error(`Error deleting item ${mediaId}:`, error);
    alert(`Failed to delete item: ${error.message || 'Unknown error'}`); // Inform the user about the error
  } finally {
    refreshMedia(); // Call local refresh function
  }
};

// Handle bulk actions (from MovieList.vue)
const handleBulkAction = async (event) => {
  const action = event.target.value;
  if (!action || selectedItems.value.size === 0 || isBulkProcessing.value) {
    if (event && event.target) event.target.value = ''; // Reset dropdown if no action
    return;
  }

  isBulkProcessing.value = true;
  const itemsToProcess = Array.from(selectedItems.value);
  let promises = [];

  try {
    if (action === 'ignore') {
      promises = itemsToProcess.map(itemId => toggleIgnore(itemId));
    } else if (action === 'delete') {
      // Optional: Add a confirmation dialog here
      // if (!confirm(`Are you sure you want to delete ${itemsToProcess.length} items? This action cannot be undone.`)) {
      //   isBulkProcessing.value = false;
      //   if (event && event.target) event.target.value = '';
      //   return;
      // }
      promises = itemsToProcess.map(itemId => deleteMediaItem(itemId));
    } else if (action === 'request') {
      const mediaToRequest = [];
      for (const itemId of itemsToProcess) {
        const item = activeMedia.value.find(m => m.id === itemId); // Use local activeMedia
        if (item && item.tmdb_id && item.media_type && !item.requested) {
          mediaToRequest.push(item);
        }
      }
      if (mediaToRequest.length > 0) {
        promises = mediaToRequest.map(item => requestMediaForItem(item));
      } else {
        console.log("No items eligible for bulk request or all already requested.");
        // Potentially show a message to the user
      }
    }

    if (promises.length > 0) {
      await Promise.all(promises);
    }
  } catch (error) {
    console.error(`Error during bulk action "${action}":`, error);
    // Optionally show an error notification
  } finally {
    refreshMedia(); // Call local refresh function
    isBulkProcessing.value = false;
    selectedItems.value.clear();
    if (event && event.target) event.target.value = ''; // Reset dropdown
  }
};

// Open Movie Details Modal (from MovieList.vue)
const openMovieDetailsModal = (movie) => {
  movieForModal.value = movie;
  showDetailsModal.value = true;
};

// Close Movie Details Modal (from MovieList.vue)
const closeDetailsModal = () => {
  showDetailsModal.value = false;
  movieForModal.value = null;
};

// Select movie (opens modal) (from MovieList.vue)
const selectMovie = (movie, event) => {
  // Check if the click target or its parent is a button or link to prevent row selection
  let target = event.target;
  while (target && target !== event.currentTarget) {
    if (target.tagName === 'BUTTON' || target.tagName === 'A' || target.type === 'checkbox') {
      return; // Click was on an interactive element, don't select row
    }
    target = target.parentNode;
  }
  if (event.target.type !== 'checkbox') {
    openMovieDetailsModal(movie); // Open modal instead of emitting
  }
};

// Open Request Modal (from MovieList.vue)
const openRequestModal = (item) => {
  selectedMedia.value = item;
  showRequestModal.value = true;
};

// Navigate to Edit Saved Search (from MovieList.vue)
const navigateToEditSavedSearch = (searchId) => {
  if (searchId) {
    // Assuming 'search-view' is the name of the route that mounts SearchView.vue
    // and is configured to accept 'searchId' as a parameter.
    router.push({
      name: 'search-view',
      params: { searchId: String(searchId) } // Pass searchId as a route parameter
    });
  } else {
    console.warn('navigateToEditSavedSearch called without a searchId.');
  }
};

// Navigate to Search with Title (from MovieList.vue)
const navigateToSearch = (title) => {
  if (title) {
    const promptText = null;
    const mediaNameText = title; // Pass the title as media_name context
    router.push({
      name: 'search-view', // Use the route name for clarity
      query: {
        initialMediaName: mediaNameText
      }
    });
  }
};

const refreshMedia = async () => {
  await fetchActiveMedia();
};

const fetchActiveMedia = async () => {
  try {
    const activeResponse = await fetch(`${config.apiUrl}/media/active`);
    const activeData = await activeResponse.json();
    
    activeMedia.value = activeData; // Update the local ref
    
    // Set the first movie as the featured movie if on home page
    if (activeData.length > 0) {
      movieStore.setMovie(activeData[0]);
    }
  } catch (error) {
    console.error('Failed to fetch active media:', error);
  }
};

const availableNetworks = ref([]);
const availableGenres = ref([]);
const availableSources = ref([]);
const availableMediaStatuses = ref([]);
const availableOriginalLanguages = ref([]);

// For custom multi-select dropdowns
const networkDropdownActive = ref(false);
const genreDropdownActive = ref(false);
const sourceDropdownActive = ref(false);
const mediaStatusDropdownActive = ref(false);
const originalLanguageDropdownActive = ref(false);

const networkFilterButtonRef = ref(null);
const networkDropdownRef = ref(null);
const genreFilterButtonRef = ref(null);
const genreDropdownRef = ref(null);
const sourceFilterButtonRef = ref(null);
const sourceDropdownRef = ref(null);
const mediaStatusFilterButtonRef = ref(null);
const mediaStatusDropdownRef = ref(null);
const originalLanguageFilterButtonRef = ref(null);
const originalLanguageDropdownRef = ref(null);

const fetchUniqueFieldValues = async (fieldName, targetRef) => {
  try {
    const response = await fetch(`${config.apiUrl}/media/field/${fieldName}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch unique ${fieldName}`);
    }
    targetRef.value = await response.json();
  } catch (error) {
    console.error(`Error fetching unique ${fieldName}:`, error);
    // Optionally show a toast or error message to the user
  }
};

const handleClickOutside = (event) => {
  if (networkDropdownActive.value && networkFilterButtonRef.value && !networkFilterButtonRef.value.contains(event.target) && networkDropdownRef.value && !networkDropdownRef.value.contains(event.target)) {
    networkDropdownActive.value = false;
  }
  if (genreDropdownActive.value && genreFilterButtonRef.value && !genreFilterButtonRef.value.contains(event.target) && genreDropdownRef.value && !genreDropdownRef.value.contains(event.target)) {
    genreDropdownActive.value = false;
  }
  if (sourceDropdownActive.value && sourceFilterButtonRef.value && !sourceFilterButtonRef.value.contains(event.target) && sourceDropdownRef.value && !sourceDropdownRef.value.contains(event.target)) {
    sourceDropdownActive.value = false;
  }
  if (mediaStatusDropdownActive.value && mediaStatusFilterButtonRef.value && !mediaStatusFilterButtonRef.value.contains(event.target) && mediaStatusDropdownRef.value && !mediaStatusDropdownRef.value.contains(event.target)) {
    mediaStatusDropdownActive.value = false;
  }
  if (originalLanguageDropdownActive.value && originalLanguageFilterButtonRef.value && !originalLanguageFilterButtonRef.value.contains(event.target) && originalLanguageDropdownRef.value && !originalLanguageDropdownRef.value.contains(event.target)) {
    originalLanguageDropdownActive.value = false;
  }
};

onMounted(async () => {
  await fetchActiveMedia();
  await fetchUniqueFieldValues('networks', availableNetworks);
  await fetchUniqueFieldValues('genres', availableGenres);
  await fetchUniqueFieldValues('source_title', availableSources);
  await fetchUniqueFieldValues('media_status', availableMediaStatuses);
  await fetchUniqueFieldValues('original_language', availableOriginalLanguages);
  document.addEventListener('mousedown', handleClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleClickOutside);
});

const toggleNetworkDropdown = () => {
  networkDropdownActive.value = !networkDropdownActive.value;
  if (networkDropdownActive.value) {
    genreDropdownActive.value = false; 
    sourceDropdownActive.value = false;
    mediaStatusDropdownActive.value = false;
    originalLanguageDropdownActive.value = false;
  }
};

const toggleGenreDropdown = () => {
  genreDropdownActive.value = !genreDropdownActive.value;
  if (genreDropdownActive.value) {
    networkDropdownActive.value = false;
    sourceDropdownActive.value = false;
    mediaStatusDropdownActive.value = false;
    originalLanguageDropdownActive.value = false;
  }
};

const toggleSourceDropdown = () => {
  sourceDropdownActive.value = !sourceDropdownActive.value;
  if (sourceDropdownActive.value) { networkDropdownActive.value = false; genreDropdownActive.value = false; mediaStatusDropdownActive.value = false; originalLanguageDropdownActive.value = false; }
};

const toggleMediaStatusDropdown = () => {
  mediaStatusDropdownActive.value = !mediaStatusDropdownActive.value;
  if (mediaStatusDropdownActive.value) { networkDropdownActive.value = false; genreDropdownActive.value = false; sourceDropdownActive.value = false; originalLanguageDropdownActive.value = false; }
};

const toggleOriginalLanguageDropdown = () => {
  originalLanguageDropdownActive.value = !originalLanguageDropdownActive.value;
  if (originalLanguageDropdownActive.value) { networkDropdownActive.value = false; genreDropdownActive.value = false; sourceDropdownActive.value = false; mediaStatusDropdownActive.value = false; }
};

const selectedNetworksText = computed(() => filters.value.networks.length > 0 ? filters.value.networks.join(', ') : 'Networks');
const selectedGenresText = computed(() => filters.value.genres.length > 0 ? filters.value.genres.join(', ') : 'Genres');
const selectedSourcesText = computed(() => filters.value.source.length > 0 ? filters.value.source.join(', ') : 'Sources');
const selectedMediaStatusesText = computed(() => filters.value.media_status.length > 0 ? filters.value.media_status.join(', ') : 'Statuses');
const selectedOriginalLanguagesText = computed(() => filters.value.original_language.length > 0 ? filters.value.original_language.join(', ') : 'Languages');

const selectAllNetworks = () => {
  filters.value.networks = [...availableNetworks.value];
};
const clearNetworks = () => {
  filters.value.networks = [];
};

const selectAllGenres = () => {
  filters.value.genres = [...availableGenres.value];
};
const clearGenres = () => {
  filters.value.genres = [];
};

const selectAllSources = () => {
  filters.value.source = [...availableSources.value];
};
const clearSources = () => {
  filters.value.source = [];
};

const selectAllMediaStatuses = () => {
  filters.value.media_status = [...availableMediaStatuses.value];
};
const clearMediaStatuses = () => {
  filters.value.media_status = [];
};

const selectAllOriginalLanguages = () => {
  filters.value.original_language = [...availableOriginalLanguages.value];
};
const clearOriginalLanguages = () => {
  filters.value.original_language = [];
};


// This logic should ideally be inside onMounted or a watcher
// to ensure activeMedia has been fetched. Moving to onMounted.
// if (activeMedia.length > 0 && !movieStore.currentMovie) {
//   selectMovie(activeMedia[0])
// }

// Watch for filter changes to clear selection
watch(filters, () => {
    selectedItems.value.clear();
}, { deep: true }); // Use deep watch since filters is an object


// Helper function to clear a specific filter
const clearFilter = (filterKey) => {
  if (filters.value.hasOwnProperty(filterKey)) {
    if (Array.isArray(filters.value[filterKey])) {
      filters.value[filterKey] = [];
    } else {
      // Assuming all non-array filters are strings
      filters.value[filterKey] = '';
    }
    // For multi-selects, ensure dropdowns are closed if they were part of the clear action
    if (filterKey === 'networks') networkDropdownActive.value = false;
    if (filterKey === 'genres') genreDropdownActive.value = false;
    if (filterKey === 'source') sourceDropdownActive.value = false;
    if (filterKey === 'media_status') mediaStatusDropdownActive.value = false;
    if (filterKey === 'original_language') originalLanguageDropdownActive.value = false;
  }
};
</script>

<template>
<div class="h-full flex flex-col"> <!-- Root div: h-full for height constraint, flex flex-col for layout -->
  <!-- Scrollable area for the table -->
  <div class="flex-grow overflow-y-auto overflow-x-auto px-1 sm:px-4">
      <table class="min-w-full bg-black text-white">
        <!-- Sorting Row -->
        <thead class="text-xs py-2">
          <tr class="border-b border-gray-700">
          <th class="px-3 py-2 text-center text-gray-400 uppercase tracking-wider">
              <input
                type="checkbox"
                :checked="isAllSelected"
                @change="toggleSelectAll"
                :disabled="filteredAndSortedMedia.length === 0"
              class="w-5 h-5 cursor-pointer bg-gray-800 border-gray-600 rounded focus:ring-discovarr"
                title="Select/Deselect all visible"
              />
            </th>
          <th class="px-3 py-2 text-center text-gray-400 uppercase tracking-wider">Request</th>
            <th
            class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('title')"
            >
              Title
              <span v-if="sortColumn === 'title'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
            class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800" @click="sort('media_type')"
            >
              Type
              <span v-if="sortColumn === 'media_type'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
            class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('rt_score')"
            >
              RT
              <span v-if="sortColumn === 'rt_score'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
              class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('release_date')"
            >
              Release Date
              <span v-if="sortColumn === 'release_date'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
              class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('networks')"
            >
              Networks
              <span v-if="sortColumn === 'networks'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
              class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('genres')"
            >
              Genres
              <span v-if="sortColumn === 'genres'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
            class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('source_title')"
            >
              Source Title
              <span v-if="sortColumn === 'source_title'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
              class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('media_status')"
            >
              Status
              <span v-if="sortColumn === 'media_status'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
            <th
              class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-800"
              @click="sort('original_language')"
            >
              Language
              <span v-if="sortColumn === 'original_language'" class="ml-1 inline-flex items-center">
                {{ sortDirection === 'asc' ? '↑' : '↓' }}
                <button @click.stop="clearSort" title="Clear sort" class="ml-1 p-0.5 text-gray-500 hover:text-white focus:outline-none rounded-full hover:bg-gray-700">
                  <CloseIcon :size="14" />
                </button>
              </span>
            </th>
          <th class="px-3 py-2 text-left text-gray-400 uppercase tracking-wider">Search</th>
          <th class="px-3 py-2 text-center text-gray-400 uppercase tracking-wider">Ignore</th>
          <th class="px-3 py-2 text-center text-gray-400 uppercase tracking-wider">Delete</th>
          </tr>
        </thead>
        <!-- Filter Row -->
        <!-- Separate tbody for filter row to keep it outside the transition-group -->
        <tbody class="bg-gray-800/50">
          <tr class="border-b border-gray-700">
            <td class="px-3 py-2"></td> <!-- Cell for Select All checkbox column -->
            <td class="px-3 py-2"></td> <!-- Request column -->
            <td class="px-3 py-2">
              <div class="relative">
                <input
                  v-model="filters.title"
                  placeholder="Filter title..."
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr placeholder-gray-500"
                />
                <button
                  v-if="filters.title"
                  @click="clearFilter('title')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none"
                  title="Clear title filter"
                >
                  <CloseIcon :size="18" />
                </button>
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="relative">
                <input
                  type="text"
                  v-model="filters.type"
                  placeholder="Filter type..."
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr placeholder-gray-500"
                />
                <button
                  v-if="filters.type"
                  @click="clearFilter('type')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none"
                  title="Clear type filter"
                >
                  <CloseIcon :size="18" />
                </button>
              </div>
            </td>
            <td class="px-3 py-2"></td> <!-- RT column -->
            <td class="px-3 py-2">
              <div class="relative">
                <input
                  v-model="filters.release_date"
                  placeholder="Filter date..."
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr placeholder-gray-500"
                />
                <button
                  v-if="filters.release_date"
                  @click="clearFilter('release_date')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none"
                  title="Clear release date filter"
                >
                  <CloseIcon :size="18" />
                </button>
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="relative">
                <button 
                  ref="networkFilterButtonRef"
                  type="button" 
                  @click="toggleNetworkDropdown" 
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr text-left truncate"
                  :title="selectedNetworksText"
                >
                  {{ selectedNetworksText }}
                </button>
                <button
                  v-if="filters.networks.length > 0"
                  @click.stop="clearFilter('networks')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none z-10"
                  title="Clear selected networks"
                >
                  <CloseIcon :size="18" />
                </button>
                <div v-if="networkDropdownActive" ref="networkDropdownRef" class="absolute z-20 mt-1 w-full bg-gray-800 border border-gray-700 rounded-md shadow-lg py-1">
                  <div class="flex justify-between px-3 py-1 border-b border-gray-700">
                    <button @click.stop="selectAllNetworks" type="button" class="text-xs text-blue-400 hover:text-blue-300">Select All</button>
                    <button @click.stop="clearNetworks" type="button" class="text-xs text-red-400 hover:text-red-300">Clear</button>
                  </div>
                  <div class="max-h-52 overflow-y-auto">
                    <label v-for="network in availableNetworks" :key="network" class="flex items-center px-3 py-1.5 text-sm text-white hover:bg-gray-700 cursor-pointer">
                      <input type="checkbox" :value="network" v-model="filters.networks" class="mr-2 accent-discovarr">
                      {{ network }}
                    </label>
                    <div v-if="availableNetworks.length === 0" class="px-3 py-1.5 text-sm text-gray-500">No networks available</div>
                  </div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="relative">
                <button 
                  ref="genreFilterButtonRef"
                  type="button" 
                  @click="toggleGenreDropdown" 
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr text-left truncate"
                  :title="selectedGenresText"
                >
                  {{ selectedGenresText }}
                </button>
                <button
                  v-if="filters.genres.length > 0"
                  @click.stop="clearFilter('genres')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none z-10"
                  title="Clear selected genres"
                >
                  <CloseIcon :size="18" />
                </button>
                <div v-if="genreDropdownActive" ref="genreDropdownRef" class="absolute z-20 mt-1 w-full bg-gray-800 border border-gray-700 rounded-md shadow-lg py-1">
                  <div class="flex justify-between px-3 py-1 border-b border-gray-700">
                    <button @click.stop="selectAllGenres" type="button" class="text-xs text-blue-400 hover:text-blue-300">Select All</button>
                    <button @click.stop="clearGenres" type="button" class="text-xs text-red-400 hover:text-red-300">Clear</button>
                  </div>
                  <div class="max-h-52 overflow-y-auto">
                    <label v-for="genre in availableGenres" :key="genre" class="flex items-center px-3 py-1.5 text-sm text-white hover:bg-gray-700 cursor-pointer">
                      <input type="checkbox" :value="genre" v-model="filters.genres" class="mr-2 accent-discovarr">
                      {{ genre }}
                    </label>
                    <div v-if="availableGenres.length === 0" class="px-3 py-1.5 text-sm text-gray-500">No genres available</div>
                  </div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="relative"> <!-- Source Filter -->
                <button
                  ref="sourceFilterButtonRef"
                  type="button"
                  @click="toggleSourceDropdown"
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr text-left truncate"
                  :title="selectedSourcesText"
                >
                  {{ selectedSourcesText }}
                </button>
                <button
                  v-if="filters.source.length > 0"
                  @click="clearFilter('source')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none z-10"
                  title="Clear source filter"
                >
                  <CloseIcon :size="18" />
                </button>
                <div v-if="sourceDropdownActive" ref="sourceDropdownRef" class="absolute z-20 mt-1 w-full bg-gray-800 border border-gray-700 rounded-md shadow-lg py-1">
                  <div class="flex justify-between px-3 py-1 border-b border-gray-700">
                    <button @click.stop="selectAllSources" type="button" class="text-xs text-blue-400 hover:text-blue-300">Select All</button>
                    <button @click.stop="clearSources" type="button" class="text-xs text-red-400 hover:text-red-300">Clear</button>
                  </div>
                  <div class="max-h-52 overflow-y-auto">
                    <label v-for="sourceItem in availableSources" :key="sourceItem" class="flex items-center px-3 py-1.5 text-sm text-white hover:bg-gray-700 cursor-pointer">
                      <input type="checkbox" :value="sourceItem" v-model="filters.source" class="mr-2 accent-discovarr">
                      {{ sourceItem }}
                    </label>
                    <div v-if="availableSources.length === 0" class="px-3 py-1.5 text-sm text-gray-500">No sources available</div>
                  </div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="relative"> <!-- Media Status Filter -->
                <button
                  ref="mediaStatusFilterButtonRef"
                  type="button"
                  @click="toggleMediaStatusDropdown"
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr text-left truncate"
                  :title="selectedMediaStatusesText"
                >
                  {{ selectedMediaStatusesText }}
                </button>
                <button
                  v-if="filters.media_status.length > 0"
                  @click="clearFilter('media_status')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none z-10"
                  title="Clear status filter"
                >
                  <CloseIcon :size="18" />
                </button>
                <div v-if="mediaStatusDropdownActive" ref="mediaStatusDropdownRef" class="absolute z-20 mt-1 w-full bg-gray-800 border border-gray-700 rounded-md shadow-lg py-1">
                  <div class="flex justify-between px-3 py-1 border-b border-gray-700">
                    <button @click.stop="selectAllMediaStatuses" type="button" class="text-xs text-blue-400 hover:text-blue-300">Select All</button>
                    <button @click.stop="clearMediaStatuses" type="button" class="text-xs text-red-400 hover:text-red-300">Clear</button>
                  </div>
                  <div class="max-h-52 overflow-y-auto">
                    <label v-for="statusItem in availableMediaStatuses" :key="statusItem" class="flex items-center px-3 py-1.5 text-sm text-white hover:bg-gray-700 cursor-pointer">
                      <input type="checkbox" :value="statusItem" v-model="filters.media_status" class="mr-2 accent-discovarr">
                      {{ statusItem }}
                    </label>
                    <div v-if="availableMediaStatuses.length === 0" class="px-3 py-1.5 text-sm text-gray-500">No statuses available</div>
                  </div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="relative"> <!-- Original Language Filter -->
                <button
                  ref="originalLanguageFilterButtonRef"
                  type="button"
                  @click="toggleOriginalLanguageDropdown"
                  class="w-full pl-3 pr-8 py-1.5 bg-gray-900 text-white border border-gray-700 rounded-md text-sm focus:ring-discovarr focus:border-discovarr text-left truncate"
                  :title="selectedOriginalLanguagesText"
                >
                  {{ selectedOriginalLanguagesText }}
                </button>
                <button
                  v-if="filters.original_language.length > 0"
                  @click="clearFilter('original_language')"
                  type="button"
                  class="absolute inset-y-0 right-0 flex items-center justify-center w-8 h-full text-gray-500 hover:text-white focus:outline-none z-10"
                  title="Clear language filter"
                >
                  <CloseIcon :size="18" />
                </button>
                <div v-if="originalLanguageDropdownActive" ref="originalLanguageDropdownRef" class="absolute z-20 mt-1 w-full bg-gray-800 border border-gray-700 rounded-md shadow-lg py-1">
                  <div class="flex justify-between px-3 py-1 border-b border-gray-700">
                    <button @click.stop="selectAllOriginalLanguages" type="button" class="text-xs text-blue-400 hover:text-blue-300">Select All</button>
                    <button @click.stop="clearOriginalLanguages" type="button" class="text-xs text-red-400 hover:text-red-300">Clear</button>
                  </div>
                  <div class="max-h-52 overflow-y-auto">
                    <label v-for="langItem in availableOriginalLanguages" :key="langItem" class="flex items-center px-3 py-1.5 text-sm text-white hover:bg-gray-700 cursor-pointer">
                      <input type="checkbox" :value="langItem" v-model="filters.original_language" class="mr-2 accent-discovarr">
                      {{ langItem }}
                    </label>
                    <div v-if="availableOriginalLanguages.length === 0" class="px-3 py-1.5 text-sm text-gray-500">No languages available</div>
                  </div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2"></td> <!-- Search column -->
            <td class="px-3 py-2"></td> <!-- Ignore column -->
            <td class="px-3 py-2"></td> <!-- Delete column -->
          </tr>
        </tbody>
        <!-- Data Row -->
        <transition-group tag="tbody" name="list-item-row">
          <tr
            v-for="item in filteredAndSortedMedia"
            :key="item.id"
            class="border-b border-gray-700 hover:bg-gray-900 cursor-pointer text-sm"
            @click="selectMovie(item, $event)">
              <td class="px-3 py-2 text-center">
                <input
                  type="checkbox"
                  :checked="selectedItems.has(item.id)"
                  @change="toggleSelectItem(item.id)"
                  @click.stop
                  class="w-5 h-5 cursor-pointer"/>
              </td>

              <td class="px-3 py-2 text-center">
                  <button
                    @click.stop="openRequestModal(item)"
                    class="p-2 text-white rounded-full hover:bg-gray-800 disabled:opacity-50 disabled:hover:bg-transparent"
                    :disabled="item.requested"
                    :title="item.requested ? 'Already Requested' : 'Request Media'"
                  >
                    <Send :class="item.requested ? 'text-gray-600' : 'text-discovarr'" />
                  </button>
              </td>
              <td class="px-3 py-2">
                <div class="flex items-center">
                  <span
                    class="block truncate w-[250px]"
                    :title="item.title"
                  >{{ item.title }}</span>
                  <button
                    @click.stop="navigateToSearch(item.title)"
                    class="ml-2 p-0.5 text-gray-400 hover:text-discovarr focus:outline-none rounded-full hover:bg-gray-800"
                    title="Search this title"
                  >
                    <MagnifyIcon :size="18" />
                  </button>
                </div>
              </td>
              <td class="px-3 py-2">
                  <span class="ml-2 text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full">{{ item.media_type?.toUpperCase() }}</span>
              </td>
              <td class="px-3 py-2"><a
                  v-if="item.rt_url"
                  :href="item.rt_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-blue-400 hover:text-blue-300"
                  @click.stop
                >{{ item.rt_score }}</a>
                <div v-if="!item.rt_url">{{ item.rt_score }}</div></td>
              <td class="px-3 py-2 whitespace-nowrap">{{ item.release_date }}</td>
              <td class="px-3 py-2"><div class="w-[150px] truncate" :title="item.networks">{{ item.networks }}</div></td>
              <td class="px-3 py-2"><div class="w-[150px] truncate" :title="item.genres">{{ item.genres }}</div></td>
              <td class="px-3 py-2"><div class="w-[200px] truncate" :title="item.source_title">{{ item.source_title }}</div></td>
              <td class="px-3 py-2 whitespace-nowrap">{{ item.media_status }}</td>
              <td class="px-3 py-2 whitespace-nowrap text-center">{{ item.original_language }}</td>
              <td class="px-3 py-2 text-center">
                <button
                  v-if="item.search"
                  @click.stop="navigateToEditSavedSearch(item.search.id)"
                  class="text-discovarr hover:opacity-80 focus:outline-none"
                  :title="'Edit Search ' + item.search.id"
                >
                  <Edit :size="24" />
                </button>
              </td>
              <td class="px-3 py-2 text-center">
                  <input
                  type="checkbox"
                  :checked="item.ignore"
                  @change.stop="handleToggleIgnore(item.id)"
                  class="w-5 h-5 cursor-pointer"
                  >
              </td>
              <td class="px-3 py-2 text-center">
                <button
                  @click.stop="handleSingleDelete(item.id)"
                  class="p-1 text-gray-400 hover:text-discovarr focus:outline-none"
                  title="Delete Media"
                >
                  <DeleteIcon :size="20" />
                </button>
              </td>
          </tr>
        </transition-group>
        <!-- Separate tbody for "No media found" message -->
        <tbody v-if="filteredAndSortedMedia.length === 0">
          <tr>
            <td :colspan="15" class="text-center py-10 text-gray-500">
              <div class="text-lg">No media found.</div>
              <p v-if="activeMedia.length > 0" class="text-sm">Try adjusting your filters.</p> <!-- Use local activeMedia -->
              <p v-else class="text-sm">There is no media to display.</p>
            </td>
          </tr>
        </tbody>
      </table>
  </div>

  <!-- Bulk Actions Bar -->
  <div
    v-if="selectedItems.size > 0"
    class="flex-shrink-0 p-3 bg-gray-800 border-t border-gray-700 flex items-center space-x-3 z-20 px-1 sm:px-4"
  >
    <span class="text-gray-300 text-sm">{{ selectedItems.size }} item(s) selected</span>
    <div class="relative">
      <select
        @change="handleBulkAction"
        :disabled="isBulkProcessing"
        class="pl-3 pr-8 py-2 bg-gray-700 text-white rounded-md border border-gray-600 focus:outline-none focus:border-discovarr focus:ring-1 focus:ring-discovarr appearance-none text-sm"
      >
        <option value="">Actions...</option>
        <option value="ignore">Toggle Ignore</option>
        <option value="delete">Delete</option>
        <option value="request">Request</option>
      </select>
      <!-- You might want a chevron icon for the select dropdown here -->
    </div>
    <span v-if="isBulkProcessing" class="text-discovarr text-sm animate-pulse">Processing...</span>
  </div>

    <RequestModal
      v-model:show="showRequestModal"
      :media="selectedMedia"
      @close="showRequestModal = false"
      @request-complete="refreshMedia" 
    />


    <!-- Movie Details Modal -->
    <Teleport to="body">
      <div v-if="showDetailsModal"
            class="fixed inset-0 bg-black bg-opacity-80 z-50 flex items-center justify-center p-2 sm:p-4"
            @click.self="closeDetailsModal">
        <div class="relative bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl lg:max-w-4xl max-h-[90vh] flex flex-col">
          <button @click="closeDetailsModal" class="absolute top-2 right-2 text-gray-400 hover:text-white p-1 rounded-full hover:bg-gray-700/80 z-10">
            <CloseIcon :size="28" />
          </button>
          <div class="overflow-y-auto flex-grow modal-content-scrollable">
            <!-- Listen for tmdb-id-updated from MovieDetails -->
            <MediaDetailsModal :movie="movieForModal" @close="closeDetailsModal" @tmdb-id-updated="refreshMedia" />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* Styles from MovieList.vue */
.list-item-row-leave-active {
  transition: opacity 0.5s ease;
}
.list-item-row-leave-to {
  opacity: 0;
}

.modal-content-scrollable {
  /* Ensures that the MovieDetails component's own padding is respected */
  /* and the scrollbar appears correctly if content overflows. */
}
</style>