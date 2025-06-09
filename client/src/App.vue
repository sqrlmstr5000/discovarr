<script setup>
import { ref, provide, onMounted, onBeforeUnmount } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import GlobalToast from '@/components/GlobalToast.vue'; // Adjust path

import Magnify from 'vue-material-design-icons/Magnify.vue';
import HomeOutline from 'vue-material-design-icons/HomeOutline.vue';
import HistoryIcon from 'vue-material-design-icons/History.vue';
import MovieOutline from 'vue-material-design-icons/MovieOutline.vue';
import MenuIcon from 'vue-material-design-icons/Menu.vue'; // For hamburger
import Cog from 'vue-material-design-icons/Cog.vue';

import { useMovieStore } from './stores/movie';
import { storeToRefs } from 'pinia';
import { useSettingsStore } from './stores/settings'; // Import the settings store

const router = useRouter();
const route = useRoute();
const settingsStore = useSettingsStore(); // Instantiate the settings store
const movieStore = useMovieStore();
// const { movie } = storeToRefs(movieStore); // movie is not used

// Define activeMedia and refreshMedia, or implement their actual logic
const activeMedia = ref(null); 
const refreshMedia = () => { console.log('refreshMedia called in App.vue'); };

const showSearchModal = ref(false);
const searchModalQuery = ref('');
const isMouseDownOnSearchContent = ref(false); // Track mousedown on search content
const searchModalMediaName = ref(null);

// Reactive property to track mobile state
const isMobile = ref(false);
// Function to check and update mobile state
const checkMobileScreen = () => {
  const mobileCheck = window.innerWidth < 768; // Tailwind's `md` breakpoint is 768px
  if (isMobile.value && !mobileCheck) { // Transitioning from mobile to desktop
    isMobileNavOpen.value = false; // Close mobile nav
  }
  isMobile.value = mobileCheck;
};
provide('isMobile', isMobile); // Provide the isMobile state

const isMobileNavOpen = ref(false);
const toggleMobileNav = () => {
  isMobileNavOpen.value = !isMobileNavOpen.value;
};

const handleGlobalKeyDown = (event) => {
  // Check if the pressed key is '/'
  if (event.key === '/') {
    // Prevent opening search if an input or textarea is already focused
    const activeElement = document.activeElement;
    if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
      return;
    }
    event.preventDefault(); // Prevent default browser action for '/' (e.g., quick find)
    router.push('/search');
  }
};

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeyDown);
  checkMobileScreen(); // Initial check
  window.addEventListener('resize', checkMobileScreen); // Update on resize
  settingsStore.fetchSettings(); // Fetch settings when the app mounts
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleGlobalKeyDown);
  window.removeEventListener('resize', checkMobileScreen); // Clean up listener
});

</script>

<template>
  <div class="fixed w-full h-screen bg-black">
    <!-- Mobile Top Bar -->
    <div
      v-if="isMobile"
      class="fixed top-0 left-0 w-full h-14 bg-gray-900 border-b border-gray-700 z-40 flex items-left px-4 shadow-md"
    >
      <!-- Logo for Mobile Top Bar -->
      <img
        class="h-8 w-auto mt-3 mr-3"
        src="/logo.png"
        alt="Discovarr Logo"
      />
      <!-- Hamburger Menu Button for Mobile (moved into top bar) -->
      <button
        @click="toggleMobileNav"
        class="p-2 text-white hover:bg-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-discovarr"
        aria-label="Toggle navigation menu"
      >
        <MenuIcon :size="28" />
      </button>
    </div>

    <div 
      id="SideNav" 
      class="h-screen bg-gray-900 border-r border-gray-700 select-none transition-transform duration-300 ease-in-out flex items-start"
      :class="[ isMobile ? `fixed top-0 left-0 w-[65px] z-50 ${isMobileNavOpen ? 'translate-x-0 shadow-xl' : '-translate-x-full'}` : 'relative w-[65px] flex-shrink-0 z-40']">
      <div class="w-full flex flex-col items-center pt-4 space-y-1"> 
        <!-- Logo -->
        <div class="mb-5 px-2">
          <img
            class="h-8 w-auto max-w-full"
            src="/logo.png"
            alt="Discovarr Logo"
          />
        </div>

        <!-- Icon Links -->
        <div
          class="w-full flex justify-center items-center h-[52px] cursor-pointer hover:bg-gray-800/70 transition-colors duration-150 ease-in-out relative"
          :class="{ 'bg-gray-700 border-r-4 border-discovarr': $route.name === 'search' && (!isMobile || isMobileNavOpen) }"
          title="Search"
          @click="() => { router.push('/search'); if (isMobile) toggleMobileNav(); }"
        >
          <Magnify fillColor="#FFFFFF" :size="28" />
        </div>
        <div
          class="w-full flex justify-center items-center h-[52px] cursor-pointer hover:bg-gray-800/70 transition-colors duration-150 ease-in-out relative"
          :class="{ 'bg-gray-700 border-r-4 border-discovarr': $route.name === 'home' && (!isMobile || isMobileNavOpen) }"
          title="Home"
          @click="() => { router.push('/'); if (isMobile) toggleMobileNav(); }"
        >
          <HomeOutline fillColor="#FFFFFF" :size="28" />
        </div>
        <div
          class="w-full flex justify-center items-center h-[52px] cursor-pointer hover:bg-gray-800/70 transition-colors duration-150 ease-in-out relative"
          :class="{ 'bg-gray-700 border-r-4 border-discovarr': $route.name === 'watch-history' && (!isMobile || isMobileNavOpen) }"
          title="Watch History"
          @click="() => { router.push('/watch-history'); if (isMobile) toggleMobileNav(); }"
        >
          <HistoryIcon fillColor="#FFFFFF" :size="28" />
        </div>
        <div
          class="w-full flex justify-center items-center h-[52px] cursor-pointer hover:bg-gray-800/70 transition-colors duration-150 ease-in-out relative mt-auto mb-2"
          :class="{ 'bg-gray-700 border-r-4 border-discovarr': $route.name === 'settings' && (!isMobile || isMobileNavOpen) }"
          title="Settings"
          @click="() => { router.push('/settings'); if (isMobile) toggleMobileNav(); }"
        >
          <Cog fillColor="#FFFFFF" :size="28" />
        </div>
      </div>
    </div>

    <!-- Backdrop for Mobile Nav -->
    <div
      v-if="isMobile && isMobileNavOpen"
      @click="toggleMobileNav"
      class="fixed inset-0 bg-black bg-opacity-60 z-45"
      aria-hidden="true"
    ></div>

    <!-- Main Content Area -->
    <div 
      class="fixed h-full bg-black transition-all duration-300 ease-in-out z-20"
      :class="[
        isMobile ? 'top-14 left-0 w-full h-[calc(100%-56px)] overflow-y-auto' : 'top-0 left-[65px] w-[calc(100%-65px)] right-0 overflow-hidden' // 56px = h-14
      ]"
    >
      <router-view 
        :activeMedia="activeMedia" 
        @refresh="refreshMedia"  
      />
    </div>
    <GlobalToast />

  </div>
</template>
