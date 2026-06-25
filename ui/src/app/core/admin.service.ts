import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface AdminUser {
  id: number;
  username: string;
  role: string;
  profile_id: number | null;
}

export interface Profile {
  id: number;
  name: string;
  is_dependent: boolean;
}

/** Owner-only family management: list and create profiles and users. Calls the
 *  /api/admin endpoints (the server enforces the owner role). */
@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  listUsers(): Observable<AdminUser[]> {
    return this.http.get<AdminUser[]>(`${this.base}/api/admin/users`);
  }

  listProfiles(): Observable<Profile[]> {
    return this.http.get<Profile[]>(`${this.base}/api/admin/profiles`);
  }

  createProfile(name: string, isDependent: boolean): Observable<unknown> {
    return this.http.post(`${this.base}/api/admin/profiles`,
      { name, is_dependent: isDependent });
  }

  createUser(username: string, password: string, role: string,
             profileId: number | null): Observable<unknown> {
    return this.http.post(`${this.base}/api/admin/users`,
      { username, password, role, profile_id: profileId });
  }
}
