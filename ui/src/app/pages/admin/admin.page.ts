import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList, IonItem,
  IonLabel, IonInput, IonSelect, IonSelectOption, IonCheckbox, IonButton, IonNote,
} from '@ionic/angular/standalone';
import { AdminService, AdminUser, Profile } from '../../core/admin.service';

/** Owner view to manage the household: see users and profiles, and create them.
 *  The server rejects non-owners (403), this page is offered only to the owner. */
@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons,
    IonMenuButton, IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonList,
    IonItem, IonLabel, IonInput, IonSelect, IonSelectOption, IonCheckbox,
    IonButton, IonNote,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Family</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <ion-card>
        <ion-card-header><ion-card-title>Profiles</ion-card-title></ion-card-header>
        <ion-card-content>
          <ion-list>
            @for (p of profiles(); track p.id) {
              <ion-item>
                <ion-label>{{ p.name }}</ion-label>
                @if (p.is_dependent) { <ion-note slot="end">dependent</ion-note> }
              </ion-item>
            } @empty { <ion-item><ion-label>No profiles</ion-label></ion-item> }
          </ion-list>
          <ion-item>
            <ion-input label="New profile" labelPlacement="stacked"
                       [(ngModel)]="newProfileName"></ion-input>
          </ion-item>
          <ion-item>
            <ion-checkbox [(ngModel)]="newProfileDependent">Dependent (child)</ion-checkbox>
          </ion-item>
          <ion-button expand="block" class="ion-margin-top"
                      (click)="addProfile()">Add profile</ion-button>
        </ion-card-content>
      </ion-card>

      <ion-card>
        <ion-card-header><ion-card-title>Users</ion-card-title></ion-card-header>
        <ion-card-content>
          <ion-list>
            @for (u of users(); track u.id) {
              <ion-item>
                <ion-label>{{ u.username }}</ion-label>
                <ion-note slot="end">{{ u.role }}</ion-note>
              </ion-item>
            } @empty { <ion-item><ion-label>No users</ion-label></ion-item> }
          </ion-list>
          <ion-item>
            <ion-input label="Username" labelPlacement="stacked"
                       [(ngModel)]="newUser.username"></ion-input>
          </ion-item>
          <ion-item>
            <ion-input label="Password" labelPlacement="stacked" type="password"
                       [(ngModel)]="newUser.password"></ion-input>
          </ion-item>
          <ion-item>
            <ion-select label="Role" [(ngModel)]="newUser.role">
              <ion-select-option value="adult">adult</ion-select-option>
              <ion-select-option value="owner">owner</ion-select-option>
            </ion-select>
          </ion-item>
          <ion-item>
            <ion-select label="Profile" [(ngModel)]="newUser.profileId">
              @for (p of profiles(); track p.id) {
                <ion-select-option [value]="p.id">{{ p.name }}</ion-select-option>
              }
            </ion-select>
          </ion-item>
          @if (error()) { <ion-note color="danger">{{ error() }}</ion-note> }
          <ion-button expand="block" class="ion-margin-top"
                      (click)="addUser()">Add user</ion-button>
        </ion-card-content>
      </ion-card>
    </ion-content>
  `,
})
export class AdminPage implements OnInit {
  private readonly admin = inject(AdminService);

  readonly users = signal<AdminUser[]>([]);
  readonly profiles = signal<Profile[]>([]);
  readonly error = signal('');

  newProfileName = '';
  newProfileDependent = false;
  newUser = { username: '', password: '', role: 'adult', profileId: null as number | null };

  ngOnInit(): void {
    this.refresh();
  }

  addProfile(): void {
    if (!this.newProfileName.trim()) {
      return;
    }
    this.admin.createProfile(this.newProfileName.trim(), this.newProfileDependent)
      .subscribe(() => {
        this.newProfileName = '';
        this.newProfileDependent = false;
        this.refresh();
      });
  }

  addUser(): void {
    this.error.set('');
    if (!this.newUser.username || this.newUser.password.length < 8) {
      this.error.set('Username and a password of at least 8 characters are required');
      return;
    }
    this.admin.createUser(this.newUser.username, this.newUser.password,
      this.newUser.role, this.newUser.profileId).subscribe({
        next: () => {
          this.newUser = { username: '', password: '', role: 'adult', profileId: null };
          this.refresh();
        },
        error: () => this.error.set('Could not create the user'),
      });
  }

  private refresh(): void {
    this.admin.listProfiles().subscribe((p) => this.profiles.set(p));
    this.admin.listUsers().subscribe((u) => this.users.set(u));
  }
}
