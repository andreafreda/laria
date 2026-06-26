import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonItem, IonInput,
  IonButton, IonNote, IonSegment, IonSegmentButton, IonLabel,
} from '@ionic/angular/standalone';
import { Reminder, RemindersService } from '../../core/reminders.service';

type Mode = 'once' | 'repeat';

/** Manage reminders: one-shot (a date and time) or recurring (a cron). The
 *  scheduler in the Telegram process delivers them; new ones start firing once
 *  that process next reloads active reminders. */
@Component({
  selector: 'app-reminders',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
    IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonItem, IonInput,
    IonButton, IonNote, IonSegment, IonSegmentButton, IonLabel,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Reminders</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">

        @for (r of reminders(); track r.id) {
          <ion-card>
            <ion-card-content>
              <div class="head">
                <span class="message">{{ r.message }}</span>
                <ion-button fill="clear" color="danger" size="small"
                            (click)="remove(r)">Delete</ion-button>
              </div>
              @if (r.recurring) {
                <span class="when">repeat · {{ r.recurring }}</span>
              } @else {
                <span class="when">once · {{ r.remind_at }}</span>
              }
            </ion-card-content>
          </ion-card>
        } @empty {
          <p class="muted">No reminders yet.</p>
        }

        <ion-card>
          <ion-card-header><ion-card-title>New reminder</ion-card-title></ion-card-header>
          <ion-card-content>
            <ion-item>
              <ion-input label="Message" labelPlacement="stacked"
                         [(ngModel)]="message" placeholder="Take medicine"></ion-input>
            </ion-item>

            <ion-segment [(ngModel)]="mode" class="ion-margin-top">
              <ion-segment-button value="once"><ion-label>Once</ion-label></ion-segment-button>
              <ion-segment-button value="repeat"><ion-label>Repeat</ion-label></ion-segment-button>
            </ion-segment>

            @if (mode === 'once') {
              <ion-item>
                <ion-input label="When" labelPlacement="stacked" type="datetime-local"
                           [(ngModel)]="remindAt"></ion-input>
              </ion-item>
            } @else {
              <ion-item>
                <ion-input label="Cron (min hour day month weekday)" labelPlacement="stacked"
                           [(ngModel)]="cron" placeholder="0 9 * * *"></ion-input>
              </ion-item>
            }

            @if (error()) { <ion-note color="danger">{{ error() }}</ion-note> }
            <ion-button expand="block" class="ion-margin-top"
                        [disabled]="busy()" (click)="create()">Add reminder</ion-button>
          </ion-card-content>
        </ion-card>

      </div>
    </ion-content>
  `,
  styles: [`
    .head { display: flex; align-items: center; justify-content: space-between; }
    .message { font-weight: 600; }
    .when { font-size: 14px; color: var(--laria-text-muted); }
    .muted { color: var(--laria-text-muted); }
  `],
})
export class RemindersPage implements OnInit {
  private readonly service = inject(RemindersService);

  readonly reminders = signal<Reminder[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');

  message = '';
  mode: Mode = 'once';
  remindAt = '';
  cron = '0 9 * * *';

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.service.reminders().subscribe((r) => this.reminders.set(r));
  }

  create(): void {
    if (!this.message.trim()) {
      this.error.set('Add a message.');
      return;
    }
    const once = this.mode === 'once';
    if (once && !this.remindAt) {
      this.error.set('Pick a date and time.');
      return;
    }
    if (!once && !this.cron.trim()) {
      this.error.set('Add a cron time.');
      return;
    }
    this.error.set('');
    this.busy.set(true);
    // datetime-local gives 'YYYY-MM-DDTHH:MM'; the backend stores a space-separated
    // local time, so swap the 'T' for a space.
    const remindAt = once ? this.remindAt.replace('T', ' ') : null;
    const recurring = once ? null : this.cron.trim();
    this.service.create(this.message.trim(), remindAt, recurring).subscribe({
      next: () => {
        this.message = '';
        this.busy.set(false);
        this.reload();
      },
      error: () => {
        this.error.set('Could not create the reminder.');
        this.busy.set(false);
      },
    });
  }

  remove(reminder: Reminder): void {
    this.service.remove(reminder.id).subscribe(() => this.reload());
  }
}
