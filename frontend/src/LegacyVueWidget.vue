<template>
  <section class="legacy-vue-widget">
    <header>
      <h2>{{ title }}</h2>
      <p class="subtitle">{{ subtitle }}</p>
    </header>
    <article>
      <slot>
        <p>{{ message }}</p>
      </slot>
    </article>
  </section>
</template>

<script>
export default {
  name: 'LegacyVueWidget',
  props: {
    title: {
      type: String,
      default: 'Legacy Vue Widget'
    },
    subtitle: {
      type: String,
      default: 'Used for cross-framework experiments'
    },
    message: {
      type: String,
      default: 'This Vue component lives alongside the React/TSX code to enable shared indexing and migration tooling.'
    }
  }
};
</script>

<style scoped>
.legacy-vue-widget {
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 1rem;
  background: #f8fafc;
  max-width: 420px;
}

.subtitle {
  color: #475569;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}
</style>
