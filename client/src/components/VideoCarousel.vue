<script setup>
import { ref, toRefs, watch } from 'vue';
import { useRouter } from 'vue-router';
import 'vue3-carousel/dist/carousel.css'
import { Carousel, Slide, Navigation } from 'vue3-carousel'
import { useSettingsStore } from '@/stores/settings'; // Adjust path if necessary
import { config } from '../config'; // Import the config
import { computed } from 'vue';
const settingsStore = useSettingsStore();

let currentSlide = ref(0)
const router = useRouter();

const props = defineProps({ category: String, historyItems: Array })
const { historyItems, category } = toRefs(props)

const emit = defineEmits([
    'delete-media-item' // Emit when a media item delete is requested
]);

const placeholderImage = '/placeholder-image.jpg'; // Assumes it's in the public folder
const imageDisplayData = ref({}); // Stores { src: String, isLoading: Boolean, originalPosterUrl: String|null }

watch(() => props.historyItems, (newHistoryItems) => {
    const newImageStates = {};
    if (newHistoryItems) {
        newHistoryItems.forEach(historyItem => {
            if (historyItem && historyItem.id != null) { // Use historyItem.id
                const itemId = historyItem.id; // Use historyItem.id as the key
                const currentData = imageDisplayData.value[itemId];
                
                // If poster URL hasn't changed, keep existing state to avoid re-flicker
                if (currentData && currentData.originalPosterUrl === historyItem.poster_url) {
                    newImageStates[itemId] = currentData;
                } else {
                    if (historyItem.poster_url) {
                        newImageStates[itemId] = {
                            src: `${config.apiUrl.replace(/\/api$/, '')}/cache/image/${historyItem.poster_url}`,
                            isLoading: true,
                            originalPosterUrl: historyItem.poster_url
                        };
                    } else {
                        newImageStates[itemId] = {
                            src: placeholderImage,
                            isLoading: false,
                            originalPosterUrl: null
                        };
                    }
                }
            } // Make sure historyItem.id is the correct unique identifier
        });
    }
    imageDisplayData.value = newImageStates;
}, { immediate: true, deep: true });

const onImageLoad = (mediaId) => {
    if (imageDisplayData.value[mediaId]) {
        imageDisplayData.value[mediaId].isLoading = false;
    }
};

const onImageError = (mediaId) => {
    if (imageDisplayData.value[mediaId] && imageDisplayData.value[mediaId].src !== placeholderImage) {
        imageDisplayData.value[mediaId].src = placeholderImage;
    }
    if (imageDisplayData.value[mediaId]) { // Ensure isLoading is set to false even if it was already placeholder
        imageDisplayData.value[mediaId].isLoading = false;
    }
};

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

const triggerDeleteHistoryItem = (historyId) => {
  console.log(`Requesting delete for history ID: ${historyId}`);
  emit('delete-history-item', historyId);
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


<template>
    <div class="min-w-[1200px] relative"> <!-- Consider removing min-w-[1200px] if carousel handles width adaptively -->
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
                v-for="(historyItem, index) in historyItems"
                :key="historyItem.id"  
                class="flex items-center object-cover text-white bg-transparent"
            >
                <div 
                    class="w-full h-[100%] hover:brightness-125 cursor-pointer rounded-lg overflow-hidden relative"
                    :class="currentSlide !== index ? 'border-4 border-transparent' : 'border-4 border-white'"
                >
                    <!-- Placeholder while image is loading -->
                    <div v-if="imageDisplayData[historyItem.id]?.isLoading"
                         class="absolute inset-0 bg-gray-800 flex items-center justify-center animate-pulse">
                        <!-- Optional: You can add an icon or text here -->
                        <!-- <svg class="w-10 h-10 text-gray-600" fill="currentColor" viewBox="0 0 20 20"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.022 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path></svg> -->
                    </div>
                    <!-- Actual Image -->
                    <img
                        v-show="imageDisplayData[historyItem.id] && !imageDisplayData[historyItem.id].isLoading"
                        :src="imageDisplayData[historyItem.id]?.src"
                        :alt="historyItem.title"
                        style="user-select: none" 
                        class="pointer-events-none w-full h-full object-cover"
                        @load="onImageLoad(historyItem.id)"
                        @error="onImageError(historyItem.id)"
                    >
                    <!-- Delete Button -->
                    <button
                        v-if="imageDisplayData[historyItem.id] && !imageDisplayData[historyItem.id].isLoading"
                        @click="triggerDeleteHistoryItem(historyItem.id)"
                        class="absolute top-2 left-2 z-10 p-1.5 bg-black bg-opacity-60 rounded-full text-white hover:text-red-500 hover:bg-opacity-80 focus:outline-none transition-colors duration-150"
                        :aria-label="'Delete ' + historyItem.title"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                    <!-- Search Button -->
                    <button
                        v-if="imageDisplayData[historyItem.id] && !imageDisplayData[historyItem.id].isLoading"
                        @click="navigateToSearch(historyItem.title)"
                        class="absolute top-2 right-2 z-10 p-1.5 bg-black bg-opacity-60 rounded-full text-white hover:bg-opacity-80 focus:outline-none transition-colors duration-150"
                        :aria-label="'Search for media similar to ' + historyItem.title"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                        </svg>
                    </button>
                    <div 
                        v-if="imageDisplayData[historyItem.id] && !imageDisplayData[historyItem.id].isLoading"
                        class="absolute bottom-0 left-0 w-full p-1 bg-black bg-opacity-60 text-white text-xs text-center truncate">
                        {{ historyItem.title }}
                    </div>
                </div>
            </Slide>
            <template #addons>
                <Navigation />
            </template>
        </Carousel>
    </div>
</template>

