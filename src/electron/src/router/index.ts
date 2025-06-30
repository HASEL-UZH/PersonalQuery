import { createRouter, createWebHashHistory, Router } from 'vue-router';
import Chat from '../views/Chat.vue';
import ChatView from '../views/ChatView.vue';

const router: Router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/experience-sampling',
      name: 'ExperienceSampling',
      component: () => import('../views/ExperienceSamplingView.vue')
    },
    {
      path: '/onboarding',
      name: 'Onboarding',
      component: () => import('../views/OnboardingView.vue'),
      props: (route) => ({ query: route.query.isMacOS })
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/SettingsView.vue'),
      props: (route) => ({ query: route.query.isMacOS }),
      children: [
        {
          path: '',
          name: 'General',
          redirect: 'about'
        },
        {
          path: '/about',
          name: 'About',
          component: () => import('../views/settings/AboutView.vue')
        },
        {
          path: '/work-hours',
          name: 'Active Times',
          component: () => import('../views/settings/WorkHoursView.vue')
        }
      ]
    },
    {
      path: '/data-export',
      name: 'DataExport',
      component: () => import('../views/DataExportView.vue')
    },
    {
      path: '/chat',
      component: Chat,
      children: [
        {
          path: ':chatId',
          component: ChatView
        }
      ]
    },
    { path: '/', redirect: '/chat/default' },
    {
      path: '/setup-env',
      name: 'SetupEnv',
      component: () => import('../views/SetupEnvView.vue')
    }
  ]
});

export default router;
