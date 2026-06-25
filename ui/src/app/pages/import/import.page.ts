import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton,
  IonCard, IonCardContent, IonItem, IonInput, IonButton, IonNote,
} from '@ionic/angular/standalone';
import { FinanceService } from '../../core/finance.service';

/** Upload a BancoPosta or Postepay statement file and import its movements into
 *  an account. Shows the import counts; duplicates are skipped server-side. */
@Component({
  selector: 'app-import',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonBackButton, IonCard, IonCardContent, IonItem, IonInput, IonButton, IonNote,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/dashboard"></ion-back-button></ion-buttons>
        <ion-title>Import statement</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <ion-card>
        <ion-card-content>
          <ion-item>
            <ion-input label="Account" labelPlacement="stacked"
                       [(ngModel)]="account" placeholder="e.g. checking"></ion-input>
          </ion-item>
          <div class="ion-padding-vertical">
            <input type="file" accept=".csv,.xlsx,.txt" (change)="pick($event)" />
          </div>

          @if (result()) {
            <ion-note color="success">
              Imported {{ result()!.inserted }}, skipped {{ result()!.duplicates }} duplicates
              ({{ result()!.format }}).
            </ion-note>
          }
          @if (error()) { <ion-note color="danger">{{ error() }}</ion-note> }

          <ion-button expand="block" class="ion-margin-top"
                      [disabled]="busy() || !file || !account.trim()"
                      (click)="upload()">
            {{ busy() ? 'Importing…' : 'Import' }}
          </ion-button>
        </ion-card-content>
      </ion-card>
    </ion-content>
  `,
})
export class ImportPage {
  private readonly finance = inject(FinanceService);

  account = '';
  file: File | null = null;
  readonly busy = signal(false);
  readonly result = signal<import('../../core/finance.service').ImportResult | null>(null);
  readonly error = signal('');

  pick(event: Event): void {
    this.file = (event.target as HTMLInputElement).files?.[0] ?? null;
  }

  upload(): void {
    if (!this.file || !this.account.trim()) {
      return;
    }
    this.error.set('');
    this.result.set(null);
    this.busy.set(true);
    this.finance.importStatement(this.account.trim(), this.file).subscribe({
      next: (res) => {
        this.result.set(res);
        this.busy.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.error ?? 'Import failed');
        this.busy.set(false);
      },
    });
  }
}
