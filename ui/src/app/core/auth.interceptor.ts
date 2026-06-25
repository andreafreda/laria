import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from './auth.service';

/**
 * Attaches the login token as a Bearer header to every API request.
 *
 * Skips the login endpoint (it has no token yet) and any non-API URL, so static
 * assets are not given an Authorization header they don't need.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(AuthService).token();
  const needsAuth = req.url.includes('/api/') && !req.url.includes('/api/auth/login');
  if (token && needsAuth) {
    req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  }
  return next(req);
};
