import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList, IonItem,
  IonLabel, IonCheckbox, IonSegment, IonSegmentButton, IonNote,
} from '@ionic/angular/standalone';
import {
  DiaryEntry, FoodService, PantryItem, PlanMeal, ShoppingItem,
} from '../../core/food.service';

type Tab = 'plan' | 'diary' | 'shopping' | 'pantry';

interface PlanDay {
  date: string;
  meals: PlanMeal[];
}

/** Food overview with a plan / diary / shopping / pantry switch.
 *
 * Plan groups this week's meals by day; diary shows each member's nutrition for
 * today against their targets; shopping lets items be ticked off; pantry lists
 * stock with the soon-to-expire items called out. Each tab loads its own data
 * the first time it is shown.
 */
@Component({
  selector: 'app-food',
  standalone: true,
  imports: [
    DecimalPipe, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
    IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList, IonItem,
    IonLabel, IonCheckbox, IonSegment, IonSegmentButton, IonNote,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Food</ion-title>
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
            @for (day of planDays(); track day.date) {
              <ion-card>
                <ion-card-header><ion-card-title>{{ dayLabel(day.date) }}</ion-card-title></ion-card-header>
                <ion-card-content>
                  @for (m of day.meals; track m.meal_type + m.member) {
                    <div class="line">
                      <span class="cap">{{ m.meal_type }}</span>
                      <span>{{ m.items }}</span>
                    </div>
                  }
                </ion-card-content>
              </ion-card>
            } @empty {
              <p class="muted">No meals planned for this week.</p>
            }
          }

          @case ('diary') {
            @for (e of diary(); track e.member) {
              <ion-card>
                <ion-card-header>
                  <ion-card-title class="cap">{{ e.member }}</ion-card-title>
                </ion-card-header>
                <ion-card-content>
                  <div class="kpis">
                    <div><span class="muted">kcal</span> {{ e.totals.kcal | number:'1.0-0' }}{{ e.kcal_target ? ' / ' + e.kcal_target : '' }}</div>
                    <div><span class="muted">P</span> {{ e.totals.protein_g | number:'1.0-0' }}g</div>
                    <div><span class="muted">C</span> {{ e.totals.carbs_g | number:'1.0-0' }}g</div>
                    <div><span class="muted">F</span> {{ e.totals.fat_g | number:'1.0-0' }}g</div>
                    <div><span class="muted">water</span> {{ e.hydration.ml_total }} ml</div>
                  </div>
                  @for (meal of e.meals; track meal.meal_type + meal.description) {
                    <div class="line">
                      <span class="cap">{{ meal.meal_type }}</span>
                      <span>{{ meal.description }}</span>
                      <span class="muted">{{ meal.kcal_total ? (meal.kcal_total | number:'1.0-0') + ' kcal' : '' }}</span>
                    </div>
                  }
                </ion-card-content>
              </ion-card>
            } @empty {
              <p class="muted">No meals logged today.</p>
            }
          }

          @case ('shopping') {
            <ion-card>
              <ion-card-content>
                @if (shoppingCost(); as c) {
                  @if (c.priced) {
                    <ion-note>Estimated {{ c.total | number:'1.2-2' }} ({{ c.priced }}/{{ c.count }} priced)</ion-note>
                  }
                }
                <ion-list>
                  @for (it of shopping(); track it.id) {
                    <ion-item lines="full">
                      <ion-checkbox slot="start" [checked]="it.checked"
                                    (ionChange)="toggle(it)"></ion-checkbox>
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
                    <div class="line">
                      <span>{{ it.name }}</span>
                      <span class="muted">{{ it.expires_on }}</span>
                    </div>
                  }
                </ion-card-content>
              </ion-card>
            }
            <ion-card>
              <ion-card-header><ion-card-title>Pantry</ion-card-title></ion-card-header>
              <ion-card-content>
                @for (it of pantry(); track it.name) {
                  <div class="line">
                    <span>{{ it.name }}</span>
                    <span class="muted">{{ it.qty }}</span>
                  </div>
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
    .line { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; padding: 6px 0; }
    .line span:nth-child(2) { flex: 1; }
    .cap { text-transform: capitalize; font-weight: 600; min-width: 84px; }
    .muted { color: var(--laria-text-muted); }
    .done { text-decoration: line-through; color: var(--laria-text-muted); }
    .kpis { display: flex; flex-wrap: wrap; gap: 16px; font-size: 14px; margin-bottom: 10px; }
  `],
})
export class FoodPage implements OnInit {
  private readonly food = inject(FoodService);

  readonly tab = signal<Tab>('plan');
  readonly plan = signal<PlanMeal[]>([]);
  readonly diary = signal<DiaryEntry[]>([]);
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

  ngOnInit(): void {
    this.load('plan');
  }

  changeTab(event: CustomEvent): void {
    const tab = event.detail.value as Tab;
    this.tab.set(tab);
    this.load(tab);
  }

  /** Load the data the chosen tab needs. */
  private load(tab: Tab): void {
    if (tab === 'plan') {
      this.food.plan().subscribe((p) => this.plan.set(p));
    } else if (tab === 'diary') {
      this.food.diary().subscribe((d) => this.diary.set(d.members));
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

  toggle(item: ShoppingItem): void {
    this.food.toggleShopping(item.id).subscribe(() => this.load('shopping'));
  }

  dayLabel(date: string): string {
    return new Date(date).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
  }
}
