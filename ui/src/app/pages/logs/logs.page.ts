import { Component, OnInit, inject, signal } from '@angular/core';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonButton, IonCard, IonCardContent, IonNote,
} from '@ionic/angular/standalone';
import { ErrorLog, NewsService } from '../../core/news.service';

/** System error log (owner only).
 *
 * Shows the most recent captured errors so the owner can see what went wrong
 * without shell access, and clear them once handled.
 */
@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [
    IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
    IonButton, IonCard, IonCardContent, IonNote,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>System log</ion-title>
        <ion-buttons slot="end">
          <ion-button color="danger" (click)="clear()" [disabled]="!logs().length">Clear</ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">
        @for (log of logs(); track log.ts + log.message) {
          <ion-card>
            <ion-card-content>
              <ion-note>{{ log.ts }} · {{ log.source }} · {{ log.level }}</ion-note>
              <div class="msg">{{ log.message }}</div>
            </ion-card-content>
          </ion-card>
        } @empty {
          <p class="muted">No errors logged.</p>
        }
      </div>
    </ion-content>
  `,
  styles: [`
    .msg { margin-top: 4px; white-space: pre-wrap; font-size: 14px; }
    .muted { color: var(--laria-text-muted); }
  `],
})
export class LogsPage implements OnInit {
  private readonly news = inject(NewsService);

  readonly logs = signal<ErrorLog[]>([]);

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.news.logs().subscribe((l) => this.logs.set(l));
  }

  clear(): void {
    this.news.clearLogs().subscribe(() => this.reload());
  }
}
