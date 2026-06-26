import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonButton, IonIcon, IonCard, IonCardHeader, IonCardTitle, IonCardContent,
  IonList, IonItem, IonLabel, IonProgressBar, IonSegment, IonSegmentButton,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { cloudUploadOutline, chevronBack, chevronForward } from 'ionicons/icons';
import {
  Balance, BudgetStatus, CategoryYear, ExpenseSummary, FinanceService, Goal, MonthTrend,
} from '../../core/finance.service';

type Period = 'week' | 'month' | 'year';

interface CategoryBar {
  category: string;
  amount: number;
  pct: number;
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Finance overview with a week / month / year switch.
 *
 * Week and month read the period summary (income, expenses, net, category
 * breakdown) for the selected range; year reads the twelve-month trend and the
 * per-category yearly spend. The arrows step through periods, capped at the
 * current one so a user cannot page into the future. Balances and savings goals
 * are running totals, shown under every period.
 */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DecimalPipe, RouterLink, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonMenuButton, IonButton, IonIcon, IonCard, IonCardHeader, IonCardTitle,
    IonCardContent, IonList, IonItem, IonLabel, IonProgressBar, IonSegment, IonSegmentButton,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Finance</ion-title>
        <ion-buttons slot="end">
          <ion-button routerLink="/import" aria-label="Import statement">
            <ion-icon slot="icon-only" name="cloud-upload-outline"></ion-icon>
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
      <ion-toolbar>
        <ion-segment [value]="period()" (ionChange)="changePeriod($event)">
          <ion-segment-button value="week"><ion-label>Week</ion-label></ion-segment-button>
          <ion-segment-button value="month"><ion-label>Month</ion-label></ion-segment-button>
          <ion-segment-button value="year"><ion-label>Year</ion-label></ion-segment-button>
        </ion-segment>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">

        <div class="period-nav">
          <ion-button fill="clear" size="small" (click)="step(-1)" aria-label="Previous">
            <ion-icon slot="icon-only" name="chevron-back"></ion-icon>
          </ion-button>
          <span class="period-label">{{ periodLabel() }}</span>
          <ion-button fill="clear" size="small" [disabled]="offset() >= 0"
                      (click)="step(1)" aria-label="Next">
            <ion-icon slot="icon-only" name="chevron-forward"></ion-icon>
          </ion-button>
        </div>

        <div class="metrics">
          <div class="metric">
            <div class="metric-label">Income</div>
            <div class="metric-value income">{{ income() | number:'1.2-2' }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Expenses</div>
            <div class="metric-value expense">{{ expenses() | number:'1.2-2' }}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Net</div>
            <div class="metric-value">{{ net() | number:'1.2-2' }}</div>
          </div>
        </div>

        @if (period() === 'month' && budgets().length) {
          <ion-card>
            <ion-card-header><ion-card-title>Budget</ion-card-title></ion-card-header>
            <ion-card-content>
              @for (b of budgets(); track b.category) {
                <div class="row">
                  <div class="row-top">
                    <span>{{ b.category }}</span>
                    <span>{{ b.spent | number:'1.0-0' }} / {{ b.budget | number:'1.0-0' }}
                      · {{ b.over ? 'over ' + (-b.remaining | number:'1.0-0') : (b.remaining | number:'1.0-0') + ' left' }}</span>
                  </div>
                  <div class="bar">
                    <div class="bar-fill" [class.warn]="b.perc >= 80 && !b.over" [class.over]="b.over"
                         [style.width.%]="b.perc > 100 ? 100 : b.perc"></div>
                  </div>
                </div>
              }
            </ion-card-content>
          </ion-card>
        }

        @if (period() === 'year' && trend().length) {
          <ion-card>
            <ion-card-header><ion-card-title>Expenses by month</ion-card-title></ion-card-header>
            <ion-card-content>
              <div class="chart">
                @for (m of trend(); track m.month) {
                  <div class="chart-col">
                    <div class="chart-bar" [style.height.%]="monthHeight(m)"></div>
                    <div class="chart-tick">{{ monthLabel(m.month) }}</div>
                  </div>
                }
              </div>
            </ion-card-content>
          </ion-card>
        }

        <ion-card>
          <ion-card-header><ion-card-title>Spending by category</ion-card-title></ion-card-header>
          <ion-card-content>
            @for (c of categories(); track c.category) {
              <div class="row">
                <div class="row-top">
                  <span>{{ c.category }}</span>
                  <span>{{ c.amount | number:'1.2-2' }}</span>
                </div>
                <div class="bar"><div class="bar-fill" [style.width.%]="c.pct"></div></div>
              </div>
            } @empty {
              <p class="muted">No spending in this period.</p>
            }
          </ion-card-content>
        </ion-card>

        <ion-card>
          <ion-card-header><ion-card-title>Balances</ion-card-title></ion-card-header>
          <ion-card-content>
            <ion-list>
              @for (b of balances(); track b.account) {
                <ion-item lines="none">
                  <ion-label>{{ b.account }}</ion-label>
                  <ion-label slot="end">{{ b.balance | number:'1.2-2' }}</ion-label>
                </ion-item>
              } @empty {
                <ion-item lines="none"><ion-label>No accounts yet</ion-label></ion-item>
              }
            </ion-list>
          </ion-card-content>
        </ion-card>

        <ion-card>
          <ion-card-header><ion-card-title>Savings goals</ion-card-title></ion-card-header>
          <ion-card-content>
            @for (g of goals(); track g.name) {
              <div class="row">
                <div class="row-top">
                  <span>{{ g.name }}</span>
                  <span class="muted">{{ g.saved | number:'1.0-0' }} / {{ g.target | number:'1.0-0' }}</span>
                </div>
                <ion-progress-bar [value]="g.perc / 100"></ion-progress-bar>
              </div>
            } @empty {
              <p class="muted">No goals yet.</p>
            }
          </ion-card-content>
        </ion-card>

      </div>
    </ion-content>
  `,
  styles: [`
    .period-nav { display: flex; align-items: center; justify-content: center; gap: 8px; margin: 4px 0 16px; }
    .period-label { font-weight: 600; min-width: 160px; text-align: center; text-transform: capitalize; }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 4px; }
    .metric { background: var(--laria-surface-muted); border-radius: var(--laria-radius-sm); padding: 14px; }
    .metric-label { font-size: 12px; color: var(--laria-text-muted); }
    .metric-value { font-size: 20px; font-weight: 600; margin-top: 2px; }
    .metric-value.income { color: var(--ion-color-success); }
    .metric-value.expense { color: var(--ion-color-danger); }
    .row { margin-bottom: 14px; }
    .row:last-child { margin-bottom: 0; }
    .row-top { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 6px; }
    .bar { background: var(--laria-surface-muted); border-radius: var(--laria-radius-pill); height: 8px; overflow: hidden; }
    .bar-fill { background: var(--ion-color-primary); height: 100%; border-radius: var(--laria-radius-pill); }
    .bar-fill.warn { background: #d97706; }
    .bar-fill.over { background: var(--ion-color-danger); }
    .muted { color: var(--laria-text-muted); font-size: 14px; }
    .chart { display: flex; align-items: flex-end; gap: 6px; height: 140px; }
    .chart-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
    .chart-bar { width: 100%; min-height: 2px; background: var(--ion-color-primary); border-radius: var(--laria-radius-sm) var(--laria-radius-sm) 0 0; }
    .chart-tick { font-size: 10px; color: var(--laria-text-muted); margin-top: 6px; }
  `],
})
export class DashboardPage implements OnInit {
  private readonly finance = inject(FinanceService);

  readonly period = signal<Period>('month');
  readonly offset = signal(0);

  readonly balances = signal<Balance[]>([]);
  readonly goals = signal<Goal[]>([]);
  readonly summary = signal<ExpenseSummary | null>(null);
  readonly trend = signal<MonthTrend[]>([]);
  readonly categoryYear = signal<CategoryYear[]>([]);
  readonly budgets = signal<BudgetStatus[]>([]);

  readonly income = computed(() => this.totals().income);
  readonly expenses = computed(() => this.totals().expenses);
  readonly net = computed(() => this.totals().net);

  readonly categories = computed<CategoryBar[]>(() => {
    const raw = this.period() === 'year'
      ? this.categoryYear().map((c) => ({ category: c.category, amount: Math.abs(c.total) }))
      : (this.summary()?.by_category ?? []).map((c) => ({ category: c.category, amount: Math.abs(c.total) }));
    const largest = Math.max(1, ...raw.map((r) => r.amount));
    return raw.map((r) => ({ ...r, pct: (r.amount / largest) * 100 }));
  });

  constructor() {
    addIcons({ cloudUploadOutline, chevronBack, chevronForward });
  }

  ngOnInit(): void {
    this.finance.balances().subscribe((b) => this.balances.set(b));
    this.finance.goals().subscribe((g) => this.goals.set(g));
    this.load();
  }

  changePeriod(event: CustomEvent): void {
    this.period.set(event.detail.value as Period);
    this.offset.set(0);
    this.load();
  }

  step(direction: number): void {
    const next = this.offset() + direction;
    if (next > 0) {
      return;
    }
    this.offset.set(next);
    this.load();
  }

  /** Fetch the data the current period needs: a summary for week/month, the
   *  twelve-month trend plus yearly categories for year. */
  private load(): void {
    if (this.period() === 'year') {
      const year = new Date().getFullYear() + this.offset();
      this.finance.trend(year).subscribe((t) => this.trend.set(t));
      this.finance.categoryYear(year).subscribe((c) => this.categoryYear.set(c));
      return;
    }
    const [from, to] = this.range();
    this.finance.summary(from, to).subscribe((s) => this.summary.set(s));
    if (this.period() === 'month') {
      const first = new Date(from);
      this.finance.budgetStatus(first.getFullYear(), first.getMonth() + 1)
        .subscribe((b) => this.budgets.set(b));
    } else {
      this.budgets.set([]);
    }
  }

  private totals(): { income: number; expenses: number; net: number } {
    if (this.period() === 'year') {
      const income = this.trend().reduce((sum, m) => sum + m.income, 0);
      // Keep the same sign convention as the week/month summary: expenses negative.
      const expenses = -this.trend().reduce((sum, m) => sum + Math.abs(m.expenses), 0);
      return { income, expenses, net: income + expenses };
    }
    const s = this.summary();
    return { income: s?.income ?? 0, expenses: s?.expenses ?? 0, net: s?.net ?? 0 };
  }

  monthLabel(month: number): string {
    return MONTH_LABELS[month - 1] ?? '';
  }

  monthHeight(month: MonthTrend): number {
    const largest = Math.max(1, ...this.trend().map((m) => Math.abs(m.expenses)));
    return (Math.abs(month.expenses) / largest) * 100;
  }

  periodLabel(): string {
    if (this.period() === 'year') {
      return String(new Date().getFullYear() + this.offset());
    }
    const [from, to] = this.range();
    if (this.period() === 'month') {
      return new Date(from).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    }
    return `${from} to ${to}`;
  }

  /** The [from, to] ISO date range for the selected week or month. */
  private range(): [string, string] {
    const now = new Date();
    if (this.period() === 'week') {
      const monday = startOfWeek(now);
      monday.setDate(monday.getDate() + this.offset() * 7);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      return [iso(monday), iso(sunday)];
    }
    const first = new Date(now.getFullYear(), now.getMonth() + this.offset(), 1);
    const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
    return [iso(first), iso(last)];
  }
}

/** Monday of the week containing ``date`` (weeks start on Monday). */
function startOfWeek(date: Date): Date {
  const result = new Date(date);
  const weekday = (result.getDay() + 6) % 7;
  result.setDate(result.getDate() - weekday);
  return result;
}

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}
