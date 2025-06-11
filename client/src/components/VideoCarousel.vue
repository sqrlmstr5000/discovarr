<template>
    <div class="min-w-[1200px] relative">
        <!-- Category Title -->
        <div class="flex justify-between mr-6 mb-2"> <!-- Optional: Added a small bottom margin for better spacing -->
            <div class="flex items-center font-semibold text-white text-2xl cursor-pointer">
                {{ category }}
            </div>
        </div>

        <Carousel 
            ref="carousel" 
            v-model="currentSlide"
            :items-to-show="8" 
            :items-to-scroll="1"
            :wrap-around="false"
            :transition="500"
            snapAlign="start"
            class="bg-transparent"
        >
            <Slide
                v-for="(media, index) in movies"
                :key="media.media_id" 
                class="flex items-center object-cover text-white bg-transparent"
            >
                <div 
                    class="w-full h-[100%] hover:brightness-125 cursor-pointer rounded-lg overflow-hidden relative"
                    :class="currentSlide !== index ? 'border-4 border-transparent' : 'border-4 border-white'"
                >
                    <img 
                        style="user-select: none" 
                        class="pointer-events-none w-full h-full object-cover"
                        :src="`${config.apiUrl.replace(/\/api$/, '')}/cache/${media.poster_url}`"
                        :alt="media.title"
                    >
                    <button
                        @click="navigateToSearch(media.title)"
                        class="absolute top-2 right-2 z-10 p-1.5 bg-black bg-opacity-60 rounded-full text-white hover:bg-opacity-80 focus:outline-none transition-colors duration-150"
                        :aria-label="'Search for media similar to ' + media.title"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                        </svg>
                    </button>
                    <div class="absolute bottom-0 left-0 w-full p-1 bg-black bg-opacity-60 text-white text-xs text-center truncate">
                        {{ media.title }}
                    </div>
                </div>
            </Slide>
            <template #addons>
                <Navigation />
            </template>
        </Carousel>
    </div>
</template>

<script setup>
import { ref, toRefs, inject } from 'vue';
import { useRouter } from 'vue-router';
import 'vue3-carousel/dist/carousel.css'
import { Carousel, Slide, Navigation } from 'vue3-carousel'
import { useSettingsStore } from '@/stores/settings'; // Adjust path if necessary
import { config } from '../config'; // Import the config
import { computed } from 'vue';
const settingsStore = useSettingsStore();

// Access a specific setting's value directly
const currentGeminiLimit = computed(() => settingsStore.getSettingValue("gemini", "limit"));

console.log("Gemini Limit:", currentGeminiLimit.value);

let currentSlide = ref(0)
const router = useRouter();

// const openSearchModal = inject('openSearchModal', null); // No longer using modal for this action

const props = defineProps({ category: String, movies: Array })
const { movies, category } = toRefs(props)

const navigateToSearch = (title) => {
  if (title) {
    const promptText = null;
    const mediaNameText = title;
    router.push({ 
      name: 'search-view', 
      query: { 
        initialMediaName: mediaNameText 
      } 
    });
  }
};
</script>

<style>
    .carousel__prev, 
    .carousel__next, 
    .carousel__prev:hover, 
    .carousel__next:hover {
        color: white;
    }
</style>
