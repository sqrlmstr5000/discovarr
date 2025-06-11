<template>
    <div v-if="movie" class="z-80 text-white px-8 py-8 flex flex-col md:flex-row">
        <!-- Close Button (Optional, if needed here) -->
        <!-- <button v-if="showCloseButton" @click="$emit('close')" class="absolute top-2 right-2 text-gray-400 hover:text-white p-1 rounded-full hover:bg-gray-700/80 z-10">
            <CloseIcon :size="28" /> -->
        <!-- Movie Poster -->
        <div class="w-full md:w-auto md:h-[250px] lg:h-[300px] mb-6 md:mb-0 md:mr-8 flex-shrink-0 relative">
            <!-- Placeholder while image is loading -->
            <div v-if="imageLoading"
                 class="w-full h-full bg-gray-800 rounded-xl flex items-center justify-center animate-pulse mx-auto md:mx-0 max-w-[200px] md:max-w-none">
                <!-- Optional: You can add an icon or text here -->
                <!-- <svg class="w-10 h-10 text-gray-600" fill="currentColor" viewBox="0 0 20 20"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.022 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path></svg> -->
            </div>
            <!-- Actual Image -->
            <img 
                v-show="!imageLoading"
                :src="currentImageSrc"
                :alt="movie.title"
                class="w-full h-full object-contain md:object-cover rounded-xl shadow-lg mx-auto md:mx-0 max-w-[200px] md:max-w-none"
                @load="onImageLoad"
                @error="onImageError"
            />
        </div>
        <!-- Movie Details -->
        <div class="flex-grow">
            <h1 class="text-3xl sm:text-4xl lg:text-5xl font-bold font-serif mb-3">{{ movie.title }}</h1>
            
            <div class="flex flex-wrap items-center text-xs mb-6">
                <span v-if="movie.source_title" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">SOURCE: {{ movie.source_title }}</span>
                <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">{{ movie.media_type.toUpperCase() }}</span>
                
                <!-- TMDB ID Display/Edit -->
                <span class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2 flex items-center">
                    TMDB: 
                    <span v-if="!editingTmdbId" class="ml-1 flex items-center">
                        <a 
                            v-if="movie.tmdb_id"
                            :href="`https://www.themoviedb.org/${movie.media_type}/${movie.tmdb_id}`"
                            target="_blank" 
                            rel="noopener noreferrer" 
                            class="text-blue-400 hover:text-blue-300 hover:underline"
                            @click.stop
                        >{{ movie.tmdb_id }}</a>
                        <span v-else class="text-gray-500 italic">N/A</span>
                        <button @click.stop="startEditTmdbId" class="ml-1 text-gray-400 hover:text-discovarr p-0.5 rounded-full hover:bg-gray-800">
                            <PencilIcon :size="14" />
                        </button>
                    </span>
                    <span v-else class="ml-1 flex items-center space-x-1">
                        <input type="text" v-model="editableTmdbIdValue" 
                               class="bg-gray-900 text-white border border-gray-700 rounded-md px-1 py-0.5 text-xs w-20 focus:ring-discovarr focus:border-discovarr"
                               @keyup.enter="saveEditTmdbId" @keyup.esc="cancelEditTmdbId" @click.stop />
                        <button @click.stop="saveEditTmdbId" class="text-green-500 hover:text-green-400 p-0.5 rounded-full hover:bg-gray-800"><CheckIcon :size="16" /></button>
                        <button @click.stop="cancelEditTmdbId" class="text-red-500 hover:text-red-400 p-0.5 rounded-full hover:bg-gray-800"><CloseIcon :size="16" /></button>
                    </span>
                </span>
                <span v-if="movie.imdb_id" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">IMDB: {{ movie.imdb_id }}</span>
                <span v-if="movie.rt_score" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">RT: 
                    <a 
                    v-if="movie.rt_url"
                    :href="movie.rt_url" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    class="text-blue-400 hover:text-blue-300"
                    @click.stop
                    >{{ movie.rt_score }}</a>
                    <div v-if="!movie.rt_url">{{ movie.rt_score }}</div></span>
                <span v-if="movie.media_status" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">{{ movie.media_status.toUpperCase() }}</span>
                <span v-if="movie.release_date" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">RELEASE: {{ movie.release_date }}</span>
                <span v-if="movie.genres" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">GENRES: {{ movie.genres }}</span>
                <span v-if="movie.networks" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">NETWORKS: {{ movie.networks }}</span>
                <span v-if="movie.original_language" class="bg-gray-700 text-gray-200 px-2.5 py-1 rounded-full mr-2 mb-2">LANG: {{ movie.original_language.toUpperCase() }}</span>
            </div>
            
            <div class="mb-6">
                <h2 class="text-sm uppercase text-gray-400 tracking-wider font-semibold mb-2">Description</h2>
                <p class="text-base sm:text-lg text-gray-300 leading-relaxed">{{ movie.description || 'No description available.' }}</p>
            </div>

            <div v-if="movie.similarity">
                <h2 class="text-sm uppercase text-gray-400 tracking-wider font-semibold mb-2">Similarity</h2>
                <p class="text-base sm:text-lg text-gray-300">{{ movie.similarity }}</p>
            </div>

            <!-- Request Button Section -->
            <div class="mt-8 pt-6 border-t border-gray-700/50">
                <button
                    v-if="movie.tmdb_id && movie.media_type"
                    @click="triggerInternalRequestModal(movie)"
                    :disabled="movie.requested"                    
                    class="w-full flex items-center justify-center px-6 py-3 rounded-lg font-semibold text-white transition-colors duration-150 ease-in-out"
                    :class="movie.requested 
                        ? 'bg-gray-600 cursor-not-allowed' 
                        : 'bg-discovarr hover:bg-discovarr-dark focus:outline-none focus:ring-2 focus:ring-discovarr-light focus:ring-opacity-75'"
                    :title="movie.requested ? 'This item has already been requested' : 'Request this media'"
                >
                    <SendIcon :size="20" class="mr-2" :fillColor="movie.requested ? '#9CA3AF' : '#FFFFFF'" />
                    <span>{{ movie.requested ? 'Requested' : 'Request Media' }}</span>
                </button>
            </div>
        </div>
    </div>
    <div v-else class="z-40 text-white p-10 pb-0 flex items-center justify-center h-[300px] md:h-[400px]">
        <p class="text-gray-500 text-xl">Select a movie to see details.</p>
    </div>

    <!-- Internal Request Modal -->
    <Teleport to="body">
        <RequestModal 
            v-if="showInternalRequestModal"
            v-model:show="showInternalRequestModal" 
            :media="mediaForInternalRequestModal"
            @close="showInternalRequestModal = false"
            @request-complete="handleInternalRequestComplete"
        />
    </Teleport>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import SendIcon from 'vue-material-design-icons/Send.vue';
import RequestModal from './RequestModal.vue'; // Adjust path if necessary
import PencilIcon from 'vue-material-design-icons/Pencil.vue';
import CheckIcon from 'vue-material-design-icons/Check.vue';
import CloseIcon from 'vue-material-design-icons/Close.vue';
import { useToastStore } from '@/stores/toast'; // Import toast store
const toastStore = useToastStore(); // Initialize toast store
import { config } from '../config'; // Import config for API URL

const props = defineProps({
    movie: Object,
    // showCloseButton: { // Prop from a previous step, keep if needed
    //     type: Boolean,
    //     default: false
    // }
});

const emit = defineEmits([
    'close', // Emits an event to tell parent to close this modal
    'refresh-list', // Emits an event to tell parent to refresh data
    'tmdb-id-updated' // New emit for TMDB ID updates
]); 

const showInternalRequestModal = ref(false);
const mediaForInternalRequestModal = ref(null);

const imageLoading = ref(true);
const currentImageSrc = ref('');
const placeholderImage = '/placeholder-image.jpg'; // Assumes it's in the public folder

const triggerInternalRequestModal = (movieItem) => {
    if (movieItem.requested) return; // Don't open if already requested
    mediaForInternalRequestModal.value = movieItem;
    showInternalRequestModal.value = true;
};

// TMDB ID Edit State
const editingTmdbId = ref(false);
const editableTmdbIdValue = ref('');

// Watch for movie prop changes to update editableTmdbIdValue
watch(() => props.movie, (newMovie, oldMovie) => {
    if (newMovie) {
        editableTmdbIdValue.value = String(newMovie.tmdb_id || '');
        if (newMovie.id !== oldMovie?.id) { // Reset TMDB edit state only if it's a new movie
          editingTmdbId.value = false;
        }

        // Handle image loading
        if (newMovie.poster_url) {
            imageLoading.value = true; // Set to true to show placeholder before new image loads
            currentImageSrc.value = `${config.apiUrl.replace(/\/api$/, '')}/cache/image/${newMovie.poster_url}`;
        } else {
            imageLoading.value = false; // No poster, show placeholder image directly
            currentImageSrc.value = placeholderImage;
        }
    } else {
        editableTmdbIdValue.value = '';
        editingTmdbId.value = false;
        imageLoading.value = false; // No movie, show placeholder image directly
        currentImageSrc.value = placeholderImage;
    }
}, { immediate: true }); // Run immediately on mount if movie prop is initially set

const startEditTmdbId = () => {
    editingTmdbId.value = true;
    // editableTmdbIdValue is already updated by the watcher
};

const cancelEditTmdbId = () => {
    editingTmdbId.value = false;
    // Reset value to the current prop value
    editableTmdbIdValue.value = String(props.movie?.tmdb_id || '');
};

const saveEditTmdbId = async () => {
    if (!props.movie) return;

    const newTmdbId = editableTmdbIdValue.value.trim();
    // Basic validation: ensure it's a number if your TMDB IDs are numeric
    if (newTmdbId !== '' && isNaN(Number(newTmdbId))) { // Allow empty string to clear ID
        toastStore.show('Invalid TMDB ID. Please enter a numeric ID or leave empty.', 'error');
        return;
    }

    try {
        // ** Placeholder for API call **
        // Replace with your actual API call to update the TMDB ID
        console.log(`Attempting to save TMDB ID for item ${props.movie.id}: New ID = ${newTmdbId === '' ? null : newTmdbId}`);
        // Example: const response = await fetch(`${config.apiUrl}/media/${props.movie.id}/tmdb_id`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tmdb_id: newTmdbId === '' ? null : Number(newTmdbId) }) }); // Use Number(newTmdbId) if backend expects number
        // if (!response.ok) throw new Error('API update failed');
        // const updatedItem = await response.json(); // Assuming API returns the updated item
        
        // Simulate success for placeholder
        alert(`TMDB ID for "${props.movie.title}" would be updated to ${newTmdbId || 'N/A'}.\n(This is a placeholder - no actual API call made.)`);

        editingTmdbId.value = false;
        // The watcher will update editableTmdbIdValue when the parent refreshes and passes the new movie prop
        emit('tmdb-id-updated'); // Notify parent to refresh the list

    } catch (error) {
        console.error(`Error saving TMDB ID for ${props.movie.id}:`, error);
        toastStore.show(`Failed to save TMDB ID: ${error.message || 'Unknown error'}`, 'error');
        cancelEditTmdbId(); // Revert on error
    }
};

const handleInternalRequestComplete = () => {
    showInternalRequestModal.value = false;
    mediaForInternalRequestModal.value = null;
    emit('refresh-list'); // Signal parent to refresh its data
};

const onImageLoad = () => {
    imageLoading.value = false;
};

const onImageError = () => {
    // Fallback to placeholder image if the primary one fails
    if (currentImageSrc.value !== placeholderImage) {
        currentImageSrc.value = placeholderImage;
    }
    imageLoading.value = false; // Stop showing loading animation
};

// Handle Escape key press to close the modal
const handleKeydown = (event) => {
    if (event.key === 'Escape') {
        // Only close this modal if the internal request modal is not shown
        if (!showInternalRequestModal.value) {
            emit('close');
        }
        // If showInternalRequestModal is true, assume RequestModal handles its own Escape key.
    }
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
});
</script>
