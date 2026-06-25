import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonButton,
  IonFooter, IonInput, IonIcon,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { logOutOutline, send } from 'ionicons/icons';
import { AuthService } from '../../core/auth.service';
import { ChatService } from '../../core/chat.service';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

/** The conversation view: a scrolling list of turns and an input to send one.
 *  Replies come from POST /api/chat; the user identity is the login token. */
@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonButton, IonFooter, IonInput, IonIcon,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-title>LARIA</ion-title>
        <ion-buttons slot="end">
          <ion-button (click)="logout()" aria-label="Sign out">
            <ion-icon slot="icon-only" name="log-out-outline"></ion-icon>
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      @for (message of messages(); track $index) {
        <div class="bubble" [class.user]="message.role === 'user'">{{ message.text }}</div>
      }
      @if (sending()) {
        <div class="bubble assistant">…</div>
      }
    </ion-content>

    <ion-footer>
      <ion-toolbar>
        <ion-input [(ngModel)]="draft" placeholder="Ask LARIA…"
                   (keyup.enter)="send()" [disabled]="sending()"></ion-input>
        <ion-buttons slot="end">
          <ion-button (click)="send()" [disabled]="sending()" aria-label="Send">
            <ion-icon slot="icon-only" name="send"></ion-icon>
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-footer>
  `,
  styles: [`
    .bubble {
      max-width: 80%;
      margin: 6px 0;
      padding: 10px 14px;
      border-radius: 14px;
      background: var(--ion-color-light);
      white-space: pre-wrap;
    }
    .bubble.user {
      margin-left: auto;
      background: var(--ion-color-primary);
      color: var(--ion-color-primary-contrast);
    }
  `],
})
export class ChatPage {
  private readonly chat = inject(ChatService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly messages = signal<Message[]>([]);
  readonly sending = signal(false);
  draft = '';

  constructor() {
    addIcons({ logOutOutline, send });
  }

  send(): void {
    const text = this.draft.trim();
    if (!text || this.sending()) {
      return;
    }
    this.append({ role: 'user', text });
    this.draft = '';
    this.sending.set(true);
    this.chat.send(text).subscribe({
      next: (res) => {
        this.append({ role: 'assistant', text: res.reply });
        this.sending.set(false);
      },
      error: () => {
        this.append({ role: 'assistant', text: 'Something went wrong. Please try again.' });
        this.sending.set(false);
      },
    });
  }

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }

  private append(message: Message): void {
    this.messages.update((list) => [...list, message]);
  }
}
