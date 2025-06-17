<template>
  <div
    class="prose prose-sm prose-invert max-w-none
           prose-headings:text-slate-200
           prose-p:text-slate-300
           prose-a:text-amber-400 prose-a:no-underline hover:prose-a:underline
           prose-strong:text-slate-100
           prose-code:text-fuchsia-400 prose-code:before:content-[''] prose-code:after:content-[''] prose-code:px-1 prose-code:py-0.5 prose-code:font-normal prose-code:bg-slate-700/50 prose-code:rounded-sm
           prose-blockquote:border-l-amber-400 prose-blockquote:text-slate-400 prose-blockquote:font-normal
           prose-ul:text-slate-300 prose-ol:text-slate-300 prose-li:marker:text-slate-500
           prose-hr:border-slate-700
           prose-table prose-thead:border-b prose-thead:border-slate-700 prose-th:text-slate-200
           prose-tbody prose-tr:border-b prose-tr:border-slate-800 prose-td:text-slate-300"
    :class="classes"
    v-html="markdownHTML"
  ></div>
</template>

<script>
import MarkdownIt from "markdown-it";
var md = new MarkdownIt({
  html: true,    // Enable HTML tags in source
  linkify: true, // Autoconvert URL-like text to links
});

export default {
  props: ["mdstring", "classes"],
  computed: {
    markdownHTML() {
      return md.render(this.mdstring);
    },
  },
};
</script>