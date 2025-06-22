<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router';
import { useToastStore } from '@/stores/toast'; // Import the toast store
import { config } from '../config'

const settings = ref(null)
const radarrQualityProfiles = ref([])
const loadingRadarrProfiles = ref(false)
const sonarrQualityProfiles = ref([])
const loadingSonarrProfiles = ref(false)
const jellyseerrUsers = ref([]);
const loadingJellyseerrUsers = ref(false);
const overseerrUsers = ref([]);
const loadingOverseerrUsers = ref(false);
const llmModels = ref({}); // Will store models keyed by provider name
const loadingLlmModels = ref(false);
const tokenUsageSummary = ref(null)
const users = ref([]);
const loadingUsers = ref(false);
const loadingTokenUsage = ref(false)
const showTraktAuthModal = ref(false);
const traktAuthDetails = ref({ user_code: '', verification_url: '' });
const traktAuthLoading = ref(false);
const traktAuthError = ref('');
const tokenUsageError = ref(null)

const selectedRange = ref('all_time');
const startDate = ref('');
const endDate = ref('');

let originalValues = {}
const toastStore = useToastStore(); // Initialize the toast store
const route = useRoute();

const applicationSettings = computed(() => {
  if (!settings.value) return {};
  return Object.entries(settings.value)
    .filter(([, groupDetails]) => {
      const baseProvider = groupDetails.base_provider?.value;
      return !(baseProvider === 'library' || baseProvider === 'llm' || baseProvider === 'request');
    })
    .reduce((obj, [key, value]) => ({ ...obj, [key]: value }), {});
});

const libraryProviderSettings = computed(() => {
  if (!settings.value) return {};
  return Object.entries(settings.value)
    .filter(([, groupDetails]) => {
      const baseProvider = groupDetails.base_provider?.value;
      return baseProvider === 'library';
    })
    .reduce((obj, [key, value]) => ({ ...obj, [key]: value }), {});
});

const llmProviderSettings = computed(() => {
  if (!settings.value) return {};
  return Object.entries(settings.value)
    .filter(([, groupDetails]) => {
      const baseProvider = groupDetails.base_provider?.value;
      return baseProvider === 'llm';
    })
    .reduce((obj, [key, value]) => ({ ...obj, [key]: value }), {});
});

const requestProviderSettings = computed(() => {
  if (!settings.value) return {};
  return Object.entries(settings.value)
    .filter(([, groupDetails]) => groupDetails.base_provider?.value === 'request')
    .reduce((obj, [key, value]) => ({ ...obj, [key]: value }), {});
});

const geminiModels = computed(() => {
  return llmModels.value?.gemini || [];
});

const ollamaModels = computed(() => {
  return llmModels.value?.ollama || [];
});

const openaiModels = computed(() => {
  return llmModels.value?.openai || [];
});

// Helper functions for type checking
const isNumberType = (value) => typeof value === 'number'
const isBooleanType = (value) => typeof value === 'boolean'

const isProviderConfigured = (groupName) => {
  if (!settings.value || !settings.value[groupName]) {
    return false; // Group doesn't exist in settings
  }
  const group = settings.value[groupName];
  const tmdbApiKeySet = !!(settings.value.tmdb && settings.value.tmdb.api_key && settings.value.tmdb.api_key.value); // Check for TMDB API key

  switch (groupName) {
    case 'gemini':
      return !!group.api_key?.value && tmdbApiKeySet; // Gemini needs its API key AND TMDB's
    case 'openai':
      return !!group.api_key?.value && tmdbApiKeySet; // OpenAI needs its API key AND TMDB's
    case 'ollama':
      // Ollama primarily needs a base_url to be functional for enabling, AND TMDB's API key
      return !!group.base_url?.value && tmdbApiKeySet; 
    case 'radarr':
    case 'sonarr':
    case 'plex':
    case 'overseerr':
    case 'jellyseerr':
    case 'jellyfin':
      return !!group.url?.value && !!group.api_key?.value;
    case 'trakt':
      return !!group.client_id?.value && !!group.client_secret?.value;
    default:
      return true; // For any other group or if a group doesn't match, assume it's configurable
  }
};

// Get placeholder text for inputs
const getPlaceholder = (group, key) => {
  if (key.includes('url')) {
    return 'http://example:port'
  } else if (key.includes('api_key')) {
    return 'Enter API key'
  } else if (key.includes('limit')) {
    return '5'
  }
  return ''
}

// Load settings from the server
const loadSettings = async () => {
  try {
    const response = await fetch(`${config.apiUrl}/settings`)
    if (!response.ok) throw new Error('Failed to load settings')
    settings.value = await response.json()
    originalValues = JSON.parse(JSON.stringify(settings.value))
  } catch (error) {
    console.error('Error loading settings:', error)
  }
}

// Load LLM models (Gemini, Ollama, etc.)
const fetchLlmModels = async () => {
  // Check if at least one LLM provider is enabled in settings
  const geminiEnabled = settings.value?.gemini?.enabled?.value;
  const ollamaEnabled = settings.value?.ollama?.enabled?.value;
  const openaiEnabled = settings.value?.openai?.enabled?.value;

  if (!geminiEnabled && !ollamaEnabled && !openaiEnabled) {
    console.log('No LLM providers are enabled. Skipping fetching LLM models.');
    llmModels.value = {}; // Ensure models object is empty
    loadingLlmModels.value = false;
    return;
  }

  loadingLlmModels.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/llm/models`);
    if (!response.ok) throw new Error('Failed to load LLM models');
    llmModels.value = await response.json(); // Expects format: { "gemini": [...], "ollama": [...], "openai": [...] }
    console.log('LLM Models loaded:', llmModels.value);
  } catch (error) {
    console.error('Error loading LLM models:', error);
    llmModels.value = {}; // Set to empty object on error
  } finally {
    loadingLlmModels.value = false;
  }
};
// Load Radarr quality profiles
const fetchRadarrQualityProfiles = async () => {
  loadingRadarrProfiles.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/quality-profiles/movie`);
    if (!response.ok) throw new Error('Failed to load Radarr quality profiles');
    radarrQualityProfiles.value = await response.json();
  } catch (error) {
    console.error('Error loading Radarr quality profiles:', error);
    radarrQualityProfiles.value = []; // Set to empty array on error
  } finally {
    loadingRadarrProfiles.value = false;
  }
};

// Load Sonarr quality profiles
const fetchSonarrQualityProfiles = async () => {
  loadingSonarrProfiles.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/quality-profiles/tv`);
    if (!response.ok) throw new Error('Failed to load Sonarr quality profiles');
    sonarrQualityProfiles.value = await response.json();
  } catch (error) {
    console.error('Error loading Sonarr quality profiles:', error);
    sonarrQualityProfiles.value = []; // Set to empty array on error
  } finally {
    loadingSonarrProfiles.value = false;
  }
};

// Load Jellyseerr users
const fetchJellyseerrUsers = async () => {
  loadingJellyseerrUsers.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/jellyseerr/users`);
    if (!response.ok) throw new Error('Failed to load Jellyseerr users');
    jellyseerrUsers.value = await response.json();
  } catch (error) {
    console.error('Error loading Jellyseerr users:', error);
    jellyseerrUsers.value = [];
    toastStore.show(`Failed to load Jellyseerr users: ${error.message}`, 'error');
  } finally {
    loadingJellyseerrUsers.value = false;
  }
};

// Load Overseerr users
const fetchOverseerrUsers = async () => {
  loadingOverseerrUsers.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/overseerr/users`);
    if (!response.ok) throw new Error('Failed to load Overseerr users');
    overseerrUsers.value = await response.json();
  } catch (error) {
    console.error('Error loading Overseerr users:', error);
    overseerrUsers.value = [];
    toastStore.show(`Failed to load Overseerr users: ${error.message}`, 'error');
  } finally {
    loadingOverseerrUsers.value = false;
  }
};
// Load users from the server
const fetchUsers = async () => {
  loadingUsers.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/users`);
    if (!response.ok) throw new Error('Failed to load users');
    // Assuming the API returns an array of user objects like:
    // { id: 'some_id_or_name', username: 'User Display Name', source_provider: 'plex' }
    users.value = await response.json();
  } catch (error) {
    console.error('Error loading users:', error);
    users.value = [];
    toastStore.show(`Failed to load users: ${error.message}`, 'error');
  } finally {
    loadingUsers.value = false;
  }
};

// Trakt Authentication
const traktAuthenticate = async () => {
  traktAuthLoading.value = true;
  traktAuthError.value = '';
  showTraktAuthModal.value = true; // Show modal immediately
  try {
    const response = await fetch(`${config.apiUrl}/trakt/authenticate`, {
      method: 'POST',
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Failed to initiate Trakt authentication. Status: ${response.status}`);
    }
    traktAuthDetails.value = {
      user_code: data.user_code,
      verification_url: data.verification_url,
      message: data.message
    };
    // Modal is already shown, user will see the details or error message.
  } catch (error) {
    console.error('Error initiating Trakt authentication:', error);
    traktAuthError.value = error.message;
    traktAuthDetails.value = { user_code: '', verification_url: '', message: '' }; // Clear details on error
    // toastStore.show(`Trakt Authentication Error: ${error.message}`, 'error'); // Toast is also an option
  } finally {
    traktAuthLoading.value = false;
  }
};
// Update a setting
const updateSetting = async (group, name) => {
  // Only update if the setting's value has changed
  // Ensure originalValues and the specific setting path exist
  if (originalValues && originalValues[group] && originalValues[group][name] &&
      settings.value[group][name].value === originalValues[group][name].value) {
    return;
  }

  let valueToSave = settings.value[group][name].value;
  const currentGroupDetails = settings.value[group];

  // Automatically disable other LLM providers if this one is being enabled
  if (currentGroupDetails.base_provider?.value === 'llm' && name === 'enabled' && valueToSave === true) {
    // Iterate over the group names of LLM providers identified by llmProviderSettings
    for (const otherGroupName of Object.keys(llmProviderSettings.value)) {
      if (otherGroupName === group) continue; // Skip the current group

      // Get the settings for the other LLM provider group from the main settings object
      const otherLLMGroupDetails = settings.value[otherGroupName];
      if (otherLLMGroupDetails.enabled?.value === true) { // Check if it's enabled
        console.log(`Attempting to disable other LLM provider: ${otherGroupName}`);
        
        const originalOtherProviderEnabledState = originalValues[otherGroupName]?.enabled?.value;
        settings.value[otherGroupName].enabled.value = false; // Update local state for UI responsiveness

        try {
          // Call updateSetting for the other provider to disable it and persist the change.
          // This recursive call will handle its own API request and originalValues update.
          await updateSetting(otherGroupName, 'enabled'); 
          toastStore.show(`${otherGroupName.charAt(0).toUpperCase() + otherGroupName.slice(1)} provider has been automatically disabled.`, 'info');
        } catch (error) {
          console.error(`Failed to automatically disable ${otherGroupName}:`, error);
          // Revert local change for the other provider if disabling failed
          if (originalValues[otherGroupName]?.enabled) { // Check if originalValues path exists
            settings.value[otherGroupName].enabled.value = originalOtherProviderEnabledState;
          }
          toastStore.show(`Failed to automatically disable ${otherGroupName}. Please disable it manually.`, 'error');
          
          // Revert the current provider's enabling attempt as well
          settings.value[group][name].value = originalValues[group][name].value;
          return; // Stop further processing for the current setting
        }
      }
    }
  }

  // Automatically manage request provider exclusivity
  if (currentGroupDetails.base_provider?.value === 'request' && name === 'enabled' && valueToSave === true) {
    const proxyProviders = ['jellyseerr', 'overseerr'];
    const directProviders = ['radarr', 'sonarr'];

    if (proxyProviders.includes(group)) {
      // If a proxy provider (Jellyseerr/Overseerr) is enabled, disable all other request providers.
      const providersToDisable = [...proxyProviders.filter(p => p !== group), ...directProviders];
      for (const otherProvider of providersToDisable) {
        if (settings.value[otherProvider]?.enabled?.value === true) {
          const originalState = originalValues[otherProvider].enabled.value;
          settings.value[otherProvider].enabled.value = false;
          try {
            await updateSetting(otherProvider, 'enabled');
            toastStore.show(`${otherProvider.charAt(0).toUpperCase() + otherProvider.slice(1)} has been automatically disabled.`, 'info');
          } catch (error) {
            console.error(`Failed to automatically disable ${otherProvider}:`, error);
            settings.value[otherProvider].enabled.value = originalState; // Revert on failure
            toastStore.show(`Failed to automatically disable ${otherProvider}. Please disable it manually.`, 'error');
            // Also revert the original action
            settings.value[group][name].value = originalValues[group][name].value;
            return; // Stop processing
          }
        }
      }
    } else if (directProviders.includes(group)) {
      // If a direct provider (Radarr/Sonarr) is enabled, disable all proxy providers.
      for (const proxyProvider of proxyProviders) {
        if (settings.value[proxyProvider]?.enabled?.value === true) {
          const originalState = originalValues[proxyProvider].enabled.value;
          settings.value[proxyProvider].enabled.value = false;
          try {
            await updateSetting(proxyProvider, 'enabled');
            toastStore.show(`${proxyProvider.charAt(0).toUpperCase() + proxyProvider.slice(1)} has been automatically disabled.`, 'info');
          } catch (error) {
            console.error(`Failed to automatically disable ${proxyProvider}:`, error);
            settings.value[proxyProvider].enabled.value = originalState; // Revert on failure
            toastStore.show(`Failed to automatically disable ${proxyProvider}. Please disable it manually.`, 'error');
            // Also revert the original action
            settings.value[group][name].value = originalValues[group][name].value;
            return; // Stop processing
          }
        }
      }
    }
  }

  try {
    const response = await fetch(`${config.apiUrl}/settings/${group}/${name}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      // Send the actual value, ensuring null is handled correctly by backend
      // valueToSave?.toString() will be undefined if valueToSave is null,
      // which results in the 'value' key not being present in JSON if it's the only property.
      body: JSON.stringify({
        value: valueToSave !== null ? valueToSave.toString() : null
      })
    })

    if (!response.ok) throw new Error('Failed to update setting') 

    // If the setting was successfully updated on the backend,
    // update the local 'originalValues' to reflect this new persisted state.
    // This is crucial for the "Only update if the setting's value has changed" check at the beginning.
    const successfullyUpdatedValue = settings.value[group][name].value;
    originalValues[group][name].value = successfullyUpdatedValue;

    // If a setting for an enabled Gemini provider was changed (e.g., API key updated, or enabled set to true),
    if ((group === 'gemini' && settings.value.gemini?.enabled?.value === true) || (group === 'ollama' && settings.value.ollama?.enabled?.value === true) || (group === 'openai' && settings.value.openai?.enabled?.value === true)) {
        await fetchLlmModels();
    }
    // If a setting for a request provider was updated, refresh Radarr profiles if any are configured
    if ((group === 'radarr' || group === 'jellyseerr' || group === 'overseerr') && (
      (settings.value.radarr?.enabled?.value && settings.value.radarr?.api_key?.value) ||
      (settings.value.jellyseerr?.enabled?.value && settings.value.jellyseerr?.api_key?.value) ||
      (settings.value.overseerr?.enabled?.value && settings.value.overseerr?.api_key?.value)
    )) {
        await fetchRadarrQualityProfiles();
    }
    // If a setting for a request provider was updated, refresh Sonarr profiles if any are configured
    if ((group === 'sonarr' || group === 'jellyseerr' || group === 'overseerr') && (
      (settings.value.sonarr?.enabled?.value && settings.value.sonarr?.api_key?.value) ||
      (settings.value.jellyseerr?.enabled?.value && settings.value.jellyseerr?.api_key?.value) ||
      (settings.value.overseerr?.enabled?.value && settings.value.overseerr?.api_key?.value)
    )) {
        await fetchSonarrQualityProfiles();
    }
    // If a setting for Jellyseerr was updated, refresh its users
    if (group === 'jellyseerr' && settings.value.jellyseerr?.enabled?.value && settings.value.jellyseerr?.api_key?.value) {
        await fetchJellyseerrUsers();
    }
    // If a setting for Overseerr was updated, refresh its users
    if (group === 'overseerr' && settings.value.overseerr?.enabled?.value && settings.value.overseerr?.api_key?.value) {
        await fetchOverseerrUsers();
    }
    // Specific action for Trakt when it's enabled
    if (group === 'trakt' && name === 'enabled' && successfullyUpdatedValue === true) {
        toastStore.show('Trakt enabled. Please follow the authentication instructions.', 'info');
        // Fetch users immediately if a library provider is enabled
        await fetchUsers();
        await traktAuthenticate();
      }
    // Fetch users if any other library provider (Plex, Jellyfin) is enabled
    else if (['plex', 'jellyfin'].includes(group) && name === 'enabled' && successfullyUpdatedValue === true) {
        await fetchUsers();
    }
    // Consider a generic success toast if not an auto-disable call, or rely on UI change.
    // For now, no explicit success toast for individual updates to keep UI less noisy.
  } catch (error) {
    console.error('Error updating setting:', error)
    // Revert to original value on error
    if (originalValues && originalValues[group] && originalValues[group][name]) {
      settings.value[group][name].value = originalValues[group][name].value
    }
    toastStore.show(`Failed to update setting ${group}.${name}: ${error.message}`, 'error');
  }
}

// Fetch token usage summary
const fetchTokenUsageSummary = async () => {
  loadingTokenUsage.value = true;
  tokenUsageError.value = null;
  let url = `${config.apiUrl}/search/stat/summary`;
  const params = new URLSearchParams();
  if (startDate.value) {
    params.append('start_date', new Date(startDate.value).toISOString());
  }
  if (endDate.value) {
    params.append('end_date', new Date(endDate.value).toISOString());
  }
  if (params.toString()) {
    url += `?${params.toString()}`;
  }
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to load token usage summary' }));
      throw new Error(errorData.detail || `HTTP error ${response.status}`);
    }
    tokenUsageSummary.value = await response.json();
  } catch (error) {
    console.error('Error loading token usage summary:', error);
    tokenUsageError.value = error.message;
    tokenUsageSummary.value = null; // Clear any previous data
  } finally {
    loadingTokenUsage.value = false;
  }
};

// Format token values (e.g., cost as currency)
const formatTokenValue = (key, value) => {
  if (key.toLowerCase().includes('cost')) {
    return `$${Number(value).toFixed(4)}`;
  }
  return value;
};

// Date range logic
const updateDatesFromRange = () => {
  const now = new Date();
  let newStartDate = new Date();
  let newEndDate = new Date(now); // Set end date to now by default for ranges ending "now"

  switch (selectedRange.value) {
    case 'yesterday':
      newStartDate.setDate(now.getDate() - 1);
      newEndDate.setDate(now.getDate() - 1);
      newStartDate.setHours(0, 0, 0, 0);
      newEndDate.setHours(23, 59, 59, 999);
      break;
    case 'last_week':
      newStartDate.setDate(now.getDate() - now.getDay() - 6); // Last week's Monday
      newEndDate.setDate(now.getDate() - now.getDay());    // Last week's Sunday
      newStartDate.setHours(0, 0, 0, 0);
      newEndDate.setHours(23, 59, 59, 999);
      break;
    case 'last_month':
      newStartDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      newEndDate = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59, 999);
      break;
    case 'last_year':
      newStartDate = new Date(now.getFullYear() - 1, 0, 1);
      newEndDate = new Date(now.getFullYear() - 1, 11, 31, 23, 59, 59, 999);
      break;
    case 'all_time':
      startDate.value = '';
      endDate.value = '';
      fetchTokenUsageSummary(); // Refetch for all time
      return;
    case 'custom':
      // Do nothing, user will set dates manually
      // If startDate and endDate are empty, perhaps set a default custom range like today
      if (!startDate.value && !endDate.value) {
        const todayStart = new Date();
        todayStart.setHours(0,0,0,0);
        startDate.value = todayStart.toISOString().slice(0, 16);
        const todayEnd = new Date();
        todayEnd.setHours(23,59,59,999);
        endDate.value = todayEnd.toISOString().slice(0,16);
      }
      return; // Don't automatically fetch for custom if dates not set yet
  }

  startDate.value = newStartDate.toISOString().slice(0, 16); // Format for datetime-local
  endDate.value = newEndDate.toISOString().slice(0, 16);     // Format for datetime-local
};

const handleDateInputChange = () => {
  selectedRange.value = 'custom';
  // The watch effect on startDate and endDate will trigger the fetch
};

// Watch for changes in dates to refetch summary
watch([startDate, endDate], () => {
  // Only fetch if both dates are set for custom, or if one is cleared (implicitly all_time or invalid custom)
  // The selectedRange changing to 'all_time' will also trigger a fetch via updateDatesFromRange
  if ((startDate.value && endDate.value) || (!startDate.value && !endDate.value && selectedRange.value !== 'all_time')) {
     fetchTokenUsageSummary();
  }
});

const atLeastOneLibraryProviderEnabled = computed(() => {
  if (!settings.value || !libraryProviderSettings.value) return false;
  return Object.keys(libraryProviderSettings.value).some(groupName => {
    return settings.value[groupName]?.enabled?.value === true;
  });
});

const scrollToHash = (hash) => {
  if (!hash) return;
  // Use nextTick to ensure the DOM has a chance to update before we try to find the element.
  // This is especially useful for the watcher when navigating within the page.
  nextTick(() => {
    const element = document.querySelector(hash);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      // This warning is helpful for debugging if the element isn't found.
      console.warn(`Anchor element '${hash}' not found.`);
    }
  });
};

onMounted(async () => { // Make onMounted async
  await loadSettings(); // Await the loading of settings

  // Fetch Radarr quality profiles if any relevant provider is configured
  if (
    (settings.value?.radarr?.enabled?.value && settings.value?.radarr?.api_key?.value) ||
    (settings.value?.jellyseerr?.enabled?.value && settings.value?.jellyseerr?.api_key?.value) ||
    (settings.value?.overseerr?.enabled?.value && settings.value?.overseerr?.api_key?.value)
  ) {
    fetchRadarrQualityProfiles();
  }
  // Fetch Sonarr quality profiles if any relevant provider is configured
  if (
    (settings.value?.sonarr?.enabled?.value && settings.value?.sonarr?.api_key?.value) ||
    (settings.value?.jellyseerr?.enabled?.value && settings.value?.jellyseerr?.api_key?.value) ||
    (settings.value?.overseerr?.enabled?.value && settings.value?.overseerr?.api_key?.value)
  ) {
    fetchSonarrQualityProfiles();
  }
  
  // Fetch Jellyseerr users if configured
  if (settings.value?.jellyseerr?.enabled?.value && settings.value?.jellyseerr?.api_key?.value) {
    fetchJellyseerrUsers();
  }

  // Fetch Overseerr users if configured
  if (settings.value?.overseerr?.enabled?.value && settings.value?.overseerr?.api_key?.value) {
    fetchOverseerrUsers();
  }

  // Fetch LLM models if any LLM provider is enabled
  await fetchLlmModels();

  // Fetch users only if at least one library provider is enabled
  if (atLeastOneLibraryProviderEnabled.value) {
    await fetchUsers();
  }
  updateDatesFromRange(); // Initialize dates based on default selectedRange and fetch

  // Scroll to anchor link if present in URL
  // A small timeout is used to ensure all v-if/v-for elements
  // based on the fetched settings have been rendered in the DOM. This fixes
  // a race condition that can occur on a soft refresh (F5).
  if (route.hash) {
    setTimeout(() => scrollToHash(route.hash), 150);
  }
});

// Watch for subsequent hash changes (e.g., clicking TOC links) for smooth in-page navigation.
watch(() => route.hash, (newHash) => {
  if (newHash) {
    scrollToHash(newHash);
  }
});
</script>

<template>
  <!-- Root element for scrolling, page background, and vertical padding -->
  <div class="flex h-full bg-black text-white"> <!-- Changed h-screen to h-full -->
    <!-- Fixed TOC Sidebar -->
    <aside class="w-64 h-full overflow-y-auto p-6 bg-gray-800 text-gray-300 border-r border-gray-700 flex-shrink-0"> <!-- Removed fixed, top, left, z-10; Added flex-shrink-0 -->
      <h2 class="text-lg font-semibold text-white mb-4">Settings</h2>
      <nav>
        <ul class="space-y-2">
          <li>
            <a href="#section-token-usage" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2">Token Usage Summary</a>
          </li>
          <li>
            <a href="#section-keyboard-shortcuts" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2">Keyboard Shortcuts</a>
          </li>
          <li>
            <a href="#section-help" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2">Help / Instructions</a>
          </li>
          <li v-if="settings" class="pt-3 mt-3 border-t border-gray-700">
            <a href="#section-application-settings" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2">Application Settings</a>
            <ul class="space-y-1">
              <li v-for="(groupSettings, groupName) in applicationSettings" :key="`toc-app-${groupName}`">
                <a :href="`#section-settings-${groupName}`" class="hover:text-amber-400 block capitalize pl-3 py-0.5 text-sm py-1">
                  {{ groupName.replace(/_/g, ' ') }}
                </a>
              </li>
            </ul>
            <a href="#section-library-provider-settings" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2 mt-2">Library Provider Settings</a>
            <ul class="space-y-1">
              <li v-for="(groupSettings, groupName) in libraryProviderSettings" :key="`toc-lib-provider-${groupName}`">
                <a :href="`#section-settings-${groupName}`" class="hover:text-amber-400 block capitalize pl-3 py-0.5 text-sm py-1">
                  {{ groupName.replace(/_/g, ' ') }}
                </a>
              </li>
            </ul>
            <a href="#section-request-provider-settings" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2 mt-2">Request Provider Settings</a>
            <ul class="space-y-1">
              <li v-for="(groupSettings, groupName) in requestProviderSettings" :key="`toc-req-provider-${groupName}`">
                <a :href="`#section-settings-${groupName}`" class="hover:text-amber-400 block capitalize pl-3 py-0.5 text-sm py-1">
                  {{ groupName.replace(/_/g, ' ') }}
                </a>
              </li>
            </ul>
            <a href="#section-llm-provider-settings" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2 mt-2">LLM Provider Settings</a>
            <ul class="space-y-1">
              <li v-for="(groupSettings, groupName) in llmProviderSettings" :key="`toc-llm-provider-${groupName}`">
                <a :href="`#section-settings-${groupName}`" class="hover:text-amber-400 block capitalize pl-3 py-0.5 text-sm py-1">
                  {{ groupName.replace(/_/g, ' ') }}
                </a>
              </li>
            </ul>
          </li>
        </ul>
      </nav>
    </aside>

    <!-- Scrollable Main Content Area -->
    <main class="flex-1 overflow-y-auto">
      <div class="px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto py-6 sm:py-12">

        <!-- Token Usage Section -->
        <div id="section-token-usage" class="mb-8">
          <h2 class="text-2xl text-white font-semibold mb-4">Token Usage Summary</h2>
          <div class="bg-gray-900 rounded-lg p-6 shadow-md">
            <!-- Date Range Filters -->
            <div class="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div>
                <label for="dateRange" class="block text-sm font-medium text-gray-300 mb-1">Date Range</label>
                <select id="dateRange" v-model="selectedRange" @change="updateDatesFromRange" class="w-full p-2 bg-gray-800 border border-gray-700 rounded-md focus:ring-discovarr focus:border-discovarr">
                  <option value="all_time">All Time</option>
                  <option value="yesterday">Yesterday</option>
                  <option value="last_week">Last Week</option>
                  <option value="last_month">Last Month</option>
                  <option value="last_year">Last Year</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div>
                <label for="startDate" class="block text-sm font-medium text-gray-300 mb-1">Start Date</label>
                <input type="datetime-local" id="startDate" v-model="startDate" @change="handleDateInputChange" class="w-full p-2 bg-gray-800 border border-gray-700 rounded-md focus:ring-discovarr focus:border-discovarr">
              </div>
              <div>
                <label for="endDate" class="block text-sm font-medium text-gray-300 mb-1">End Date</label>
                <input type="datetime-local" id="endDate" v-model="endDate" @change="handleDateInputChange" class="w-full p-2 bg-gray-800 border border-gray-700 rounded-md focus:ring-discovarr focus:border-discovarr">
              </div>
            </div>

            <!-- Summary Display -->
            <div>
              <div v-if="loadingTokenUsage" class="text-gray-400 text-center py-4">Loading token usage...</div>
              <div v-else-if="tokenUsageError" class="text-red-400 text-center py-4">{{ tokenUsageError }}</div>
              <div v-else-if="tokenUsageSummary && Object.keys(tokenUsageSummary).length > 0" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div v-for="(value, key) in tokenUsageSummary" :key="key" class="bg-gray-800 p-4 rounded-md">
                  <dt class="text-sm font-medium text-gray-400 capitalize">{{ key.replace(/_/g, ' ') }}</dt>
                  <dd class="mt-1 text-lg font-semibold text-white">
                    {{ formatTokenValue(key, value) }}
                  </dd>
                </div>
              </div>
              <div v-else class="text-gray-500 text-center py-4">No token usage data available for the selected period.</div>
            </div>
          </div>
        </div>

        <!-- Keyboard Shortcuts Section -->
        <div id="section-keyboard-shortcuts" class="mb-8">
          <h2 class="text-2xl text-white font-semibold mb-4">Keyboard Shortcuts</h2>
          <div class="bg-gray-900 rounded-lg p-6 shadow-md">
            <table class="w-full text-sm text-left text-gray-400">
              <thead class="text-xs text-gray-300 uppercase bg-gray-800/50">
                <tr>
                  <th scope="col" class="px-4 py-2 w-1/4 text-center">Key</th>
                  <th scope="col" class="px-4 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr class="border-b border-gray-700 hover:bg-gray-800/30">
                  <td class="px-4 py-3 text-center">
                    <kbd class="px-2 py-1.5 text-xs font-semibold text-gray-200 bg-gray-700 border border-gray-600 rounded-md">
                      /
                    </kbd>
                  </td>
                  <td class="px-4 py-3 text-gray-300">Open Search</td>
                </tr>
                <tr class="border-b border-gray-700 hover:bg-gray-800/30 last:border-b-0 ">
                  <td class="px-4 py-3 text-center">
                    <kbd class="px-2 py-1.5 text-xs font-semibold text-gray-200 bg-gray-700 border border-gray-600 rounded-md">
                      Esc
                    </kbd>
                  </td>
                  <td class="px-4 py-3 text-gray-300">Close Modal / Pop-up</td>
                </tr>
                <!-- Add more shortcuts here as <tr> elements -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- Help / Instructions Section -->
        <div id="section-help" class="mb-8">
          <h2 class="text-2xl text-white font-semibold mb-4">Help / Instructions</h2>
          <div class="bg-gray-900 rounded-lg p-6 shadow-md space-y-3 text-gray-300">
            <ul class="list-disc pl-5 space-y-2">
              <li><strong>LLM Providers (Gemini/Ollama):</strong> Only one LLM provider can be enabled at a time.</li>
              <li>
                LLM providers require a <a href="#section-settings-tmdb" class="text-discovarr hover:underline">TMDB API key</a> to be configured for full functionality.
              </li>
              <li>Use the navigation on the left to jump to specific setting groups.</li>
            </ul>
            <p>Remember to configure your API keys and URLs for services like
              <a href="#section-settings-radarr" class="text-discovarr hover:underline">Radarr</a>,
              <a href="#section-settings-sonarr" class="text-discovarr hover:underline">Sonarr</a>,
              <a href="#section-settings-tmdb" class="text-discovarr hover:underline">TMDB</a>,
              and your chosen LLM provider (e.g.,
              <a href="#section-settings-gemini" class="text-discovarr hover:underline">Gemini</a> or
              <a href="#section-settings-ollama" class="text-discovarr hover:underline">Ollama</a>) for full functionality.</p>
            <!-- Add more instructions here -->
          </div>
        </div>

        <!-- Application Settings Section -->
        <div id="section-application-settings">
          <h2 class="text-2xl text-white font-semibold mb-6">Application Settings</h2>
          <div v-if="Object.keys(applicationSettings).length > 0" class="space-y-8">
            <div v-for="(groupSettings, groupName) in applicationSettings" :key="groupName" :id="`section-settings-${groupName}`" class="bg-gray-900 rounded-lg p-6 shadow-md">
            <h3 class="text-xl text-white font-medium mb-4 capitalize">{{ groupName }}</h3>

            <div class="space-y-4">
              <div v-for="(settingDetails, settingName) in groupSettings" :key="settingName" class="flex flex-col">
                <div v-if="settingDetails.show != false">
                  <label :for="groupName + '-' + settingName" class="text-gray-400 capitalize">
                    {{ settingName.replace(/_/g, ' ') }}
                    <span v-if="settingDetails.required" class="text-red-500 ml-1">*</span>
                  </label>
                  <!-- Textarea for specific settings like default_prompt -->
                  <div v-if="groupName === 'app' && settingName === 'default_prompt'">
                    <textarea
                      :id="groupName + '-' + settingName"
                      v-model="settingDetails.value"
                      @change="updateSetting(groupName, settingName)"
                      class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 min-h-[80px] resize-y"
                      rows="5"
                      :placeholder="getPlaceholder(groupName, settingName)"
                    ></textarea>
                    <div class="mt-2 mb-4">Supported template variables: 
                      <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">limit</span>
                      <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">media_name</span>
                      <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">all_media</span>
                      <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">watch_history</span>
                    </div>
                  </div>  
                  <!-- Textarea for specific settings like system_prompt -->
                  <div v-else-if="groupName === 'app' && (settingName === 'system_prompt' || settingName === 'default_research_prompt')">
                    <textarea
                      :id="groupName + '-' + settingName"
                      v-model="settingDetails.value"
                      @change="updateSetting(groupName, settingName)"
                      class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 min-h-[80px] resize-y"
                      rows="5"
                      :placeholder="getPlaceholder(groupName, settingName)"
                    ></textarea>
                  </div>

                  <!-- Other input types -->
                  <input             
                    v-else-if="isNumberType(settingDetails.value) && typeof settingDetails.value !== 'undefined' && settingDetails.value !== null"
                    :id="groupName + '-' + settingName"
                    v-model.number="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    type="number"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                  >
                  <input
                    v-else-if="isBooleanType(settingDetails.value) && typeof settingDetails.value !== 'undefined'"
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    type="checkbox"
                    class="w-6 h-6 mx-2 bg-black border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 cursor-pointer"
                  >
                  <input
                    v-else
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    :type="settingName.includes('key') || settingName.includes('token') ? 'password' : 'text'"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :placeholder="getPlaceholder(groupName, settingName)"
                  >
                  <div class="mt-1 text-sm text-gray-500">
                    {{ settingDetails.description }}
                  </div>
                </div>
              </div>
            </div>
            </div>
          </div>
        </div>

        <!-- Library Provider Settings Section -->
        <div id="section-library-provider-settings" class="mt-8">
          <h2 class="text-2xl text-white font-semibold mb-6">Library Provider Settings</h2>
          <div class="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6 text-sm text-gray-400 text-center">
            <p>Configure your library providers like Plex, Jellyfin, and Trakt here.</p>
            <p>Ensure URLs are correct and API keys are provided for enabled services.</p>
            <p>Note: Results are combined when multiple library providers are enabled.</p>
            <!-- Add more specific library provider instructions here -->
          </div>
          <div v-if="Object.keys(libraryProviderSettings).length > 0" class="space-y-8">
            <div v-for="(groupSettings, groupName) in libraryProviderSettings" :key="groupName" :id="`section-settings-${groupName}`" class="bg-gray-900 rounded-lg p-6 shadow-md">
            <h3 class="text-xl text-white font-medium mb-4 capitalize">{{ groupName }}</h3>

            <div class="space-y-4">
              <div v-for="(settingDetails, settingName) in groupSettings" :key="settingName" class="flex flex-col">
                <div v-if="settingDetails.show != false">
                  <label :for="groupName + '-' + settingName" class="text-gray-400 mb-1 capitalize">
                    {{ settingName.replace(/_/g, ' ') }}
                    <span v-if="settingDetails.required" class="text-red-500 ml-1">*</span>
                  </label>

                  <!-- Default User Dropdowns for Plex, Jellyfin, Trakt -->
                  <template v-if="['plex', 'jellyfin', 'trakt'].includes(groupName) && settingName === 'default_user'">
                    <select
                      :id="groupName + '-' + settingName"
                      v-model="settingDetails.value" @change="updateSetting(groupName, settingName)"
                      class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500" :disabled="loadingUsers">
                      <option :value="null">{{ loadingUsers ? 'Loading users...' : (users.filter(u => u.source_provider === groupName).length === 0 ? `No ${groupName} users in system` : 'None (System Default)') }}</option>
                      <option v-for="user in users.filter(u => u.source_provider === groupName)" :key="user.id" :value="user.id">{{ user.name }}</option>
                    </select>
                  </template>

                  <!-- Other input types -->
                  <input             
                    v-else-if="isNumberType(settingDetails.value) && typeof settingDetails.value !== 'undefined' && settingDetails.value !== null"
                    :id="groupName + '-' + settingName"
                    v-model.number="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    type="number"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                  >
                  <input
                    v-else-if="isBooleanType(settingDetails.value) && typeof settingDetails.value !== 'undefined'"
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    type="checkbox"
                    :disabled="settingName === 'enabled' && !isProviderConfigured(groupName)"
                    class="w-6 h-6 mx-2 bg-black border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 cursor-pointer"
                  >
                  <input
                    v-else
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    :type="settingName.includes('key') || settingName.includes('token') ? 'password' : 'text'"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :placeholder="getPlaceholder(groupName, settingName)"
                  >
                  <div v-if="settingName === 'enabled' && !isProviderConfigured(groupName)" class="mt-1 text-xs text-yellow-400">
                    *Required fields are missing
                  </div>
                  <div class="mt-1 text-sm text-gray-500">
                    {{ settingDetails.description }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <!-- Request Provider Settings Section -->
        <div id="section-request-provider-settings" class="mt-8">
          <h2 class="text-2xl text-white font-semibold mb-6">Request Provider Settings</h2>
          <div class="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6 text-sm text-gray-400 text-center">
            <p>Configure your request providers like Radarr, Sonarr, Jellyseerr, and Overseerr.</p>
            <p>Jellyseerr and Overseerr act as proxies; if one is enabled, it will be used for requests and all other request providers will be disabled automatically.</p>
            <p>If you enable Radarr or Sonarr, Jellyseerr and Overseerr will be disabled automatically.</p>
          </div>
          <div v-if="Object.keys(requestProviderSettings).length > 0" class="space-y-8">
            <div v-for="(groupSettings, groupName) in requestProviderSettings" :key="groupName" :id="`section-settings-${groupName}`" class="bg-gray-900 rounded-lg p-6 shadow-md">
              <h3 class="text-xl text-white font-medium mb-4 capitalize">{{ groupName }}</h3>
              <div class="space-y-4">
                <div v-for="(settingDetails, settingName) in groupSettings" :key="settingName" class="flex flex-col">
                  <div v-if="settingDetails.show != false">
                    <label :for="groupName + '-' + settingName" class="text-gray-400 capitalize">
                      {{ settingName.replace(/_/g, ' ') }}
                      <span v-if="settingDetails.required" class="text-red-500 ml-1">*</span>
                    </label>
                    <!-- Radarr Default Quality Profile ID Dropdown -->
                    <template v-if="groupName === 'radarr' && settingName === 'default_quality_profile_id'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model.number="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingRadarrProfiles"
                      >
                        <option :value="null">
                          {{ loadingRadarrProfiles ? 'Loading profiles...' : 'Default' }}
                        </option>
                        <option v-for="profile in radarrQualityProfiles" :key="profile.id" :value="profile.id">
                          {{ profile.name }}
                        </option>
                      </select>
                    </template>

                    <!-- Sonarr Default Quality Profile ID Dropdown -->
                    <template v-else-if="groupName === 'sonarr' && settingName === 'default_quality_profile_id'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model.number="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingSonarrProfiles"
                      >
                        <option :value="null">
                          {{ loadingSonarrProfiles ? 'Loading profiles...' : 'Default' }}
                        </option>
                        <option v-for="profile in sonarrQualityProfiles" :key="profile.id" :value="profile.id">
                          {{ profile.name }}
                        </option>
                      </select>
                    </template>

                    <!-- Jellyseerr Default Radarr Quality Profile ID Dropdown -->
                    <template v-else-if="groupName === 'jellyseerr' && settingName === 'default_radarr_quality_profile_id'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model.number="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingRadarrProfiles"
                      >
                        <option :value="null">
                          {{ loadingRadarrProfiles ? 'Loading profiles...' : 'Default' }}
                        </option>
                        <option v-for="profile in radarrQualityProfiles" :key="profile.id" :value="profile.id">
                          {{ profile.name }}
                        </option>
                      </select>
                    </template>

                    <!-- Jellyseerr Default Sonarr Quality Profile ID Dropdown -->
                    <template v-else-if="groupName === 'jellyseerr' && settingName === 'default_sonarr_quality_profile_id'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model.number="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingSonarrProfiles"
                      >
                        <option :value="null">
                          {{ loadingSonarrProfiles ? 'Loading profiles...' : 'Default' }}
                        </option>
                        <option v-for="profile in sonarrQualityProfiles" :key="profile.id" :value="profile.id">
                          {{ profile.name }}
                        </option>
                      </select>
                    </template>

                    <!-- Jellyseerr Default User Dropdown -->
                    <template v-else-if="groupName === 'jellyseerr' && settingName === 'default_user'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingJellyseerrUsers"
                      >
                        <option :value="null">
                          {{ loadingJellyseerrUsers ? 'Loading users...' : 'Select a user...' }}
                        </option>
                        <option v-for="user in jellyseerrUsers" :key="user.id" :value="user.displayName">
                          {{ user.displayName }}
                        </option>
                      </select>
                    </template>

                    <!-- Overseerr Default Radarr Quality Profile ID Dropdown -->
                    <template v-else-if="groupName === 'overseerr' && settingName === 'default_radarr_quality_profile_id'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model.number="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingRadarrProfiles"
                      >
                        <option :value="null">
                          {{ loadingRadarrProfiles ? 'Loading profiles...' : 'Default' }}
                        </option>
                        <option v-for="profile in radarrQualityProfiles" :key="profile.id" :value="profile.id">
                          {{ profile.name }}
                        </option>
                      </select>
                    </template>

                    <!-- Overseerr Default Sonarr Quality Profile ID Dropdown -->
                    <template v-else-if="groupName === 'overseerr' && settingName === 'default_sonarr_quality_profile_id'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model.number="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingSonarrProfiles"
                      >
                        <option :value="null">
                          {{ loadingSonarrProfiles ? 'Loading profiles...' : 'Default' }}
                        </option>
                        <option v-for="profile in sonarrQualityProfiles" :key="profile.id" :value="profile.id">
                          {{ profile.name }}
                        </option>
                      </select>
                    </template>

                    <!-- Overseerr Default User Dropdown -->
                    <template v-else-if="groupName === 'overseerr' && settingName === 'default_user'">
                      <select
                        :id="groupName + '-' + settingName"
                        v-model="settingDetails.value"
                        @change="updateSetting(groupName, settingName)"
                        class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                        :disabled="loadingOverseerrUsers"
                      >
                        <option :value="null">
                          {{ loadingOverseerrUsers ? 'Loading users...' : 'Select a user...' }}
                        </option>
                        <option v-for="user in overseerrUsers" :key="user.id" :value="user.displayName">
                          {{ user.displayName }}
                        </option>
                      </select>
                    </template>
                    <!-- Other input types -->
                    <input v-else-if="isNumberType(settingDetails.value) && typeof settingDetails.value !== 'undefined' && settingDetails.value !== null" :id="groupName + '-' + settingName" v-model.number="settingDetails.value" @change="updateSetting(groupName, settingName)" type="number" class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500">
                    <input v-else-if="isBooleanType(settingDetails.value) && typeof settingDetails.value !== 'undefined'" :id="groupName + '-' + settingName" v-model="settingDetails.value" @change="updateSetting(groupName, settingName)" type="checkbox" :disabled="settingName === 'enabled' && !isProviderConfigured(groupName)" class="w-6 h-6 mx-2 bg-black border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 cursor-pointer">
                    <input v-else :id="groupName + '-' + settingName" v-model="settingDetails.value" @change="updateSetting(groupName, settingName)" :type="settingName.includes('key') || settingName.includes('token') ? 'password' : 'text'" class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500" :placeholder="getPlaceholder(groupName, settingName)">
                    <div v-if="settingName === 'enabled' && !isProviderConfigured(groupName)" class="mt-1 text-xs text-yellow-400">
                      *Required fields are missing
                    </div>
                    <div class="mt-1 text-sm text-gray-500">
                      {{ settingDetails.description }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <!-- LLM Provider Settings Section -->
        <div id="section-llm-provider-settings" class="mt-8">
          <h2 class="text-2xl text-white font-semibold mb-6">LLM Provider Settings</h2>
          <div class="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6 text-sm text-gray-400 text-center">
            <p>Configure your LLM providers.</p>
            <p>Ensure URLs are correct and API keys are provided for enabled services.</p>
            <p>Note: Only one LLM provider can be enabled at a time.</p>
            <!-- Add more specific library provider instructions here -->
          </div>
          <div v-if="Object.keys(llmProviderSettings).length > 0" class="space-y-8">
            <div v-for="(groupSettings, groupName) in llmProviderSettings" :key="groupName" :id="`section-settings-${groupName}`" class="bg-gray-900 rounded-lg p-6 shadow-md">
            <h3 class="text-xl text-white font-medium mb-4 capitalize">{{ groupName }}</h3>

            <div class="space-y-4">
              <div v-for="(settingDetails, settingName) in groupSettings" :key="settingName" class="flex flex-col">
                <div v-if="settingDetails.show != false">
                  <label :for="groupName + '-' + settingName" class="text-gray-400 pb-4 capitalize">
                    {{ settingName.replace(/_/g, ' ') }}
                    <span v-if="settingDetails.required" class="text-red-500 ml-1">*</span>
                  </label>

                  <!-- Gemini Model Dropdown -->
                  <template v-if="groupName === 'gemini' && (settingName === 'model' || settingName === 'embedding_model')">
                    <select
                      :id="groupName + '-' + settingName"
                      v-model="settingDetails.value"
                      @change="updateSetting(groupName, settingName)"
                      class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                      :disabled="loadingLlmModels"
                    >
                      <option :value="null">
                        {{ loadingLlmModels ? 'Loading models...' : (geminiModels.length === 0 ? 'No models available' : 'Select a model...') }}
                      </option>
                      <option v-for="modelName in geminiModels" :key="modelName" :value="modelName">
                        {{ modelName }}
                      </option>
                    </select>
                  </template>

                  <!-- OpenAI Model Dropdown -->
                  <template v-else-if="groupName === 'openai' && (settingName === 'model' || settingName === 'embedding_model')">
                    <select
                      :id="groupName + '-' + settingName"
                      v-model="settingDetails.value"
                      @change="updateSetting(groupName, settingName)"
                      class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                      :disabled="loadingLlmModels"
                    >
                      <option :value="null">
                        {{ loadingLlmModels ? 'Loading models...' : (openaiModels.length === 0 ? 'No models available' : 'Select a model...') }}
                      </option>
                      <option v-for="modelName in openaiModels" :key="modelName" :value="modelName">
                        {{ modelName }}
                      </option>
                    </select>
                  </template>

                  <!-- Ollama Model Dropdown -->
                  <template v-else-if="groupName === 'ollama' && settingName === 'model'">
                    <select
                      :id="groupName + '-' + settingName"
                      v-model="settingDetails.value"
                      @change="updateSetting(groupName, settingName)"
                      class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                      :disabled="loadingLlmModels"
                    >
                      <option :value="null">
                        {{ loadingLlmModels ? 'Loading models...' : (ollamaModels.length === 0 ? 'No models available (is Ollama enabled?)' : 'Select a model...') }}
                      </option>
                      <option v-for="modelName in ollamaModels" :key="modelName" :value="modelName">
                        {{ modelName }}
                      </option>
                    </select>
                  </template>

                  <!-- Other input types -->
                  <input             
                    v-else-if="isNumberType(settingDetails.value) && typeof settingDetails.value !== 'undefined' && settingDetails.value !== null"
                    :id="groupName + '-' + settingName"
                    v-model.number="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    type="number"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                  >
                  <input
                    v-else-if="isBooleanType(settingDetails.value) && typeof settingDetails.value !== 'undefined'"
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    type="checkbox"
                    :disabled="settingName === 'enabled' && !isProviderConfigured(groupName)"
                    class="w-6 h-6 mx-2 bg-black border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 cursor-pointer"
                  >
                  <input
                    v-else
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    :type="settingName.includes('key') || settingName.includes('token') ? 'password' : 'text'"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :placeholder="getPlaceholder(groupName, settingName)"
                  >
                  
                  <div v-if="settingName === 'enabled' && !isProviderConfigured(groupName)" class="mt-1 text-xs text-yellow-400">
                    *Required fields are missing
                  </div>
                  <div class="mt-1 text-sm text-gray-500">
                    {{ settingDetails.description }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        </div>
        </div>
      </div>
    </main>
  </div>
  <!-- Trakt Authentication Modal -->
  <div v-if="showTraktAuthModal" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
    <div class="bg-gray-800 p-6 rounded-lg shadow-xl max-w-md w-full">
      <h3 class="text-xl font-semibold text-white mb-4">Trakt Authentication</h3>
      <div v-if="traktAuthLoading" class="text-center text-gray-300">
        <p>Contacting Trakt...</p>
        <!-- Optional: Add a spinner here -->
      </div>
      <div v-else-if="traktAuthError" class="text-red-400 mb-4">
        <p><strong>Error:</strong> {{ traktAuthError }}</p>
        <p>Please check the server logs for more details and try again if applicable.</p>
      </div>
      <div v-else-if="traktAuthDetails.user_code && traktAuthDetails.verification_url">
        <p class="text-gray-300 mb-2">
          To complete Trakt authentication, please go to:
        </p>
        <a :href="traktAuthDetails.verification_url" target="_blank" class="text-discovarr hover:underline font-semibold block text-center py-2 px-3 bg-gray-700 rounded-md mb-4">
          {{ traktAuthDetails.verification_url }}
        </a>
        <p class="text-gray-300 mb-2">And enter the code:</p>
        <p class="text-2xl font-bold text-white text-center bg-gray-700 p-3 rounded-md mb-4 tracking-widest">
          {{ traktAuthDetails.user_code }}
        </p>
        <p v-if="traktAuthDetails.message" class="text-sm text-gray-400 mt-3">{{ traktAuthDetails.message }}</p>
      </div>
      <div class="mt-6 flex justify-end">
        <button @click="showTraktAuthModal = false" class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none">Close</button>
      </div>
    </div>
  </div>
</template>
