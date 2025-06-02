<template>
  <!-- Modal Overlay -->
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="closeModal">
    <!-- Modal Content -->
    <div class="bg-gray-800 p-6 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      <h3 class="text-white text-xl mb-4">Edit Search Schedule</h3>
      
      <div class="space-y-4">
        <div class="flex items-center mb-4">
      <input
        v-model="form.isScheduled"
        type="checkbox"
        id="scheduleSearchModal"
        class="mr-2 h-4 w-4 accent-aiarr"
        :disabled="isDefaultSearch"
      />
      <label for="scheduleSearchModal" class="text-gray-300 cursor-pointer">Schedule this search</label>
    </div>

    <div v-if="form.isScheduled" class="space-y-4 p-4 bg-gray-700/30 rounded-lg">
      <div class="flex items-center">
        <input
          v-model="form.enabled"
          type="checkbox"
          id="scheduleEnabledModal"
          class="mr-2 h-4 w-4 accent-aiarr"
        />
        <label for="scheduleEnabledModal" class="text-gray-300 cursor-pointer">Enable this schedule</label>
      </div>
      <div class="grid grid-cols-3 sm:grid-cols-6 gap-3">
        <div>
          <label class="block text-gray-400 text-sm mb-1">Minute</label>
          <input
            v-model="form.minute"
            placeholder="*"
            title="Minute (0-59)"
            class="w-full p-2 bg-black text-white border border-gray-600 rounded-md focus:outline-none focus:border-aiarr text-sm"
          />
        </div>
        <div>
          <label class="block text-gray-400 text-sm mb-1">Hour</label>
          <input
            v-model="form.hour"
            placeholder="*"
            title="Hour (0-23)"
            class="w-full p-2 bg-black text-white border border-gray-600 rounded-md focus:outline-none focus:border-aiarr text-sm"
          />
        </div>
        <div>
          <label class="block text-gray-400 text-sm mb-1">Day</label>
          <input
            v-model="form.day"
            placeholder="*"
            title="Day of Month (1-31)"
            class="w-full p-2 bg-black text-white border border-gray-600 rounded-md focus:outline-none focus:border-aiarr text-sm"
          />
        </div>
        <div>
          <label class="block text-gray-400 text-sm mb-1">Month</label>
          <input
            v-model="form.month"
            placeholder="*"
            title="Month (1-12 or JAN-DEC)"
            class="w-full p-2 bg-black text-white border border-gray-600 rounded-md focus:outline-none focus:border-aiarr text-sm"
          />
        </div>
        <div>
          <label class="block text-gray-400 text-sm mb-1">DOW</label>
          <input
            v-model="form.dayOfWeek"
            placeholder="*"
            title="Day of Week (0-6 or SUN-SAT)"
            class="w-full p-2 bg-black text-white border border-gray-600 rounded-md focus:outline-none focus:border-aiarr text-sm"
          />
        </div>
        <div>
          <label class="block text-gray-400 text-sm mb-1">Year</label>
          <input
            v-model="form.year"
            placeholder="*"
            title="Year (e.g., 2024)"
            class="w-full p-2 bg-black text-white border border-gray-600 rounded-md focus:outline-none focus:border-aiarr text-sm"
          />
        </div>
      </div>

      <!-- Quick Schedules -->
      <div class="mb-4">
        <p class="text-gray-300 text-sm mb-2">Quick Schedules:</p>
        <div class="flex flex-wrap gap-2">
          <button
              type="button"
              @click="applyQuickSchedule({ minute: 0, hour: 0, day: '*', dayOfWeek: '*', month: '*', year: '*' })"
              class="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded-full hover:bg-gray-500 focus:outline-none"
            >Daily at Midnight</button>
            <button
              type="button"
              @click="applyQuickSchedule({ minute: 0, hour: 3, day: '*', dayOfWeek: 'sun', month: '*', year: '*' })"
              class="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded-full hover:bg-gray-500 focus:outline-none"
            >Every Sunday at 3 AM</button>
            <button
              type="button"
              @click="applyQuickSchedule({ minute: 0, hour: '*', day: '*', dayOfWeek: '*', month: '*', year: '*' })"
              class="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded-full hover:bg-gray-500 focus:outline-none"
            >Hourly (Top of hour)</button>
            <button
              type="button"
              @click="applyQuickSchedule({ minute: 0, hour: 9, day: '*', dayOfWeek: 'mon-fri', month: '*', year: '*' })"
              class="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded-full hover:bg-gray-500 focus:outline-none"
            >Weekdays at 9 AM (Mon)</button>
            <button
              type="button"
              @click="applyQuickSchedule({ minute: 0, hour: 0, day: '1-7', dayOfWeek: 'sun', month: '*', year: '*' })"
              class="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded-full hover:bg-gray-500 focus:outline-none"
            >First Sunday of the Month</button>
        </div>
      </div>
    </div>

    <div v-if="form.isScheduled" class="mt-4">
      <button type="button" @click="showCronInfo = !showCronInfo" class="text-gray-400 hover:text-white focus:outline-none flex items-center mb-2 text-sm">
        Cron Schedule Reference
        <ChevronDown v-if="!showCronInfo" class="ml-1" :size="18" />
        <ChevronUp v-if="showCronInfo" class="ml-1" :size="18" />
      </button>
      <div v-if="showCronInfo" class="overflow-x-auto text-xs">
        <table class="w-full text-sm text-left text-gray-400">
            <thead class="text-xs uppercase bg-gray-700">
              <tr>
                <th scope="col" class="px-4 py-2">Field</th>
                <th scope="col" class="px-4 py-2">Required</th>
                <th scope="col" class="px-4 py-2">Values</th>
                <th scope="col" class="px-4 py-2 relative">
                  Special Characters
                  <button
                    ref="tooltipToggleButtonRef"
                    @click="toggleSpecialCharTooltip"
                    type="button"
                    class="ml-1 text-gray-400 hover:text-white align-middle focus:outline-none"
                    aria-label="Show special character reference"
                  >
                    <InformationOutline :size="16" />
                  </button>
                  <div
                    v-if="showSpecialCharTooltip"
                    ref="specialCharTooltipRef"
                    class="absolute z-30 mt-2 p-3 bg-gray-900 border border-gray-700 rounded-md shadow-lg text-xs left-1/2 transform -translate-x-1/2 min-w-[300px] md:min-w-[350px] max-w-sm text-left"
                    style="top: 100%;"
                  >
                    <h4 class="text-sm font-semibold text-white mb-2">Special Character Reference</h4>
                    <ul class="space-y-1 text-gray-300">
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">*</code>: Any value (wildcard)</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">,</code>: Value list separator</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">-</code>: Range of values</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">/</code>: Step values</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">?</code>: No specific value</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">L</code>: Last day (month/week)</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">W</code>: Weekday</li>
                      <li><code class="font-mono bg-gray-600 text-gray-100 px-1.5 py-0.5 mr-1 rounded-md">#</code>: Nth weekday in month</li>
                    </ul>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
              <tr class="bg-gray-800 hover:bg-gray-700">
                <td class="px-4 py-2">minute</td>
                <td class="px-4 py-2">Yes</td>
                <td class="px-4 py-2">0-59</td>
                <td class="px-4 py-2 font-mono">* , - /</td>
              </tr>
              <tr class="bg-gray-800 hover:bg-gray-700">
                <td class="px-4 py-2">hour</td>
                <td class="px-4 py-2">Yes</td>
                <td class="px-4 py-2">0-23</td>
                <td class="px-4 py-2 font-mono">* , - /</td>
              </tr>
              <tr class="bg-gray-800 hover:bg-gray-700">
                <td class="px-4 py-2">day</td>
                <td class="px-4 py-2">Yes</td>
                <td class="px-4 py-2">1-31</td>
                <td class="px-4 py-2 font-mono">* , - / ? L W</td>
              </tr>
              <tr class="bg-gray-800 hover:bg-gray-700">
                <td class="px-4 py-2">month</td>
                <td class="px-4 py-2">Yes</td>
                <td class="px-4 py-2">1-12 or jan-dec</td>
                <td class="px-4 py-2 font-mono">* , - /</td>
              </tr>
              <tr class="bg-gray-800 hover:bg-gray-700">
                <td class="px-4 py-2">day of week</td>
                <td class="px-4 py-2">Yes</td>
                <td class="px-4 py-2">0-6 or mon-sun</td>
                <td class="px-4 py-2 font-mono">* , - / ? L #</td>
              </tr>
              <tr class="bg-gray-800 hover:bg-gray-700">
                <td class="px-4 py-2">year</td>
                <td class="px-4 py-2">No</td>
                <td class="px-4 py-2">4-digit year</td>
                <td class="px-4 py-2 font-mono">* , - /</td>
              </tr>
            </tbody>
          </table>
      </div>
    </div>
      </div>

      <!-- Modal Footer -->
      <div class="flex justify-end gap-4 mt-6">
        <button
          type="button"
          @click="closeModal"
          class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none"
        >
          Cancel
        </button>
        <button
          type="button"
          @click="handleSaveSchedule"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="saving"
        >
          {{ saving ? 'Saving...' : 'Save Schedule' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onBeforeUnmount } from 'vue';
import { config } from '../config';
import ChevronDown from 'vue-material-design-icons/ChevronDown.vue';
import ChevronUp from 'vue-material-design-icons/ChevronUp.vue';
import InformationOutline from 'vue-material-design-icons/InformationOutline.vue';
import { useToastStore } from '@/stores/toast';

const props = defineProps({
  searchId: [String, Number, null],
  prompt: {
    type: String,
    required: true,
  },
  isDefaultSearch: {
    type: Boolean,
    default: false,
  }
});

const toastStore = useToastStore();
const saving = ref(false); // Local saving state for the modal

const form = reactive({
  isScheduled: false,
  minute: '*',
  hour: '*',
  day: '*',
  dayOfWeek: '*',
  month: '*',
  year: '*',
  enabled: true,
});

const showCronInfo = ref(false);
const showSpecialCharTooltip = ref(false);

const emit = defineEmits(['close', 'save']); // Emit events to parent

const handleEscapeKey = (event) => {
  if (event.key === 'Escape') {
    closeModal();
  }
};

onMounted(() => {
  document.addEventListener('keydown', handleEscapeKey);
});
onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEscapeKey);
});

const fetchScheduleData = async (id) => {
  if (!id) {
    // Reset form for new search or if ID becomes null
    form.isScheduled = false;
    form.minute = '*';
    form.hour = '*';
    form.day = '*';
    form.dayOfWeek = '*';
    form.month = '*';
    form.year = '*';
    form.enabled = true;
    return;
  }
  try {
    const response = await fetch(`${config.apiUrl}/schedule/search/${id}`);
    if (response.ok) {
      const schedule = await response.json();
      if (schedule) {
        form.isScheduled = true; // If schedule data exists, check the box
        form.minute = (schedule.minute !== null && schedule.minute !== undefined) ? String(schedule.minute) : '*';
        form.hour = (schedule.hour !== null && schedule.hour !== undefined) ? String(schedule.hour) : '*';
        form.day = (schedule.day !== null && schedule.day !== undefined) ? String(schedule.day) : '*';
        form.dayOfWeek = (schedule.day_of_week !== null && schedule.day_of_week !== undefined) ? String(schedule.day_of_week) : '*';
        form.month = (schedule.month !== null && schedule.month !== undefined) ? String(schedule.month) : '*';
        form.year = (schedule.year !== null && schedule.year !== undefined) ? String(schedule.year) : '*';
        form.enabled = schedule.enabled !== undefined ? schedule.enabled : true;
      } else {
        form.isScheduled = false; // No schedule found
        form.enabled = true; // Default to true
      }
    } else if (response.status === 404) {
        form.isScheduled = false; // No schedule found
        form.enabled = true;
    } else {
      toastStore.show('Failed to fetch schedule data.', 'error');
    }
  } catch (error) {
    console.error('Failed to fetch schedule:', error);
    toastStore.show(`Error fetching schedule: ${error.message}`, 'error');
  }
};

watch(() => props.searchId, (newId) => {
  fetchScheduleData(newId);
}, { immediate: true });

const applyQuickSchedule = (scheduleValues) => {
  form.isScheduled = true; // Enable scheduling when a quick schedule is applied
  form.minute = scheduleValues.minute;
  form.hour = scheduleValues.hour;
  form.day = scheduleValues.day;
  form.dayOfWeek = scheduleValues.dayOfWeek;
  form.month = scheduleValues.month;
  form.year = scheduleValues.year;
  form.enabled = true; // Default to enabled
};

// This function is now internal to the modal
const saveOrUpdateSchedule = async (effectiveSearchId) => {
  if (!effectiveSearchId) {
    // This case should ideally be handled by the parent,
    // ensuring a searchId exists before calling this.
    // If called for a new search that hasn't been saved yet,
    // we can't save a schedule.
    if (form.isScheduled) {
        console.warn("Attempted to save schedule for a new search that hasn't been saved yet. Schedule not saved.");
        toastStore.show("Save the search first to enable scheduling.", "info");
    }
    return; // Or throw an error
  }

  if (form.isScheduled) {
    saving.value = true;
    // Save or Update schedule
    const payload = {
      prompt: props.prompt, // Use the prompt passed from parent
      hour: form.hour,
      minute: form.minute,
      day: form.day,
      day_of_week: form.dayOfWeek,
      year: form.year,
      month: form.month,
      enabled: form.enabled,
    };
    const response = await fetch(`${config.apiUrl}/schedule/search/${effectiveSearchId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      toastStore.show('Failed to save or update schedule');
    }
    toastStore.show('Schedule updated successfully.', 'success');
  } else {
    // Delete schedule if it exists
    const response = await fetch(`${config.apiUrl}/schedule/search/${effectiveSearchId}`, {
      method: 'DELETE',
    });
    if (!response.ok && response.status !== 404) { // 404 is ok if schedule didn't exist
      throw new Error('Failed to delete schedule');
    }
    if (response.ok && response.status !== 404) { // Only show if it was actually deleted
        toastStore.show('Schedule removed successfully.', 'success');
    }
  }
  saving.value = false;
};

// Method called by the Save button in the modal footer
const handleSaveSchedule = async () => {
  if (!props.searchId) {
    // This modal should only be opened for existing searches with an ID
    toastStore.show("Cannot save schedule for a search without an ID.", "error");
    return;
  }
  try {
    await saveOrUpdateSchedule(props.searchId);
    emit('save'); // Notify parent that schedule was saved
    closeModal(); // Close the modal
  } catch (error) {
    console.error("Error saving schedule:", error);
    toastStore.show(`Error saving schedule: ${error.message || 'Please try again.'}`, 'error');
  }
};

const toggleSpecialCharTooltip = () => {
  showSpecialCharTooltip.value = !showSpecialCharTooltip.value;
};

// Method to close the modal
const closeModal = () => {
  emit('close');
};

defineExpose({
  // We no longer need to expose saveOrUpdateSchedule as it's called internally
  // isCurrentlyScheduled: () => form.isScheduled // Expose if needed by parent
});

</script>