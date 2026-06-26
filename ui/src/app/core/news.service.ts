import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface BriefingTopic {
  topic: string;
  sources: string[];
}

export interface Briefing {
  id: number;
  cron: string;
  num_news: number;
  topics: BriefingTopic[];
}

export interface ErrorLog {
  ts: string;
  source: string;
  level: string;
  message: string;
  traceback?: string | null;
}

/** Reads and edits the user's news briefings, and (for the owner) the system
 *  error log. Briefings created here are scheduled when the Telegram process
 *  next loads active briefings. */
@Injectable({ providedIn: 'root' })
export class NewsService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  briefings(): Observable<Briefing[]> {
    return this.http.get<Briefing[]>(`${this.base}/api/news/briefings`);
  }

  createBriefing(topics: BriefingTopic[], cron: string, numNews: number): Observable<Briefing> {
    return this.http.post<Briefing>(`${this.base}/api/news/briefings`,
      { topics, cron, num_news: numNews });
  }

  deleteBriefing(id: number): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/api/news/briefings/delete`, { id });
  }

  logs(): Observable<ErrorLog[]> {
    return this.http.get<ErrorLog[]>(`${this.base}/api/system/logs`);
  }

  clearLogs(): Observable<{ deleted: number }> {
    return this.http.post<{ deleted: number }>(`${this.base}/api/system/logs/clear`, {});
  }
}

/** Parse a textarea (one topic per line, optional "| site1, site2") into the
 *  structured topics the API expects. */
export function parseTopics(text: string): BriefingTopic[] {
  const topics: BriefingTopic[] = [];
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }
    const [topicPart, sourcesPart] = line.split('|', 2);
    const topic = topicPart.trim();
    if (!topic) {
      continue;
    }
    const sources = (sourcesPart ?? '')
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter((s) => s.length > 0);
    topics.push({ topic, sources });
  }
  return topics;
}
