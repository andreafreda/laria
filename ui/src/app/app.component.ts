import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import {
  IonApp, IonRouterOutlet, IonSplitPane, IonMenu, IonContent, IonList,
  IonListHeader, IonItem, IonLabel, IonIcon, IonMenuToggle,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  chatbubbleOutline, walletOutline, restaurantOutline, newspaperOutline,
  peopleOutline, warningOutline, logOutOutline,
} from 'ionicons/icons';
import { AuthService } from './core/auth.service';

/** App shell: a side menu for navigation around a routed outlet. The menu shows
 *  the Family (admin) link only to the owner, and Sign out clears the session. */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterLink, IonApp, IonRouterOutlet, IonSplitPane, IonMenu, IonContent,
    IonList, IonListHeader, IonItem, IonLabel, IonIcon, IonMenuToggle,
  ],
  template: `
    <ion-app>
      <ion-split-pane contentId="main">
        @if (auth.isAuthenticated()) {
          <ion-menu contentId="main">
            <ion-content>
              <ion-list>
                <ion-list-header>LARIA</ion-list-header>
                <ion-menu-toggle auto-hide="false">
                  <ion-item routerLink="/chat" detail="false">
                    <ion-icon slot="start" name="chatbubble-outline"></ion-icon>
                    <ion-label>Chat</ion-label>
                  </ion-item>
                  <ion-item routerLink="/dashboard" detail="false">
                    <ion-icon slot="start" name="wallet-outline"></ion-icon>
                    <ion-label>Finance</ion-label>
                  </ion-item>
                  <ion-item routerLink="/food" detail="false">
                    <ion-icon slot="start" name="restaurant-outline"></ion-icon>
                    <ion-label>Food</ion-label>
                  </ion-item>
                  <ion-item routerLink="/news" detail="false">
                    <ion-icon slot="start" name="newspaper-outline"></ion-icon>
                    <ion-label>News</ion-label>
                  </ion-item>
                  @if (auth.isOwner()) {
                    <ion-item routerLink="/admin" detail="false">
                      <ion-icon slot="start" name="people-outline"></ion-icon>
                      <ion-label>Family</ion-label>
                    </ion-item>
                    <ion-item routerLink="/logs" detail="false">
                      <ion-icon slot="start" name="warning-outline"></ion-icon>
                      <ion-label>System log</ion-label>
                    </ion-item>
                  }
                  <ion-item button (click)="logout()" detail="false">
                    <ion-icon slot="start" name="log-out-outline"></ion-icon>
                    <ion-label>Sign out</ion-label>
                  </ion-item>
                </ion-menu-toggle>
              </ion-list>
            </ion-content>
          </ion-menu>
        }
        <ion-router-outlet id="main"></ion-router-outlet>
      </ion-split-pane>
    </ion-app>
  `,
})
export class AppComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  constructor() {
    addIcons({
      chatbubbleOutline, walletOutline, restaurantOutline, newspaperOutline,
      peopleOutline, warningOutline, logOutOutline,
    });
  }

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
