import { createApp } from 'vue';
import router from './router';
import PrimeVue from 'primevue/config';
import App from './App.vue';

import './styles/index.less';

const app = createApp(App);
app.use(router);
app.use(PrimeVue, { theme: 'none' });
app.mount('#app');
