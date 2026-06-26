import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonItem, IonInput,
  IonButton, IonText, IonList,
} from '@ionic/angular/standalone';
import { AuthService } from '../../core/auth.service';

/** Set a new password. Shown after logging in with a temporary one (the server
 *  flags must_change), and reachable any time to rotate the password. */
@Component({
  selector: 'app-change-password',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonItem,
    IonInput, IonButton, IonText, IonList,
  ],
  template: `
    <ion-header>
      <ion-toolbar><ion-title>Change password</ion-title></ion-toolbar>
    </ion-header>
    <ion-content class="ion-padding">
      <ion-list>
        <ion-item>
          <ion-input label="New password" labelPlacement="stacked" type="password"
                     [(ngModel)]="password"></ion-input>
        </ion-item>
        <ion-item>
          <ion-input label="Confirm" labelPlacement="stacked" type="password"
                     [(ngModel)]="confirm" (keyup.enter)="submit()"></ion-input>
        </ion-item>
      </ion-list>

      @if (error) {
        <ion-text color="danger"><p class="ion-padding-start">{{ error }}</p></ion-text>
      }

      <ion-button expand="block" class="ion-margin-top"
                  [disabled]="loading" (click)="submit()">Save</ion-button>
    </ion-content>
  `,
})
export class ChangePasswordPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  password = '';
  confirm = '';
  error = '';
  loading = false;

  submit(): void {
    if (this.password.length < 8) {
      this.error = 'Use at least 8 characters';
      return;
    }
    if (this.password !== this.confirm) {
      this.error = 'Passwords do not match';
      return;
    }
    this.error = '';
    this.loading = true;
    this.auth.changePassword(this.password).subscribe({
      next: () => {
        this.loading = false;
        this.router.navigateByUrl('/home');
      },
      error: () => {
        this.loading = false;
        this.error = 'Could not change the password';
      },
    });
  }
}
