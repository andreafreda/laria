import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonButton, IonInput,
  IonSelect, IonSelectOption, IonNote, IonItem,
} from '@ionic/angular/standalone';
import { FoodService, Profile, WeightEntry } from '../../core/food.service';

const SEXES = ['', 'M', 'F'];
const GOALS = ['', 'maintain', 'lose', 'gain'];
const ACTIVITY = ['', 'sedentary', 'light', 'moderate', 'intense', 'very intense'];

/** Family nutrition profiles: view, edit, and weight history.
 *
 * Each member is a card showing the computed BMI and macro targets, with an
 * inline edit form. Saving recomputes BMI server-side and shows it back.
 */
@Component({
  selector: 'app-profiles',
  standalone: true,
  imports: [
    DecimalPipe, FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonMenuButton, IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonButton,
    IonInput, IonSelect, IonSelectOption, IonNote, IonItem,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Profiles</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">
        @for (p of profiles(); track p.member) {
          <ion-card>
            <ion-card-header>
              <ion-card-title class="cap">{{ p.member }}</ion-card-title>
            </ion-card-header>
            <ion-card-content>
              <div class="summary">
                {{ p.sex || '—' }} · {{ p.age || '—' }} ·
                {{ p.height_cm || '—' }} cm · {{ p.weight_kg || '—' }} kg
                @if (p.bmi) { · BMI {{ p.bmi }} }
              </div>
              <div class="summary">
                {{ p.goal || 'no goal' }} · {{ p.activity_level || 'no activity' }} ·
                {{ p.kcal_target ? p.kcal_target + ' kcal' : 'no target' }}
              </div>
              @if (p.macro_targets; as m) {
                <div class="summary muted">
                  P {{ m.protein_target_g }} / C {{ m.carbs_target_g }} / F {{ m.fat_target_g }} g
                </div>
              }
              @if (p.allergies || p.preferences || p.restrictions) {
                <div class="summary muted">
                  @if (p.allergies) { allergies: {{ p.allergies }}. }
                  @if (p.preferences) { likes: {{ p.preferences }}. }
                  @if (p.restrictions) { avoids: {{ p.restrictions }}. }
                </div>
              }

              <ion-button fill="clear" size="small" (click)="toggle(p.member)">
                {{ editing() === p.member ? 'Close' : 'Edit' }}
              </ion-button>

              @if (editing() === p.member) {
                <div class="form">
                  <ion-item>
                    <ion-select label="Sex" [(ngModel)]="form.sex" interface="popover">
                      @for (s of sexes; track s) { <ion-select-option [value]="s">{{ s || '—' }}</ion-select-option> }
                    </ion-select>
                  </ion-item>
                  <ion-item>
                    <ion-input label="Age" type="number" [(ngModel)]="form.age"></ion-input>
                  </ion-item>
                  <ion-item>
                    <ion-input label="Height cm" type="number" [(ngModel)]="form.height_cm"></ion-input>
                  </ion-item>
                  <ion-item>
                    <ion-input label="Weight kg" type="number" [(ngModel)]="form.weight_kg"></ion-input>
                  </ion-item>
                  <ion-item>
                    <ion-select label="Goal" [(ngModel)]="form.goal" interface="popover">
                      @for (g of goals; track g) { <ion-select-option [value]="g">{{ g || '—' }}</ion-select-option> }
                    </ion-select>
                  </ion-item>
                  <ion-item>
                    <ion-select label="Activity" [(ngModel)]="form.activity_level" interface="popover">
                      @for (a of activity; track a) { <ion-select-option [value]="a">{{ a || '—' }}</ion-select-option> }
                    </ion-select>
                  </ion-item>
                  <ion-item>
                    <ion-input label="kcal target" type="number" [(ngModel)]="form.kcal_target"></ion-input>
                  </ion-item>
                  <ion-item>
                    <ion-input label="Allergies" [(ngModel)]="form.allergies"></ion-input>
                  </ion-item>
                  <ion-item>
                    <ion-input label="Preferences" [(ngModel)]="form.preferences"></ion-input>
                  </ion-item>
                  <ion-item>
                    <ion-input label="Restrictions" [(ngModel)]="form.restrictions"></ion-input>
                  </ion-item>
                  <ion-button expand="block" class="ion-margin-top" (click)="save(p.member)">Save</ion-button>
                  @if (savedMsg()) { <ion-note color="success">{{ savedMsg() }}</ion-note> }
                </div>
              }

              @if (weights()[p.member]?.length) {
                <div class="weights">
                  <div class="muted">Weight history</div>
                  @for (w of weights()[p.member]; track w.logged_at) {
                    <div class="wrow">
                      <span>{{ w.logged_at }}</span>
                      <span>{{ w.weight_kg | number:'1.1-1' }} kg</span>
                    </div>
                  }
                </div>
              }
            </ion-card-content>
          </ion-card>
        } @empty {
          <p class="muted">No profiles yet.</p>
        }
      </div>
    </ion-content>
  `,
  styles: [`
    .cap { text-transform: capitalize; }
    .summary { font-size: 14px; padding: 2px 0; }
    .muted { color: var(--laria-text-muted); }
    .form { margin-top: 8px; }
    .weights { margin-top: 12px; }
    .wrow { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
  `],
})
export class ProfilesPage implements OnInit {
  private readonly food = inject(FoodService);

  readonly sexes = SEXES;
  readonly goals = GOALS;
  readonly activity = ACTIVITY;

  readonly profiles = signal<Profile[]>([]);
  readonly weights = signal<Record<string, WeightEntry[]>>({});
  readonly editing = signal<string | null>(null);
  readonly savedMsg = signal('');

  form: Partial<Profile> = {};

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.food.profiles().subscribe((profiles) => {
      this.profiles.set(profiles);
      for (const profile of profiles) {
        this.food.weight(profile.member).subscribe((history) =>
          this.weights.update((all) => ({ ...all, [profile.member]: history })));
      }
    });
  }

  toggle(member: string): void {
    this.savedMsg.set('');
    if (this.editing() === member) {
      this.editing.set(null);
      return;
    }
    const profile = this.profiles().find((p) => p.member === member);
    this.form = {
      sex: profile?.sex ?? '',
      age: profile?.age ?? null,
      height_cm: profile?.height_cm ?? null,
      weight_kg: profile?.weight_kg ?? null,
      goal: profile?.goal ?? '',
      activity_level: profile?.activity_level ?? '',
      kcal_target: profile?.kcal_target ?? null,
      allergies: profile?.allergies ?? '',
      preferences: profile?.preferences ?? '',
      restrictions: profile?.restrictions ?? '',
    };
    this.editing.set(member);
  }

  save(member: string): void {
    this.food.saveProfile(member, this.form).subscribe((result) => {
      this.savedMsg.set(result.bmi ? `Saved (BMI ${result.bmi})` : 'Saved');
      this.reload();
    });
  }
}
