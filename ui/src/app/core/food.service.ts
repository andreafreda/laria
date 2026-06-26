import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface PlanMeal {
  date: string;
  meal_type: string;
  member: string;
  items: string;
  recipe: string | null;
  kcal: number | null;
}

export interface DayTotals {
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface MacroTargets {
  protein_target_g: number;
  carbs_target_g: number;
  fat_target_g: number;
}

export interface DiaryMeal {
  meal_type: string;
  description: string;
  kcal_total: number | null;
}

export interface DiaryEntry {
  member: string;
  totals: DayTotals;
  hydration: { ml_total: number };
  kcal_target: number | null;
  macro_targets: MacroTargets | null;
  meals: DiaryMeal[];
}

export interface ShoppingItem {
  id: number;
  name: string;
  qty: string | null;
  category: string | null;
  price: number | null;
  checked: boolean;
}

export interface PantryItem {
  name: string;
  qty: string | null;
  category: string | null;
  expires_on: string | null;
}

export interface Profile {
  member: string;
  sex: string | null;
  age: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  bmi: number | null;
  goal: string | null;
  activity_level: string | null;
  kcal_target: number | null;
  allergies: string | null;
  preferences: string | null;
  restrictions: string | null;
  macro_targets: MacroTargets | null;
}

export interface WeightEntry {
  logged_at: string;
  weight_kg: number;
  bmi: number | null;
}

export interface LoggedDay {
  day: string;
  members: number;
  meals: number;
  kcal: number;
}

/** Reads the food dashboards (meal plan, diary, shopping, pantry) from the API.
 *  Same data the assistant maintains; these are authenticated GETs plus one
 *  toggle for ticking shopping items. */
@Injectable({ providedIn: 'root' })
export class FoodService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  /** This week's planned meals, or a custom range when dates are given. */
  plan(dateFrom?: string, dateTo?: string): Observable<PlanMeal[]> {
    let params = new HttpParams();
    if (dateFrom) {
      params = params.set('date_from', dateFrom);
    }
    if (dateTo) {
      params = params.set('date_to', dateTo);
    }
    return this.http.get<PlanMeal[]>(`${this.base}/api/food/plan`, { params });
  }

  /** Each member's meals and nutrition for a day (default today). */
  diary(day?: string): Observable<{ date: string; members: DiaryEntry[] }> {
    let params = new HttpParams();
    if (day) {
      params = params.set('date', day);
    }
    return this.http.get<{ date: string; members: DiaryEntry[] }>(
      `${this.base}/api/food/diary`, { params });
  }

  shopping(): Observable<{ items: ShoppingItem[]; cost: { total: number; priced: number; count: number } }> {
    return this.http.get<{ items: ShoppingItem[]; cost: { total: number; priced: number; count: number } }>(
      `${this.base}/api/food/shopping`);
  }

  toggleShopping(id: number): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/api/food/shopping/toggle`, { id });
  }

  pantry(): Observable<{ items: PantryItem[]; expiring: PantryItem[] }> {
    return this.http.get<{ items: PantryItem[]; expiring: PantryItem[] }>(
      `${this.base}/api/food/pantry`);
  }

  profiles(): Observable<Profile[]> {
    return this.http.get<Profile[]>(`${this.base}/api/food/profiles`);
  }

  weight(member: string): Observable<WeightEntry[]> {
    const params = new HttpParams().set('member', member);
    return this.http.get<WeightEntry[]>(`${this.base}/api/food/weight`, { params });
  }

  /** Create or update a member's profile; returns the recomputed BMI. */
  saveProfile(member: string, fields: Partial<Profile>): Observable<{ ok: boolean; bmi: number | null }> {
    return this.http.post<{ ok: boolean; bmi: number | null }>(
      `${this.base}/api/food/profile`, { member, ...fields });
  }

  /** Recent days that have logged meals, for the diary chart and history. */
  diaryHistory(days = 30): Observable<LoggedDay[]> {
    const params = new HttpParams().set('days', String(days));
    return this.http.get<LoggedDay[]>(`${this.base}/api/food/diary/history`, { params });
  }

  /** Download the diary CSV as a blob. Goes through HttpClient so the auth
   *  interceptor adds the bearer token (a plain anchor link could not). */
  exportCsv(dateFrom?: string, dateTo?: string): Observable<Blob> {
    let params = new HttpParams();
    if (dateFrom) {
      params = params.set('date_from', dateFrom);
    }
    if (dateTo) {
      params = params.set('date_to', dateTo);
    }
    return this.http.get(`${this.base}/api/food/export.csv`, { params, responseType: 'blob' });
  }
}
