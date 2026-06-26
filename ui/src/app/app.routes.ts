import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'change-password',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/change-password/change-password.page').then((m) => m.ChangePasswordPage),
  },
  {
    path: 'chat',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/chat/chat.page').then((m) => m.ChatPage),
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/dashboard/dashboard.page').then((m) => m.DashboardPage),
  },
  {
    path: 'food',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/food/food.page').then((m) => m.FoodPage),
  },
  {
    path: 'import',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/import/import.page').then((m) => m.ImportPage),
  },
  {
    path: 'lists',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/lists/lists.page').then((m) => m.ListsPage),
  },
  {
    path: 'reminders',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/reminders/reminders.page').then((m) => m.RemindersPage),
  },
  {
    path: 'news',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/news/news.page').then((m) => m.NewsPage),
  },
  {
    path: 'logs',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/logs/logs.page').then((m) => m.LogsPage),
  },
  {
    path: 'admin',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/admin/admin.page').then((m) => m.AdminPage),
  },
  { path: '', redirectTo: 'chat', pathMatch: 'full' },
  { path: '**', redirectTo: 'chat' },
];
