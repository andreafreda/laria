import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
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

export interface MonthTrend {
  month: number;
  income: number;
  expenses: number;
  net: number;
}

export interface CategoryYear {
  category: string;
  total: number;
  months: number[];
}

export interface BudgetStatus {
  category: string;
  budget: number;
  spent: number;
  remaining: number;
  perc: number;
  over: boolean;
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

  /** Income, expenses and category breakdown for an optional date range. With no
   *  range the API returns the running total; a range scopes it to a week, month,
   *  or any custom span. */
  summary(dateFrom?: string, dateTo?: string): Observable<ExpenseSummary> {
    let params = new HttpParams();
    if (dateFrom) {
      params = params.set('date_from', dateFrom);
    }
    if (dateTo) {
      params = params.set('date_to', dateTo);
    }
    return this.http.get<ExpenseSummary>(`${this.base}/api/finance/summary`, { params });
  }

  goals(): Observable<Goal[]> {
    return this.http.get<Goal[]>(`${this.base}/api/finance/goals`);
  }

  /** Income/expenses/net for each of the twelve months of a year. */
  trend(year: number): Observable<MonthTrend[]> {
    const params = new HttpParams().set('year', String(year));
    return this.http.get<MonthTrend[]>(`${this.base}/api/finance/trend`, { params });
  }

  /** Per-category spending across a whole year. */
  categoryYear(year: number): Observable<CategoryYear[]> {
    const params = new HttpParams().set('year', String(year));
    return this.http.get<CategoryYear[]>(`${this.base}/api/finance/category-year`, { params });
  }

  /** Budget vs spent for each category in a month. */
  budgetStatus(year: number, month: number): Observable<BudgetStatus[]> {
    const params = new HttpParams().set('year', String(year)).set('month', String(month));
    return this.http.get<BudgetStatus[]>(`${this.base}/api/finance/budget-status`, { params });
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
