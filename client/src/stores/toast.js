import { defineStore } from 'pinia';

export const useToastStore = defineStore('toast', {
  state: () => ({
    message: '',
    type: 'success', // 'success', 'error', 'info', 'warning'
    isVisible: false,
    timeoutId: null,
  }),
  actions: {
    show(message, type = 'success', duration = 10000) {
      this.message = message;
      this.type = type;
      this.isVisible = true;

      if (this.timeoutId) {
        clearTimeout(this.timeoutId);
      }

      this.timeoutId = setTimeout(() => {
        this.hide();
      }, duration);
    },
    hide() {
      this.isVisible = false;
      this.message = '';
      this.type = 'success'; // Reset to default
      if (this.timeoutId) {
        clearTimeout(this.timeoutId);
        this.timeoutId = null;
      }
    },
  },
});
