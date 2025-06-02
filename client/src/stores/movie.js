import { defineStore } from 'pinia'

export const useMovieStore = defineStore('movie', {
  state: () => ({
    movie: null,
    showFullVideo: false,
  }),
  actions: {
    setMovie(movie) {
      this.movie = movie
    },
    clearMovie() {
      this.movie = null
    }
  },
  getters: {
    currentMovie: (state) => state.movie || null
  }
})
