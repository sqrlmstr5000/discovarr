import { createRouter, createWebHistory } from 'vue-router'
import MediaListView from '../views/MediaListView.vue'
import SettingsView from '../views/SettingsView.vue'
import SearchView from '../views/SearchView.vue' // Import the new SearchView
import WatchHistory from '../views/WatchHistoryView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: MediaListView
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    },
    {
      path: '/search/:searchId?', // Optional searchId parameter
      name: 'search-view',
      component: SearchView,
      props: true // Automatically pass route params as props to the component
    },
    {
      path: '/watch-history',
      name: 'watch-history',
      component: WatchHistory
    }
  ]
})

export default router
