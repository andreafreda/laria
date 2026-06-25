import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/** Sends a chat turn to the engine and returns its reply. The auth token is
 *  added by the interceptor, so this just posts the text. */
@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  send(text: string): Observable<{ reply: string }> {
    return this.http.post<{ reply: string }>(`${this.base}/api/chat`, { text });
  }
}
