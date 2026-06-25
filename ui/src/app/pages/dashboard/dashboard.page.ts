import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList, IonItem,
  IonLabel, IonProgressBar,
} from '@ionic/angular/standalone';
import { Balance, ExpenseSummary, FinanceService, Goal } from '../../core/finance.service';

/** Finance overview: account balances, this period's income vs expenses, and
 *  progress on savings goals. Reads the /api/finance read models. */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DecimalPipe, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonMenuButton, IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList,
    IonItem, IonLabel, IonProgressBar,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Finance</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <ion-card>
        <ion-card-header><ion-card-title>Balances</ion-card-title></ion-card-header>
        <ion-card-content>
          <ion-list>
            @for (b of balances(); track b.account) {
              <ion-item>
                <ion-label>{{ b.account }}</ion-label>
                <ion-label slot="end">{{ b.balance | number:'1.2-2' }}</ion-label>
              </ion-item>
            } @empty {
              <ion-item><ion-label>No accounts yet</ion-label></ion-item>
            }
          </ion-list>
        </ion-card-content>
      </ion-card>

      @if (summary(); as s) {
        <ion-card>
          <ion-card-header><ion-card-title>This period</ion-card-title></ion-card-header>
          <ion-card-content>
            <p>Income: {{ s.income | number:'1.2-2' }}</p>
            <p>Expenses: {{ s.expenses | number:'1.2-2' }}</p>
            <p><strong>Net: {{ s.net | number:'1.2-2' }}</strong></p>
          </ion-card-content>
        </ion-card>
      }

      <ion-card>
        <ion-card-header><ion-card-title>Savings goals</ion-card-title></ion-card-header>
        <ion-card-content>
          @for (g of goals(); track g.name) {
            <div class="goal">
              <div class="goal-row">
                <span>{{ g.name }}</span>
                <span>{{ g.saved | number:'1.0-0' }} / {{ g.target | number:'1.0-0' }}</span>
              </div>
              <ion-progress-bar [value]="g.perc / 100"></ion-progress-bar>
            </div>
          } @empty {
            <p>No goals yet</p>
          }
        </ion-card-content>
      </ion-card>
    </ion-content>
  `,
  styles: [`
    .goal { margin-bottom: 12px; }
    .goal-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
  `],
})
export class DashboardPage implements OnInit {
  private readonly finance = inject(FinanceService);

  readonly balances = signal<Balance[]>([]);
  readonly summary = signal<ExpenseSummary | null>(null);
  readonly goals = signal<Goal[]>([]);

  ngOnInit(): void {
    this.finance.balances().subscribe((b) => this.balances.set(b));
    this.finance.summary().subscribe((s) => this.summary.set(s));
    this.finance.goals().subscribe((g) => this.goals.set(g));
  }
}
