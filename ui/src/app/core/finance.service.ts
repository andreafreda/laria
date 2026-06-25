import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Balance {
  account: string;
  type: string;
  owner: string;
  balance: number;
}

export interface ExpenseSummary {
  income: number;
  expenses: number;
  net: number;
  by_category: { category: string; total: number }[];
}

export interface Goal {
  name: string;
  target: number;
  saved: number;
  remaining: number;
  perc: number;
  reached: boolean;
}

/** Reads the finance dashboards from the API. The data lives in the same store
 *  the assistant uses; these are plain GETs the interceptor authenticates. */
@Injectable({ providedIn: 'root' })
export class FinanceService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  balances(): Observable<Balance[]> {
    return this.http.get<Balance[]>(`${this.base}/api/finance/balances`);
  }

  summary(): Observable<ExpenseSummary> {
    return this.http.get<ExpenseSummary>(`${this.base}/api/finance/summary`);
  }

  goals(): Observable<Goal[]> {
    return this.http.get<Goal[]>(`${this.base}/api/finance/goals`);
  }

  /** Upload a bank-statement file to import its movements into an account. */
  importStatement(account: string, file: File): Observable<ImportResult> {
    const form = new FormData();
    form.append('account', account);
    form.append('file', file, file.name);
    return this.http.post<ImportResult>(`${this.base}/api/finance/import`, form);
  }
}

export interface ImportResult {
  inserted: number;
  duplicates: number;
  total: number;
  format: string;
}
