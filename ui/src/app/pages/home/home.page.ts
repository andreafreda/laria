import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardContent, IonIcon,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { walletOutline, restaurantOutline, newspaperOutline, chatbubbleOutline } from 'ionicons/icons';
import { Balance, FinanceService } from '../../core/finance.service';
import { FoodService, PlanMeal, ShoppingItem } from '../../core/food.service';
import { NewsService } from '../../core/news.service';

/** Landing page: a glance at the household plus quick links.
 *
 * Shows this month's net and the total balance as headline numbers, four links
 * into the main sections with a small live hint each, and a short "today" list
 * (planned meals and open shopping items).
 */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    DecimalPipe, RouterLink, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonMenuButton, IonCard, IonCardContent, IonIcon,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Home</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">

        <div class="metrics">
          <div class="metric">
            <div class="metric-label">Net this month</div>
            <div class="metric-value" [class.income]="net() >= 0" [class.expense]="net() < 0">
              {{ net() | number:'1.2-2' }}
            </div>
          </div>
          <div class="metric">
            <div class="metric-label">Total balance</div>
            <div class="metric-value">{{ totalBalance() | number:'1.2-2' }}</div>
          </div>
        </div>

        <div class="tiles">
          <ion-card routerLink="/dashboard" button>
            <ion-card-content>
              <ion-icon name="wallet-outline"></ion-icon>
              <div class="tile-title">Finance</div>
              <div class="tile-hint">{{ net() | number:'1.0-0' }} net</div>
            </ion-card-content>
          </ion-card>
          <ion-card routerLink="/food" button>
            <ion-card-content>
              <ion-icon name="restaurant-outline"></ion-icon>
              <div class="tile-title">Food</div>
              <div class="tile-hint">{{ todayMeals().length }} planned today</div>
            </ion-card-content>
          </ion-card>
          <ion-card routerLink="/news" button>
            <ion-card-content>
              <ion-icon name="newspaper-outline"></ion-icon>
              <div class="tile-title">News</div>
              <div class="tile-hint">{{ briefingCount() }} briefings</div>
            </ion-card-content>
          </ion-card>
          <ion-card routerLink="/chat" button>
            <ion-card-content>
              <ion-icon name="chatbubble-outline"></ion-icon>
              <div class="tile-title">Chat</div>
              <div class="tile-hint">Ask anything</div>
            </ion-card-content>
          </ion-card>
        </div>

        <ion-card>
          <ion-card-content>
            <div class="today-title">Today</div>
            @for (m of todayMeals(); track m.meal_type + m.member) {
              <div class="today-row"><span class="cap">{{ m.meal_type }}</span> {{ m.items }}</div>
            }
            @if (openShopping() > 0) {
              <div class="today-row">{{ openShopping() }} items on the shopping list</div>
            }
            @if (!todayMeals().length && openShopping() === 0) {
              <div class="muted">Nothing planned.</div>
            }
          </ion-card-content>
        </ion-card>

      </div>
    </ion-content>
  `,
  styles: [`
    .metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px; }
    .metric { background: var(--laria-surface-muted); border-radius: var(--laria-radius-sm); padding: 16px; }
    .metric-label { font-size: 13px; color: var(--laria-text-muted); }
    .metric-value { font-size: 24px; font-weight: 600; margin-top: 4px; }
    .metric-value.income { color: var(--ion-color-success); }
    .metric-value.expense { color: var(--ion-color-danger); }
    .tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 4px; }
    .tiles ion-card { margin: 0; }
    .tiles ion-icon { font-size: 24px; color: var(--ion-color-primary); }
    .tile-title { font-weight: 600; margin-top: 8px; }
    .tile-hint { font-size: 13px; color: var(--laria-text-muted); }
    .today-title { font-weight: 600; margin-bottom: 8px; }
    .today-row { font-size: 14px; padding: 3px 0; }
    .cap { text-transform: capitalize; font-weight: 600; }
    .muted { color: var(--laria-text-muted); font-size: 14px; }
  `],
})
export class HomePage implements OnInit {
  private readonly finance = inject(FinanceService);
  private readonly food = inject(FoodService);
  private readonly news = inject(NewsService);

  readonly balances = signal<Balance[]>([]);
  readonly net = signal(0);
  readonly todayMeals = signal<PlanMeal[]>([]);
  readonly openShopping = signal(0);
  readonly briefingCount = signal(0);

  readonly totalBalance = computed(() =>
    this.balances().reduce((sum, b) => sum + b.balance, 0));

  constructor() {
    addIcons({ walletOutline, restaurantOutline, newspaperOutline, chatbubbleOutline });
  }

  ngOnInit(): void {
    const today = new Date().toISOString().slice(0, 10);
    const monthStart = today.slice(0, 8) + '01';

    this.finance.balances().subscribe((b) => this.balances.set(b));
    this.finance.summary(monthStart, today).subscribe((s) => this.net.set(s.net));
    this.food.plan(today, today).subscribe((p) => this.todayMeals.set(p));
    this.food.shopping().subscribe((s) =>
      this.openShopping.set(s.items.filter((i: ShoppingItem) => !i.checked).length));
    this.news.briefings().subscribe((b) => this.briefingCount.set(b.length));
  }
}
