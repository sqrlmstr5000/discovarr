<script setup>
import { ref, onMounted, watch } from 'vue'
import { useToastStore } from '@/stores/toast'; // Import the toast store
import { config } from '../config'

const settings = ref(null)
const radarrQualityProfiles = ref([])
const loadingRadarrProfiles = ref(false)
const sonarrQualityProfiles = ref([])
const loadingSonarrProfiles = ref(false)
const geminiModels = ref([]);
const ollamaModels = ref([]);
const loadingOllamaModels = ref(false);
const loadingGeminiModels = ref(false);
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

// Helper functions for type checking
const isNumberType = (value) => typeof value === 'number'
const isBooleanType = (value) => typeof value === 'boolean'

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

// Load Gemini models
const fetchGeminiModels = async () => {
  // Check if Gemini API key is set before fetching models
  if (!settings.value || !settings.value.gemini || !settings.value.gemini.api_key || !settings.value.gemini.api_key.value) {
    console.log('Gemini API key not set. Skipping fetching models.');
    geminiModels.value = []; // Ensure models list is empty
    loadingGeminiModels.value = false;
    return;
  }
  loadingGeminiModels.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/gemini/models`);
    if (!response.ok) throw new Error('Failed to load Gemini models');
    geminiModels.value = await response.json();
  } catch (error) {
    console.error('Error loading Gemini models:', error);
    geminiModels.value = []; // Set to empty array on error
  } finally {
    loadingGeminiModels.value = false;
  }
};

// Load Ollama models
const fetchOllamaModels = async () => {
  // Check if Ollama is enabled before fetching models
  if (!settings.value || !settings.value.ollama || !settings.value.ollama.enabled || !settings.value.ollama.enabled.value) {
    console.log('Ollama is not enabled. Skipping fetching models.');
    ollamaModels.value = []; // Ensure models list is empty
    loadingOllamaModels.value = false;
    return;
  }
  loadingOllamaModels.value = true;
  try {
    const response = await fetch(`${config.apiUrl}/ollama/models`);
    if (!response.ok) throw new Error('Failed to load Ollama models');
    ollamaModels.value = await response.json();
  } catch (error) {
    console.error('Error loading Ollama models:', error);
    ollamaModels.value = []; // Set to empty array on error
  } finally {
    loadingOllamaModels.value = false;
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
  if (settings.value[group][name].value === originalValues[group][name].value) {
    return
  }

  let valueToSave = settings.value[group][name].value;

  // Validation: Prevent enabling both Gemini and Ollama simultaneously
  if (name === 'enabled' && valueToSave === true) { // Check if trying to enable a setting
    if (group === 'gemini') {
      // Trying to enable Gemini, check if Ollama is already enabled
      if (settings.value.ollama && settings.value.ollama.enabled && settings.value.ollama.enabled.value === true) {
        toastStore.show('Cannot enable Gemini while Ollama is enabled. Please disable Ollama first.', 'error');
        settings.value[group][name].value = originalValues[group][name].value; // Revert UI change
        return;
      }
    } else if (group === 'ollama') {
      // Trying to enable Ollama, check if Gemini is already enabled
      if (settings.value.gemini && settings.value.gemini.enabled && settings.value.gemini.enabled.value === true) {
        toastStore.show('Cannot enable Ollama while Gemini is enabled. Please disable Gemini first.', 'error');
        settings.value[group][name].value = originalValues[group][name].value; // Revert UI change
        return;
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
    
    const successfullyUpdatedValue = settings.value[group][name].value;
    // Update original value after successful save
    originalValues[group][name].value = successfullyUpdatedValue;

    // If Gemini or Ollama was just enabled, fetch their models
    if (name === 'enabled' && successfullyUpdatedValue === true) {
      if (group === 'gemini') {
        await fetchGeminiModels();
      } else if (group === 'ollama') {
        await fetchOllamaModels();
      } else if (group === 'trakt' && name === 'enabled' && successfullyUpdatedValue === true) {
        // If Trakt was just enabled, trigger authentication
        toastStore.show('Trakt enabled. Please follow the authentication instructions.', 'info');
        await traktAuthenticate();
      }
    }
    // Optionally, show a success toast here if desired
  } catch (error) {
    console.error('Error updating setting:', error)
    // Revert to original value on error
    settings.value[group][name].value = originalValues[group][name].value
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

onMounted(async () => { // Make onMounted async
  await loadSettings(); // Await the loading of settings
  fetchRadarrQualityProfiles();
  fetchSonarrQualityProfiles();
  fetchGeminiModels(); // Now this will run after settings are loaded
  fetchOllamaModels(); // Fetch Ollama models
  await fetchUsers(); // Fetch users
  updateDatesFromRange(); // Initialize dates based on default selectedRange and fetch
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
          <li v-if="settings" class="pt-3 mt-3 border-t border-gray-700">
            <a href="#section-application-settings" class="text-sm font-semibold text-gray-500 hover:text-amber-400 block mb-2">Application Settings</a>
            <ul class="space-y-1">
              <li v-for="(groupSettings, groupName) in settings" :key="`toc-${groupName}`">
                <a :href="`#section-settings-${groupName}`" class="hover:text-amber-400 block capitalize pl-3 py-0.5 text-sm">
                  {{ groupName.replace(/_/g, ' ') }}
                </a>
              </li>
            </ul>
          </li>
        </ul>
      </nav>
    </aside>

    <!-- Scrollable Main Content Area -->
    <main class="flex-1 overflow-y-auto"> <!-- Removed ml-64 -->
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

        <!-- Settings Section -->
        <div id="section-application-settings">
          <h2 class="text-2xl text-white font-semibold mb-6">Application Settings</h2>
        </div>
        
        <!-- Settings groups -->
        <div v-if="settings" class="space-y-8">
          <div v-for="(groupSettings, groupName) in settings" :key="groupName" :id="`section-settings-${groupName}`" class="bg-gray-900 rounded-lg p-6 shadow-md">
            <h3 class="text-xl text-white font-medium mb-4 capitalize">{{ groupName }}</h3>

            <div class="space-y-4">
              <div v-for="(settingDetails, settingName) in groupSettings" :key="settingName" class="flex flex-col">
                <label :for="groupName + '-' + settingName" class="text-gray-400 mb-1 capitalize">
                  {{ settingName.replace(/_/g, ' ') }}
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
                      {{ loadingRadarrProfiles ? 'Loading profiles...' : 'Select a profile...' }}
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
                      {{ loadingSonarrProfiles ? 'Loading profiles...' : 'Select a profile...' }}
                    </option>
                    <option v-for="profile in sonarrQualityProfiles" :key="profile.id" :value="profile.id">
                      {{ profile.name }}
                    </option>
                  </select>
                </template>

                <!-- Gemini Model Dropdown -->
                <template v-else-if="groupName === 'gemini' && settingName === 'model'">
                  <select
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :disabled="loadingGeminiModels"
                  >
                    <option :value="null">
                      {{ loadingGeminiModels ? 'Loading models...' : (geminiModels.length === 0 ? 'No models available' : 'Select a model...') }}
                    </option>
                    <option v-for="modelName in geminiModels" :key="modelName" :value="modelName">
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
                    :disabled="loadingOllamaModels"
                  >
                    <option :value="null">
                      {{ loadingOllamaModels ? 'Loading models...' : (ollamaModels.length === 0 ? 'No models available (is Ollama enabled?)' : 'Select a model...') }}
                    </option>
                    <option v-for="modelName in ollamaModels" :key="modelName" :value="modelName">
                      {{ modelName }}
                    </option>
                  </select>
                </template>

                <!-- Textarea for specific settings like default_prompt -->
                <div v-else-if="groupName === 'app' && settingName === 'default_prompt'">
                  <textarea
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 min-h-[80px] resize-y"
                    rows="5"
                    :placeholder="getPlaceholder(groupName, settingName)"
                  ></textarea>
                  <div>Supported template variables: 
                    <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">limit</span>
                    <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">media_name</span>
                    <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">media_exclude</span>
                  </div>
                </div>  

                <!-- Plex Default User Dropdown -->
                <template v-else-if="groupName === 'plex' && settingName === 'default_user'">
                  <select
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :disabled="loadingUsers"
                  >
                    <option :value="null">
                      {{ loadingUsers ? 'Loading users...' : (users.length === 0 ? 'No users available in system' : 'None (System Default)') }}
                    </option>
                    <option v-for="user in users.filter(u => u.source_provider === groupName)" :key="user.id" :value="user.id">
                      {{ user.name }}
                    </option>
                  </select>
                </template>

                <!-- Jellyfin Default User Dropdown -->
                <template v-else-if="groupName === 'jellyfin' && settingName === 'default_user'">
                  <select
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :disabled="loadingUsers"
                  >
                    <option :value="null">
                      {{ loadingUsers ? 'Loading users...' : (users.length === 0 ? 'No users available in system' : 'None (System Default)') }}
                    </option>
                    <option v-for="user in users.filter(u => u.source_provider === groupName)" :key="user.id" :value="user.id">
                      {{ user.name }}
                    </option>
                  </select>
                </template>

                <!-- Trakt Default User Dropdown -->
                <template v-else-if="groupName === 'trakt' && settingName === 'default_user'">
                  <select
                    :id="groupName + '-' + settingName"
                    v-model="settingDetails.value"
                    @change="updateSetting(groupName, settingName)"
                    class="w-full p-2 bg-black text-white border border-gray-700 rounded-lg focus:outline-none focus:border-red-500"
                    :disabled="loadingUsers"
                  >
                    <option :value="null">
                      {{ loadingUsers ? 'Loading users...' : (users.length === 0 ? 'No users available in system' : 'None (System Default)') }}
                    </option>
                    <option v-for="user in users.filter(u => u.source_provider === groupName)" :key="user.id" :value="user.id">
                      {{ user.name }}
                    </option>
                  </select>
                </template>

                <!-- Textarea for specific settings like default_prompt -->
                <div v-else-if="groupName === 'app' && (settingName === 'system_prompt')">
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
                  class="w-6 h-6 bg-black border border-gray-700 rounded-lg focus:outline-none focus:border-red-500 cursor-pointer"
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
