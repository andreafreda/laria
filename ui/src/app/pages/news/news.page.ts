import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonItem, IonInput,
  IonTextarea, IonButton, IonNote, IonLabel,
} from '@ionic/angular/standalone';
import { Briefing, NewsService, parseTopics } from '../../core/news.service';

/** Manage scheduled news briefings.
 *
 * A briefing is a set of topics and a cron time; at each scheduled time the
 * assistant searches the web and sends a summary over Telegram. Topics are
 * entered one per line, with an optional "| site1, site2" to limit a topic to
 * certain sources. New briefings start firing once the Telegram process reloads
 * them.
 */
@Component({
  selector: 'app-news',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
    IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonItem, IonInput,
    IonTextarea, IonButton, IonNote, IonLabel,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>News briefings</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">

        @for (b of briefings(); track b.id) {
          <ion-card>
            <ion-card-content>
              <div class="head">
                <span class="cron">{{ b.cron }}</span>
                <ion-button fill="clear" color="danger" size="small"
                            (click)="remove(b)">Delete</ion-button>
              </div>
              @for (t of b.topics; track t.topic) {
                <div class="topic">
                  {{ t.topic }}
                  @if (t.sources.length) { <span class="muted">({{ t.sources.join(', ') }})</span> }
                </div>
              }
              <ion-note>Up to {{ b.num_news }} items per topic</ion-note>
            </ion-card-content>
          </ion-card>
        } @empty {
          <p class="muted">No briefings yet.</p>
        }

        <ion-card>
          <ion-card-header><ion-card-title>New briefing</ion-card-title></ion-card-header>
          <ion-card-content>
            <ion-item>
              <ion-textarea label="Topics (one per line, optional | site1, site2)"
                            labelPlacement="stacked" [autoGrow]="true" [rows]="3"
                            [(ngModel)]="topicsText"
                            placeholder="ai
football | gazzetta.it"></ion-textarea>
            </ion-item>
            <ion-item>
              <ion-input label="Cron (min hour day month weekday)" labelPlacement="stacked"
                         [(ngModel)]="cron" placeholder="0 8 * * *"></ion-input>
            </ion-item>
            <ion-item>
              <ion-input label="Max items per topic" labelPlacement="stacked" type="number"
                         [(ngModel)]="numNews"></ion-input>
            </ion-item>
            @if (error()) { <ion-note color="danger">{{ error() }}</ion-note> }
            <ion-button expand="block" class="ion-margin-top"
                        [disabled]="busy()" (click)="create()">Add briefing</ion-button>
          </ion-card-content>
        </ion-card>

      </div>
    </ion-content>
  `,
  styles: [`
    .head { display: flex; align-items: center; justify-content: space-between; }
    .cron { font-weight: 600; }
    .topic { font-size: 14px; padding: 2px 0; }
    .muted { color: var(--laria-text-muted); }
  `],
})
export class NewsPage implements OnInit {
  private readonly news = inject(NewsService);

  readonly briefings = signal<Briefing[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');

  topicsText = '';
  cron = '0 8 * * *';
  numNews = 5;

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.news.briefings().subscribe((b) => this.briefings.set(b));
  }

  create(): void {
    const topics = parseTopics(this.topicsText);
    if (!topics.length || !this.cron.trim()) {
      this.error.set('Add at least one topic and a cron time.');
      return;
    }
    this.error.set('');
    this.busy.set(true);
    this.news.createBriefing(topics, this.cron.trim(), Number(this.numNews) || 5).subscribe({
      next: () => {
        this.topicsText = '';
        this.busy.set(false);
        this.reload();
      },
      error: () => {
        this.error.set('Could not create the briefing.');
        this.busy.set(false);
      },
    });
  }

  remove(briefing: Briefing): void {
    this.news.deleteBriefing(briefing.id).subscribe(() => this.reload());
  }
}
