// src/stores/settings.js
import { defineStore } from 'pinia';
import { ref } from 'vue';
import { config } from '../config'; // Assuming your API URL config is here

export const useSettingsStore = defineStore('settings', () => {
  // State
  const allSettings = ref({}); // Store settings as an object: { settingName: settingObject, ... }
  const isLoading = ref(false);
  const error = ref(null);

  // Actions
  async function fetchSettings() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await fetch(`${config.apiUrl}/settings`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(`Failed to fetch settings: ${response.status} ${errorData.message || ''}`);
      }
      const settingsArray = await response.json(); // Assuming API returns an array of setting objects
      
      allSettings.value = settingsArray
      // Transform the array into an object keyed by setting name for easier access
      // allSettings.value = settingsArray.reduce((acc, setting) => {
      // acc[setting.name] = setting; // Store the whole setting object
      //  return acc;
      //}, {});

      console.log('Settings fetched successfully:', allSettings.value);

    } catch (e) {
      console.error('Error fetching settings:', e);
      error.value = e.message || 'An unknown error occurred while fetching settings.';
      allSettings.value = {}; // Reset or keep stale data, depending on preference
    } finally {
      isLoading.value = false;
    }
  }

  // Getters (optional, but can be useful)
  // Example: Get a specific setting's value
  function getSettingValue(group, name, defaultValue = null) {
    return allSettings.value[group]?.[name]?.value ?? defaultValue;
  }

  return {
    allSettings,
    isLoading,
    error,
    fetchSettings,
    getSettingValue
  };
});
