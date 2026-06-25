import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

interface LoginResponse {
  token: string;
  must_change: boolean;
}

const TOKEN_KEY = 'laria.token';

/**
 * Holds the login session: the JWT and whether a password change is pending.
 *
 * The token is kept in localStorage so a reload stays logged in, and mirrored in
 * a signal so the rest of the app reacts to login and logout. The interceptor
 * reads the token from here; components read `isAuthenticated` and `mustChange`.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  private readonly _token = signal<string | null>(localStorage.getItem(TOKEN_KEY));
  private readonly _mustChange = signal(false);

  readonly token = this._token.asReadonly();
  readonly mustChange = this._mustChange.asReadonly();
  readonly isAuthenticated = computed(() => this._token() !== null);

  /** Exchange credentials for a token and remember the session. */
  login(username: string, password: string): Observable<LoginResponse> {
    return this.http
      .post<LoginResponse>(`${this.base}/api/auth/login`, { username, password })
      .pipe(tap((res) => this.startSession(res.token, res.must_change)));
  }

  /** Set a new password for the current user (clears the must-change flag). */
  changePassword(newPassword: string): Observable<unknown> {
    return this.http
      .post(`${this.base}/api/auth/change-password`, { new_password: newPassword })
      .pipe(tap(() => this._mustChange.set(false)));
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    this._token.set(null);
    this._mustChange.set(false);
  }

  private startSession(token: string, mustChange: boolean): void {
    localStorage.setItem(TOKEN_KEY, token);
    this._token.set(token);
    this._mustChange.set(mustChange);
  }
}
