import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Reminder {
  id: number;
  message: string;
  remind_at: string | null;
  recurring: string | null;
}

/** Reads and edits the user's reminders. A reminder is either one-shot
 *  (remind_at) or recurring (a 5-field cron). Like briefings, reminders created
 *  here start firing once the Telegram process next loads active reminders. */
@Injectable({ providedIn: 'root' })
export class RemindersService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  reminders(): Observable<Reminder[]> {
    return this.http.get<Reminder[]>(`${this.base}/api/reminders`);
  }

  create(message: string, remindAt: string | null, recurring: string | null): Observable<Reminder> {
    return this.http.post<Reminder>(`${this.base}/api/reminders`,
      { message, remind_at: remindAt, recurring });
  }

  remove(id: number): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/api/reminders/delete`, { id });
  }
}
