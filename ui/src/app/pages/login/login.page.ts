import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonItem, IonInput,
  IonButton, IonText, IonList,
} from '@ionic/angular/standalone';
import { AuthService } from '../../core/auth.service';

/** Username/password login. On success it routes to chat, or to the password
 *  change page when the account is on a temporary password. */
@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonItem,
    IonInput, IonButton, IonText, IonList,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-title>LARIA</ion-title>
      </ion-toolbar>
    </ion-header>
    <ion-content class="ion-padding">
      <ion-list>
        <ion-item>
          <ion-input label="Username" labelPlacement="stacked"
                     [(ngModel)]="username" autocomplete="username"></ion-input>
        </ion-item>
        <ion-item>
          <ion-input label="Password" labelPlacement="stacked" type="password"
                     [(ngModel)]="password" autocomplete="current-password"
                     (keyup.enter)="submit()"></ion-input>
        </ion-item>
      </ion-list>

      @if (error) {
        <ion-text color="danger"><p class="ion-padding-start">{{ error }}</p></ion-text>
      }

      <ion-button expand="block" class="ion-margin-top"
                  [disabled]="loading" (click)="submit()">
        {{ loading ? 'Signing in…' : 'Sign in' }}
      </ion-button>
    </ion-content>
  `,
})
export class LoginPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  username = '';
  password = '';
  error = '';
  loading = false;

  submit(): void {
    if (!this.username || !this.password) {
      this.error = 'Enter username and password';
      return;
    }
    this.error = '';
    this.loading = true;
    this.auth.login(this.username, this.password).subscribe({
      next: () => {
        this.loading = false;
        this.router.navigateByUrl(this.auth.mustChange() ? '/change-password' : '/chat');
      },
      error: () => {
        this.loading = false;
        this.error = 'Invalid username or password';
      },
    });
  }
}
