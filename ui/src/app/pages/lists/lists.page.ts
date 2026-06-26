import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
  IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonItem, IonInput,
  IonButton, IonNote, IonSegment, IonSegmentButton, IonLabel, IonCheckbox,
  IonSelect, IonSelectOption,
} from '@ionic/angular/standalone';
import { List, ListItem, ListKind, ListsService } from '../../core/lists.service';

const KINDS: ListKind[] = ['todo', 'checklist', 'shopping', 'packing'];

/** The household's generic lists. Pick a kind to filter, open a list to see and
 *  edit its items. An item can carry an optional due date or time. */
@Component({
  selector: 'app-lists',
  standalone: true,
  imports: [
    FormsModule, IonContent, IonHeader, IonToolbar, IonTitle, IonButtons, IonMenuButton,
    IonCard, IonCardHeader, IonCardTitle, IonCardContent, IonItem, IonInput,
    IonButton, IonNote, IonSegment, IonSegmentButton, IonLabel, IonCheckbox,
    IonSelect, IonSelectOption,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-menu-button></ion-menu-button></ion-buttons>
        <ion-title>Lists</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-segment [(ngModel)]="filter">
          <ion-segment-button value="all"><ion-label>All</ion-label></ion-segment-button>
          @for (k of kinds; track k) {
            <ion-segment-button [value]="k"><ion-label>{{ k }}</ion-label></ion-segment-button>
          }
        </ion-segment>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <div class="laria-content-wrap">

        @for (l of visibleLists(); track l.id) {
          <ion-card [class.open]="l.id === openId()">
            <ion-card-content>
              <div class="head" (click)="toggleOpen(l)">
                <div>
                  <span class="name">{{ l.name }}</span>
                  <span class="kind">{{ l.kind }}</span>
                </div>
                <span class="badge">{{ l.open_items }} open</span>
              </div>

              @if (l.id === openId()) {
                @for (it of items(); track it.id) {
                  <div class="row">
                    <ion-checkbox [checked]="it.checked" (ionChange)="toggle(it)"
                                  labelPlacement="end">
                      <span [class.done]="it.checked">{{ it.text }}</span>
                      @if (it.qty) { <span class="qty">{{ it.qty }}</span> }
                    </ion-checkbox>
                    <div class="row-end">
                      @if (it.due_at) { <span class="due">{{ it.due_at }}</span> }
                      <ion-button fill="clear" color="medium" size="small"
                                  (click)="removeItem(it)">✕</ion-button>
                    </div>
                  </div>
                } @empty {
                  <p class="muted">No items yet.</p>
                }

                <ion-item lines="none">
                  <ion-input placeholder="New item" [(ngModel)]="itemText"></ion-input>
                  <ion-input placeholder="due (opt.)" type="datetime-local"
                             [(ngModel)]="itemDue"></ion-input>
                  <ion-button slot="end" fill="clear"
                              (click)="addItem(l)">Add</ion-button>
                </ion-item>
                <ion-button fill="clear" color="danger" size="small"
                            (click)="removeList(l)">Delete list</ion-button>
              }
            </ion-card-content>
          </ion-card>
        } @empty {
          <p class="muted">No lists yet.</p>
        }

        <ion-card>
          <ion-card-header><ion-card-title>New list</ion-card-title></ion-card-header>
          <ion-card-content>
            <ion-item>
              <ion-input label="Name" labelPlacement="stacked"
                         [(ngModel)]="newName" placeholder="Groceries"></ion-input>
            </ion-item>
            <ion-item>
              <ion-select label="Kind" labelPlacement="stacked" [(ngModel)]="newKind">
                @for (k of kinds; track k) {
                  <ion-select-option [value]="k">{{ k }}</ion-select-option>
                }
              </ion-select>
            </ion-item>
            @if (error()) { <ion-note color="danger">{{ error() }}</ion-note> }
            <ion-button expand="block" class="ion-margin-top"
                        [disabled]="busy()" (click)="createList()">Add list</ion-button>
          </ion-card-content>
        </ion-card>

      </div>
    </ion-content>
  `,
  styles: [`
    .head { display: flex; align-items: center; justify-content: space-between; cursor: pointer; }
    .name { font-weight: 600; }
    .kind { font-size: 12px; color: var(--laria-text-muted); margin-left: 8px;
            text-transform: uppercase; letter-spacing: 0.08em; }
    .badge { font-size: 13px; color: var(--laria-text-muted); }
    .row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; }
    .row-end { display: flex; align-items: center; gap: 4px; }
    .qty { color: var(--laria-text-muted); margin-left: 8px; font-size: 13px; }
    .due { font-size: 12px; color: var(--laria-text-muted); }
    .done { text-decoration: line-through; color: var(--laria-text-muted); }
    .muted { color: var(--laria-text-muted); }
  `],
})
export class ListsPage implements OnInit {
  private readonly service = inject(ListsService);

  readonly kinds = KINDS;
  readonly lists = signal<List[]>([]);
  readonly items = signal<ListItem[]>([]);
  readonly openId = signal<number | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');

  filter: 'all' | ListKind = 'all';
  newName = '';
  newKind: ListKind = 'todo';
  itemText = '';
  itemDue = '';

  readonly visibleLists = computed(() =>
    this.filter === 'all'
      ? this.lists()
      : this.lists().filter((l) => l.kind === this.filter),
  );

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.service.lists().subscribe((l) => this.lists.set(l));
  }

  toggleOpen(list: List): void {
    if (this.openId() === list.id) {
      this.openId.set(null);
      return;
    }
    this.openId.set(list.id);
    this.loadItems(list.id);
  }

  private loadItems(listId: number): void {
    this.service.items(listId).subscribe((items) => this.items.set(items));
  }

  toggle(item: ListItem): void {
    this.service.toggleItem(item.id).subscribe(() => {
      this.loadItems(this.openId()!);
      this.reload();
    });
  }

  addItem(list: List): void {
    if (!this.itemText.trim()) {
      return;
    }
    const dueAt = this.itemDue ? this.itemDue.replace('T', ' ') : null;
    this.service.addItem(list.id, this.itemText.trim(), null, dueAt).subscribe(() => {
      this.itemText = '';
      this.itemDue = '';
      this.loadItems(list.id);
      this.reload();
    });
  }

  removeItem(item: ListItem): void {
    this.service.deleteItem(item.id).subscribe(() => {
      this.loadItems(this.openId()!);
      this.reload();
    });
  }

  createList(): void {
    if (!this.newName.trim()) {
      this.error.set('Add a name.');
      return;
    }
    this.error.set('');
    this.busy.set(true);
    this.service.createList(this.newName.trim(), this.newKind).subscribe({
      next: () => {
        this.newName = '';
        this.busy.set(false);
        this.reload();
      },
      error: () => {
        this.error.set('Could not create the list.');
        this.busy.set(false);
      },
    });
  }

  removeList(list: List): void {
    this.service.deleteList(list.id).subscribe(() => {
      if (this.openId() === list.id) {
        this.openId.set(null);
      }
      this.reload();
    });
  }
}
