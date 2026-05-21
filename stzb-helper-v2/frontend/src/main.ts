import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/global.scss'
import App from './App.vue'
import router from './routes'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)
createApp(App).use(router).use(pinia).mount('#app')
