<script setup>
import { ref, watch } from 'vue';
import { config } from '../config';
import { useToastStore } from '@/stores/toast';
const toastStore = useToastStore();

const props = defineProps({
  show: Boolean,
  media: Object
});

const emit = defineEmits(['close', 'request-complete']);

const profiles = ref([]);
const selectedProfile = ref('');
const requesting = ref(false);
const saveAsDefault = ref(false); // New ref for the checkbox

// Reset selected profile when modal closes
watch(() => props.show, (newValue) => {
  if (!newValue) {
    selectedProfile.value = '';
    saveAsDefault.value = false; // Reset checkbox on close
  }
});

// Fetch profiles when modal opens and media type is available
watch(
  [() => props.show, () => props.media?.media_type],
  async ([showValue, mediaType]) => {
    if (showValue && mediaType) {
      try {
        console.log('Fetching profiles for media type:', mediaType);
        const response = await fetch(`${config.apiUrl}/quality-profiles/${mediaType}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Received profiles:', data);
        profiles.value = data;
        
        // Set default profile based on is_default flag, or first available profile
        const defaultProfile = data.find(p => p.is_default === true);
        if (defaultProfile) {
          console.log('Setting default profile (from is_default):', defaultProfile.name);
          selectedProfile.value = defaultProfile.id;
        } else if (data.length > 0) {
          console.log('No profile marked as default, using first available profile:', data[0].name);
          selectedProfile.value = data[0].id;
        }
      } catch (error) {
        console.error('Error fetching quality profiles:', error);
        profiles.value = [];
      }
    }
  },
  { immediate: true }
);

// In RequestModal.vue
const handleRequest = async () => {
  if (!selectedProfile.value || !props.media?.tmdb_id || !props.media?.media_type) {
    console.error('Missing required data:', {
      profile: selectedProfile.value,
      tmdb_id: props.media?.tmdb_id,
      media_type: props.media?.media_type
    });
    return;
  }
  
  requesting.value = true;
  try {
    const requestPayload = {
      media_type: props.media.media_type,
      quality_profile_id: selectedProfile.value ? parseInt(selectedProfile.value) : null, // Ensure it's an int or null
      save_default: saveAsDefault.value
    };

    console.log('Sending POST request with payload:', requestPayload);
    
    const response = await fetch(
      `${config.apiUrl}/request/${props.media.tmdb_id}/${props.media.title}`, // No query params here
      { 
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestPayload) // Send data in the body
      }
    );
    
    if (!response.ok) {
      const errorText = await response.text(); // Get error text for better debugging
      toastStore.show(`Failed to request media: ${response.status} ${response.statusText} - ${errorText}`, "error");
    } else {
      const result = await response.json();
      console.log('Request successful:', result);
      toastStore.show(`Successfully requested ${props.media.title}`);
    }
    
    emit('request-complete');
    emit('close');
  } catch (error) {
    console.error('Error requesting media:', error);
    alert(`Failed to request media. ${error.message}`);
  } finally {
    requesting.value = false;
  }
};

</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 bg-black bg-opacity-75 flex items-center justify-center">
    <div class="bg-gray-900 p-8 rounded-lg w-full max-w-md">
      <h2 class="text-2xl text-white mb-6">Request Media</h2>
      
      <div class="mb-4">
        <label class="block text-gray-400 mb-2">Title</label>
        <div class="text-white">{{ media.title }}</div>
      </div>

      <div class="mb-4">
        <label class="block text-gray-400 mb-2">Type</label>
        <div class="text-white">{{ media.media_type }}</div>
      </div>

      <div class="mb-4">
        <label class="block text-gray-400 mb-2">Quality Profile</label>
        <select 
          v-model="selectedProfile"
          class="w-full p-2 bg-black text-white border border-gray-700 rounded focus:outline-none focus:border-red-500"
        >
          <option value="">Select a profile...</option>
          <option 
            v-for="profile in profiles" 
            :key="profile.id" 
            :value="profile.id"
          >
            {{ profile.name }}
          </option>
        </select>
      </div>

      <div class="mb-6">
        <label class="flex items-center text-gray-400">
          <input 
            type="checkbox" 
            v-model="saveAsDefault"
            class="mr-2 h-5 w-5 bg-black border-gray-700 rounded text-red-600 focus:ring-red-500"
          />
          Save as default quality profile for {{ media.media_type === 'tv' ? 'Sonarr' : 'Radarr' }}
        </label>
      </div>
      <div class="flex justify-end gap-4">
        <button
          type="button"
          @click="$emit('close')"
          class="px-4 py-2 text-white hover:bg-gray-700 rounded"
        >
          Cancel
        </button>
        <button
          type="button"
          @click="handleRequest"
          :disabled="!selectedProfile || requesting"
          class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          {{ requesting ? 'Requesting...' : 'Request' }}
        </button>
      </div>
    </div>
  </div>
</template>

