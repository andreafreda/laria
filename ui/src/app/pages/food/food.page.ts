import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList, IonItem,
  IonLabel, IonCheckbox, IonSegment, IonSegmentButton, IonNote, IonButton, IonIcon,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { chevronBack, chevronForward, downloadOutline } from 'ionicons/icons';
import {
  DiaryEntry, FoodService, LoggedDay, PantryItem, PlanMeal, ShoppingItem,
} from '../../core/food.service';

type Tab = 'plan' | 'diary' | 'shopping' | 'pantry';
type PlanSpan = 'week' | 'month';

interface PlanDay {
  date: string;
  meals: PlanMeal[];
}

/** Food overview with a plan / diary / shopping / pantry switch.
 *
 * Plan groups meals by day and steps through weeks or months; diary shows each
 * member's nutrition for a chosen day plus a 30-day calorie chart, history, and
 * a CSV export; shopping ticks items off; pantry calls out expiring stock.
 */
@Component({
  selector: 'app-food',
  standalone: true,
  imports: [
    DecimalPipe, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
    IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList, IonItem,
    IonLabel, IonCheckbox, IonSegment, IonSegmentButton, IonNote, IonButton, IonIcon,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Food</ion-title>
        @if (tab() === 'diary') {
          <ion-buttons slot="end">
            <ion-button (click)="exportCsv()" aria-label="Export CSV">
              <ion-icon slot="icon-only" name="download-outline"></ion-icon>
            </ion-button>
          </ion-buttons>
        }
      </ion-toolbar>
      <ion-toolbar>
        <ion-segment [value]="tab()" (ionChange)="changeTab($event)">
          <ion-segment-button value="plan"><ion-label>Plan</ion-label></ion-segment-button>
          <ion-segment-button value="diary"><ion-label>Diary</ion-label></ion-segment-button>
          <ion-segment-button value="shopping"><ion-label>Shopping</ion-label></ion-segment-button>
          <ion-segment-button value="pantry"><ion-label>Pantry</ion-label></ion-segment-button>
        </ion-segment>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">

        @switch (tab()) {
          @case ('plan') {
            <ion-segment [value]="planSpan()" (ionChange)="changeSpan($event)">
              <ion-segment-button value="week"><ion-label>Week</ion-label></ion-segment-button>
              <ion-segment-button value="month"><ion-label>Month</ion-label></ion-segment-button>
            </ion-segment>
            <div class="nav">
              <ion-button fill="clear" size="small" (click)="step(-1)"><ion-icon slot="icon-only" name="chevron-back"></ion-icon></ion-button>
              <span class="nav-label">{{ planLabel() }}</span>
              <ion-button fill="clear" size="small" (click)="step(1)"><ion-icon slot="icon-only" name="chevron-forward"></ion-icon></ion-button>
            </div>
            @for (day of planDays(); track day.date) {
              <ion-card>
                <ion-card-header><ion-card-title>{{ dayLabel(day.date) }}</ion-card-title></ion-card-header>
                <ion-card-content>
                  @for (m of day.meals; track m.meal_type + m.member) {
                    <div class="line"><span class="cap">{{ m.meal_type }}</span><span>{{ m.items }}</span></div>
                  }
                </ion-card-content>
              </ion-card>
            } @empty {
              <p class="muted">Nothing planned.</p>
            }
          }

          @case ('diary') {
            <div class="nav">
              <ion-button fill="clear" size="small" (click)="stepDay(-1)"><ion-icon slot="icon-only" name="chevron-back"></ion-icon></ion-button>
              <span class="nav-label">{{ diaryDate() }}</span>
              <ion-button fill="clear" size="small" [disabled]="isToday()" (click)="stepDay(1)"><ion-icon slot="icon-only" name="chevron-forward"></ion-icon></ion-button>
            </div>
            @for (e of diary(); track e.member) {
              <ion-card>
                <ion-card-header><ion-card-title class="cap">{{ e.member }}</ion-card-title></ion-card-header>
                <ion-card-content>
                  <div class="kpis">
                    <div><span class="muted">kcal</span> {{ e.totals.kcal | number:'1.0-0' }}{{ e.kcal_target ? ' / ' + e.kcal_target : '' }}</div>
                    <div><span class="muted">P</span> {{ e.totals.protein_g | number:'1.0-0' }}g</div>
                    <div><span class="muted">C</span> {{ e.totals.carbs_g | number:'1.0-0' }}g</div>
                    <div><span class="muted">F</span> {{ e.totals.fat_g | number:'1.0-0' }}g</div>
                    <div><span class="muted">water</span> {{ e.hydration.ml_total }} ml</div>
                  </div>
                  @for (meal of e.meals; track meal.meal_type + meal.description) {
                    <div class="line"><span class="cap">{{ meal.meal_type }}</span><span>{{ meal.description }}</span><span class="muted">{{ meal.kcal_total ? (meal.kcal_total | number:'1.0-0') + ' kcal' : '' }}</span></div>
                  }
                </ion-card-content>
              </ion-card>
            } @empty {
              <p class="muted">No meals logged.</p>
            }

            @if (history().length) {
              <ion-card>
                <ion-card-header><ion-card-title>kcal per day (last 30)</ion-card-title></ion-card-header>
                <ion-card-content>
                  <div class="chart">
                    @for (d of history(); track d.day) {
                      <div class="chart-col">
                        <div class="chart-bar" [style.height.%]="dayHeight(d)"></div>
                      </div>
                    }
                  </div>
                  <ion-list>
                    @for (d of history(); track d.day) {
                      <ion-item lines="full" button (click)="openDay(d.day)">
                        <ion-label>{{ d.day }}</ion-label>
                        <ion-note slot="end">{{ d.meals }} meals · {{ d.kcal | number:'1.0-0' }} kcal</ion-note>
                      </ion-item>
                    }
                  </ion-list>
                </ion-card-content>
              </ion-card>
            }
          }

          @case ('shopping') {
            <ion-card>
              <ion-card-content>
                @if (shoppingCost(); as c) {
                  @if (c.priced) { <ion-note>Estimated {{ c.total | number:'1.2-2' }} ({{ c.priced }}/{{ c.count }} priced)</ion-note> }
                }
                <ion-list>
                  @for (it of shopping(); track it.id) {
                    <ion-item lines="full">
                      <ion-checkbox slot="start" [checked]="it.checked" (ionChange)="toggle(it)"></ion-checkbox>
                      <ion-label [class.done]="it.checked">{{ it.name }}</ion-label>
                      <ion-note slot="end">{{ it.qty }}</ion-note>
                    </ion-item>
                  } @empty {
                    <ion-item lines="none"><ion-label class="muted">List is empty.</ion-label></ion-item>
                  }
                </ion-list>
              </ion-card-content>
            </ion-card>
          }

          @case ('pantry') {
            @if (expiring().length) {
              <ion-card>
                <ion-card-header><ion-card-title>Expiring soon</ion-card-title></ion-card-header>
                <ion-card-content>
                  @for (it of expiring(); track it.name) {
                    <div class="line"><span>{{ it.name }}</span><span class="muted">{{ it.expires_on }}</span></div>
                  }
                </ion-card-content>
              </ion-card>
            }
            <ion-card>
              <ion-card-header><ion-card-title>Pantry</ion-card-title></ion-card-header>
              <ion-card-content>
                @for (it of pantry(); track it.name) {
                  <div class="line"><span>{{ it.name }}</span><span class="muted">{{ it.qty }}</span></div>
                } @empty {
                  <p class="muted">Pantry is empty.</p>
                }
              </ion-card-content>
            </ion-card>
          }
        }

      </div>
    </ion-content>
  `,
  styles: [`
    .nav { display: flex; align-items: center; justify-content: center; gap: 8px; margin: 8px 0 12px; }
    .nav-label { font-weight: 600; min-width: 150px; text-align: center; text-transform: capitalize; }
    .line { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; padding: 6px 0; }
    .line span:nth-child(2) { flex: 1; }
    .cap { text-transform: capitalize; font-weight: 600; min-width: 84px; }
    .muted { color: var(--laria-text-muted); }
    .done { text-decoration: line-through; color: var(--laria-text-muted); }
    .kpis { display: flex; flex-wrap: wrap; gap: 16px; font-size: 14px; margin-bottom: 10px; }
    .chart { display: flex; align-items: flex-end; gap: 3px; height: 100px; margin-bottom: 8px; }
    .chart-col { flex: 1; display: flex; align-items: flex-end; height: 100%; }
    .chart-bar { width: 100%; min-height: 2px; background: var(--ion-color-primary); border-radius: 3px 3px 0 0; }
  `],
})
export class FoodPage implements OnInit {
  private readonly food = inject(FoodService);

  readonly tab = signal<Tab>('plan');
  readonly planSpan = signal<PlanSpan>('week');
  readonly planOffset = signal(0);
  readonly plan = signal<PlanMeal[]>([]);

  readonly diaryDate = signal(todayIso());
  readonly diary = signal<DiaryEntry[]>([]);
  readonly history = signal<LoggedDay[]>([]);

  readonly shopping = signal<ShoppingItem[]>([]);
  readonly shoppingCost = signal<{ total: number; priced: number; count: number } | null>(null);
  readonly pantry = signal<PantryItem[]>([]);
  readonly expiring = signal<PantryItem[]>([]);

  readonly planDays = computed<PlanDay[]>(() => {
    const byDay = new Map<string, PlanMeal[]>();
    for (const meal of this.plan()) {
      const meals = byDay.get(meal.date) ?? [];
      meals.push(meal);
      byDay.set(meal.date, meals);
    }
    return [...byDay.entries()].map(([date, meals]) => ({ date, meals }));
  });

  constructor() {
    addIcons({ chevronBack, chevronForward, downloadOutline });
  }

  ngOnInit(): void {
    this.loadPlan();
  }

  changeTab(event: CustomEvent): void {
    const tab = event.detail.value as Tab;
    this.tab.set(tab);
    if (tab === 'plan') {
      this.loadPlan();
    } else if (tab === 'diary') {
      this.loadDiary();
    } else if (tab === 'shopping') {
      this.food.shopping().subscribe((s) => {
        this.shopping.set(s.items);
        this.shoppingCost.set(s.cost);
      });
    } else {
      this.food.pantry().subscribe((p) => {
        this.pantry.set(p.items);
        this.expiring.set(p.expiring);
      });
    }
  }

  // --- plan ---

  changeSpan(event: CustomEvent): void {
    this.planSpan.set(event.detail.value as PlanSpan);
    this.planOffset.set(0);
    this.loadPlan();
  }

  step(direction: number): void {
    this.planOffset.update((o) => o + direction);
    this.loadPlan();
  }

  private loadPlan(): void {
    const [from, to] = this.planRange();
    this.food.plan(from, to).subscribe((p) => this.plan.set(p));
  }

  private planRange(): [string, string] {
    const now = new Date();
    if (this.planSpan() === 'week') {
      const monday = startOfWeek(now);
      monday.setDate(monday.getDate() + this.planOffset() * 7);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      return [iso(monday), iso(sunday)];
    }
    const first = new Date(now.getFullYear(), now.getMonth() + this.planOffset(), 1);
    const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
    return [iso(first), iso(last)];
  }

  planLabel(): string {
    const [from, to] = this.planRange();
    if (this.planSpan() === 'month') {
      return new Date(from).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    }
    return `${from} to ${to}`;
  }

  // --- diary ---

  private loadDiary(): void {
    this.food.diary(this.diaryDate()).subscribe((d) => this.diary.set(d.members));
    this.food.diaryHistory(30).subscribe((h) =>
      this.history.set([...h].sort((a, b) => a.day.localeCompare(b.day))));
  }

  stepDay(direction: number): void {
    const d = new Date(this.diaryDate());
    d.setDate(d.getDate() + direction);
    this.diaryDate.set(iso(d));
    this.loadDiary();
  }

  openDay(day: string): void {
    this.diaryDate.set(day);
    this.loadDiary();
  }

  isToday(): boolean {
    return this.diaryDate() >= todayIso();
  }

  dayHeight(day: LoggedDay): number {
    const largest = Math.max(1, ...this.history().map((d) => d.kcal));
    return (day.kcal / largest) * 100;
  }

  exportCsv(): void {
    this.food.exportCsv().subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'laria_diary.csv';
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  // --- shopping / pantry ---

  toggle(item: ShoppingItem): void {
    this.food.toggleShopping(item.id).subscribe(() =>
      this.food.shopping().subscribe((s) => {
        this.shopping.set(s.items);
        this.shoppingCost.set(s.cost);
      }));
  }

  dayLabel(date: string): string {
    return new Date(date).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
  }
}

function todayIso(): string {
  return iso(new Date());
}

function startOfWeek(date: Date): Date {
  const result = new Date(date);
  const weekday = (result.getDay() + 6) % 7;
  result.setDate(result.getDate() - weekday);
  return result;
}

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}
