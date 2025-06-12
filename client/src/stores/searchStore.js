import { defineStore } from 'pinia';

export const useSearchStore = defineStore('search', {
  state: () => ({
    results: null,
    // Context for which the current 'results' are valid
    resultsContext: {
      searchId: null,
      prompt: null,
      mediaName: null,
    },
  }),
  actions: {
    setSearchResults(results, context) {
      // context should be an object like { searchId, prompt, mediaName }
      this.results = results;
      this.resultsContext = { ...context };
    },
    clearSearchResults() {
      this.results = null;
      this.resultsContext = { searchId: null, prompt: null, mediaName: null };
    },
  },
});
