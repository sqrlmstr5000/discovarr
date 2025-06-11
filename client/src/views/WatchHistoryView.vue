<script setup>
import { ref, onMounted } from 'vue';
import { config } from '../config';
import VideoCarousel from '@/components/VideoCarousel.vue';
import SyncIcon from 'vue-material-design-icons/Sync.vue'; // For the sync button
import { useToastStore } from '@/stores/toast'; // For notifications

const groupedHistory = ref([]);
const loading = ref(true);
const error = ref(null);
const isSyncing = ref(false); // For the sync button
const isDeletingAll = ref(false); // For the delete all button

const toastStore = useToastStore(); // For notifications

const fetchGroupedWatchHistory = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`${config.apiUrl}/watch-history/grouped`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    groupedHistory.value = await response.json();
  } catch (e) {
    console.error(e);
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};

const handleSync = async () => {
  isSyncing.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/sync_watch_history`); 
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    // const result = await response.json(); // You can process result if needed
    toastStore.show('Watch history sync initiated successfully!', 'success');
    fetchGroupedWatchHistory(); // Refresh the list directly
  } catch (error) {
    console.error('Failed to sync watch history:', error);
    toastStore.show(`Failed to sync watch history: ${error.message}`, 'error');
  } finally {
    isSyncing.value = false;
  }
};

const handleDeleteHistoryItem = async (historyItemId) => {
  if (!historyItemId) {
    toastStore.show('Invalid history item ID for deletion.', 'error');
    return;
  }
  try {
    const response = await fetch(`${config.apiUrl}/watch-history/${historyItemId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `Failed to delete history item. Status: ${response.status}` }));
      throw new Error(errorData.detail);
    }
    toastStore.show('Watch history item deleted successfully!', 'success');
    fetchGroupedWatchHistory(); // Refresh the list
  } catch (error) {
    console.error('Failed to delete watch history item:', error);
    toastStore.show(`Error deleting history item: ${error.message}`, 'error');
  }
};

const handleDeleteAllHistory = async () => {
  if (!window.confirm('Are you sure you want to delete ALL watch history? This action cannot be undone.')) {
    return;
  }

  isDeletingAll.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/watch-history/all`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `Failed to delete all history. Status: ${response.status}` }));
      throw new Error(errorData.detail);
    }
    toastStore.show('All watch history deleted successfully!', 'success');
    fetchGroupedWatchHistory(); // Refresh the list
  } catch (error) {
    console.error('Failed to delete all watch history:', error);
    toastStore.show(`Error deleting all history: ${error.message}`, 'error');
  } finally {
    isDeletingAll.value = false;
  }
};

onMounted(fetchGroupedWatchHistory);
</script>
<template>
  <div class="relative p-6 md:p-8 text-white overflow-x-hidden h-full overflow-y-auto">
    <div class="flex justify-between items-center mb-8">
      <h2 class="text-2xl md:text-3xl font-semibold text-center sm:text-left">Watch History</h2>

      <div class="flex items-center space-x-3">
        <!-- Delete All Watch History Button -->
        <button
          @click="handleDeleteAllHistory"
          :disabled="isDeletingAll"
          class="p-2 sm:p-3 bg-red-600 text-white rounded-full shadow-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-75 transition-colors duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
          title="Delete All Watch History"
        >
          <!-- Using a simple trash icon, replace with vue-material-design-icons if available and preferred -->
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
        <!-- Sync Watch History Button -->
        <button
          @click="handleSync"
          :disabled="isSyncing"
          class="p-2 sm:p-3 bg-discovarr text-white rounded-full shadow-lg hover:bg-discovarr-dark focus:outline-none focus:ring-2 focus:ring-discovarr-light focus:ring-opacity-75 transition-colors duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
          title="Sync Watch History"
        >
          <SyncIcon :class="{ 'animate-spin': isSyncing }" :size="24" />
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-20 text-gray-400">
      <svg class="animate-spin h-12 w-12 text-discovarr mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-xl font-medium">Loading watch history...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-20 text-red-400">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <p class="text-xl font-semibold">Oops! Something went wrong.</p>
      <p class="text-md text-red-300 mt-1">Failed to load watch history: {{ error }}</p>
    </div>

    <!-- Main Content: Watch History Carousels -->
    <div v-else-if="groupedHistory && groupedHistory.length > 0">
      <div v-for="userHistory in groupedHistory" :key="userHistory.user" class="mb-10">
        <!--
          The VideoCarousel component expects 'movies' prop.
          The items in userHistory.history are from the WatchHistory model,
          which primarily contain 'id', 'title', 'watched_by', 'watched_at'.
          VideoCarousel might need richer objects (e.g., with poster_url).
          If VideoCarousel cannot display these items adequately, it may need
          to be adapted, or this component/backend would need to fetch fuller media details.
          For now, we assume VideoCarousel can handle these items or this is a first step.
        -->
        <VideoCarousel
          :category="`${userHistory.user}`"
          :historyItems="userHistory.history"
          @delete-history-item="handleDeleteHistoryItem"
        />
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="flex flex-col items-center justify-center py-20 text-gray-500">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p class="text-xl font-semibold">No Watch History Found</p>
      <p class="text-md text-gray-400 mt-1">Looks like there's nothing here yet. Start watching some media!</p>
    </div>

  </div>
</template>


