import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export type ListKind = 'todo' | 'checklist' | 'shopping' | 'packing';

export interface List {
  id: number;
  name: string;
  kind: ListKind;
  open_items: number;
}

export interface ListItem {
  id: number;
  text: string;
  qty: string | null;
  checked: boolean;
  due_at: string | null;
}

/** Reads and edits the household's generic lists (todo/checklist/shopping/
 *  packing) and their items. An item can carry an optional due_at date or time. */
@Injectable({ providedIn: 'root' })
export class ListsService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  lists(): Observable<List[]> {
    return this.http.get<List[]>(`${this.base}/api/lists`);
  }

  createList(name: string, kind: ListKind): Observable<List> {
    return this.http.post<List>(`${this.base}/api/lists`, { name, kind });
  }

  deleteList(id: number): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/api/lists/${id}/delete`, {});
  }

  items(listId: number): Observable<ListItem[]> {
    return this.http.get<ListItem[]>(`${this.base}/api/lists/${listId}/items`);
  }

  addItem(listId: number, text: string, qty: string | null, dueAt: string | null): Observable<ListItem> {
    return this.http.post<ListItem>(`${this.base}/api/lists/${listId}/items`,
      { text, qty, due_at: dueAt });
  }

  toggleItem(itemId: number): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/api/lists/items/${itemId}/toggle`, {});
  }

  deleteItem(itemId: number): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/api/lists/items/${itemId}/delete`, {});
  }
}
