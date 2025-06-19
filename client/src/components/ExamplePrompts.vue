<template>
  <transition name="modal-fade">
    <div v-if="show" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-[1001] p-4" @click.self="closeModal">
      <div class="bg-gray-800 p-6 rounded-lg shadow-xl max-w-lg w-full" @click.stop>
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-xl font-semibold text-white">Example Prompts</h3>
          <button @click="closeModal" class="text-gray-400 hover:text-white">
            <CloseIcon :size="24" />
          </button>
        </div>

        <div class="space-y-3 max-h-[60vh] overflow-y-auto pr-2 md:pr-3">
          <div
            v-for="(prompt, index) in examplePrompts"
            :key="index"
            @click="selectPrompt(prompt)"
            class="p-3 bg-gray-700 hover:bg-gray-600 rounded-md cursor-pointer transition-colors"
          >
            <p class="text-white font-medium">{{ prompt.title }}</p>
            <p class="text-sm text-gray-300 mt-1">{{ prompt.text }}</p>
          </div>
        </div>

        <div class="mt-6 flex justify-end">
          <button @click="closeModal" class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none">
            Close
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import CloseIcon from 'vue-material-design-icons/Close.vue';

const props = defineProps({
  show: Boolean,
});

const emit = defineEmits(['close', 'select-prompt']);

const examplePrompts = ref([
  { title: 'Simple Movie Recommendation', text: 'Suggest 3 movies similar to The Matrix.' },
  { title: 'Simple Exclude Watched Items', text: 'Suggest Recommend comedy movies I haven\'t seen, excluding {{all_media}}.' },
  { title: 'Recent TV Shows by Genre', text: 'Recommend {{limit}} science fiction TV shows from the last 5 years. \n\nExclude the following media from your recommendations: {{all_media}}.' },
  { title: 'Recent TV Shows by Platform', text: 'Recommend {{limit}} TV shows from the last 5 years on Netflix. \n\nExclude the following media from your recommendations: {{all_media}}.' },
  { title: 'Movies with Specific Actors', text: 'Recommend {{limit}} movies starring Tom Hanks and Meg Ryan. \n\nExclude the following media from your recommendations: {{all_media}}.' },
  { title: 'Based on Favorites', text: 'Recommend {{limit}} movies based on my favorites: {{favorites}}. \n\nExclude the following media from your recommendations: {{all_media}}.' },
  { title: 'Based on Watch History', text: 'Suggest {{limit}} movies or TV shows based on my watch history: {{watch_history}}. \n\nUse this list to determine what I should watch next: {{all_media}}.' },
  { title: 'Based on Mood', text: 'What is the overall feeling or mood of {{media_name}}? (e.g., suspenseful, whimsical, gritty, romantic, melancholic, hopeful). \n\nRecommend {{limit}} movies or tv series that fit this mood. \n\nExclude the following media from your recommendations: {{all_media}}.' },
  { title: 'Common Genre', text: ' \n\nWhat are the common genres of these titles: {{favorites}}? \n\nRecommend {{limit}} movies or tv series that fit this genre. \n\nExclude the following media from your recommendations: {{all_media}}.' },
]);

const selectPrompt = (prompt) => {
  emit('select-prompt', prompt);
  closeModal();
};

const closeModal = () => emit('close');

const handleEscapeKey = (event) => {
  if (event.key === 'Escape' && props.show) {
    closeModal();
  }
};

onMounted(() => {
  document.addEventListener('keydown', handleEscapeKey);
});
onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEscapeKey);
});
</script>