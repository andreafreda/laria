# codecraft examples: TypeScript

Apply TypeScript's own idioms: typed signatures over `any`, JSDoc on the public
surface, discriminated unions over boolean flags, narrow early. Examples back the
principles in `SKILL.md`, which holds the rules. For React components, see
`reference/react.md`; for untyped frontend JS, see `reference/javascript.md`.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```ts
// before: the name and the literal hide the intent
function calc(n: number, b: number): number {
  return n + b * 0.22;
}

// after: the name states the job, the constant names the value
const TAX_RATE = 0.22;

function grossWithTax(net: number, taxableBase: number): number {
  return net + taxableBase * TAX_RATE;
}
```

### Linear flow with guard clauses (principle 4)

```ts
// before: the happy path is buried under nested conditions
function withdraw(account: Account | null, amount: number): boolean {
  if (account) {
    if (account.active) {
      if (amount <= account.balance) {
        account.balance -= amount;
        return true;
      }
    }
  }
  return false;
}

// after: reject the edge cases first, then the happy path reads straight
function withdraw(account: Account | null, amount: number): boolean {
  if (!account || !account.active) return false;
  if (amount > account.balance) return false;
  account.balance -= amount;
  return true;
}
```

### Make the contract visible, document it (principle 8)

```ts
// before: any in, any out; the caller learns nothing from the signature
function find(u: any, l: any) { /* ... */ }

// after: types state the contract, the comment states the intent
/** A user's most recent orders, newest first. Returns [] if they have none. */
function recentOrders(userId: string, limit: number): Order[] { /* ... */ }
```

### Handle errors honestly (principle 9)

```ts
// before: a blanket catch swallows every error as null
try {
  return load(id);
} catch {
  return null;
}

// after: narrow to the case you expect, rethrow the rest
try {
  return load(id);
} catch (err) {
  if (err instanceof NotFoundError) return null;
  throw err;
}
```

### Keep side effects at the edges (principle 10)

```ts
// before: pure decision and IO are tangled, neither is easy to test
async function applyDiscount(orderId: string): Promise<void> {
  const order = await db.load(orderId);
  if (order.total > 100) order.total *= 0.9;
  await db.save(order);
}

// after: a pure core decides, a thin shell does the IO
/** 10% off orders above 100. Pure, so it is trivial to unit test. */
function discountedTotal(total: number): number {
  return total > 100 ? total * 0.9 : total;
}

async function applyDiscount(orderId: string): Promise<void> {
  const order = await db.load(orderId);
  order.total = discountedTotal(order.total);
  await db.save(order);
}
```

### Clarity beats DRY (tie-break rule)

```ts
// before: a "clever" helper the reader must chase to understand either caller
function apply<T, K extends keyof T>(obj: T, key: K, fn: (v: T[K]) => T[K]): void {
  obj[key] = fn(obj[key]);
}
apply(order, "total", (v) => v * 1.22);
apply(order, "ref", (v) => v.toUpperCase());

// after: two honest lines, each readable on its own, no helper to chase
order.total = order.total * 1.22;
order.ref = order.ref.toUpperCase();
```

### Explicit beats magic (tie-break rule)

```ts
// before: a method decorator hides the retry policy from the call site
class Api {
  @retry(3)
  fetch(url: string) { /* ... */ }
}

// after: the loop shows exactly what happens on failure
async function fetchWithRetries(url: string): Promise<Response> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await fetch(url);
    } catch (err) {
      if (attempt === 2) throw err;
    }
  }
  throw new Error("unreachable");
}
```

### Dependency Inversion (SOLID, apply with judgement)

```ts
// the abstraction the high-level code depends on
interface Notifier {
  notify(recipient: string, message: string): void;
}

// before: OrderService is welded to one concrete vendor
class OrderService {
  private mailer = new SendGridClient();
}

// after: it depends on Notifier; the vendor is injected
class OrderService {
  constructor(private readonly notifier: Notifier) {}

  confirm(order: Order): void {
    this.notifier.notify(order.email, "Confirmed");
  }
}
```

## Language-specific notes

### Boolean trap: model the concept instead of flags (readability smell)

```ts
// before: createUser(true, false) is unreadable at the call site
function createUser(isAdmin: boolean, sendEmail: boolean): User { /* ... */ }
createUser(true, false);

// after: a typed options object says what each value means
type CreateUserOptions = { role: "admin" | "member"; welcomeEmail: boolean };
function createUser(opts: CreateUserOptions): User { /* ... */ }
createUser({ role: "admin", welcomeEmail: false });
```

### Open/Closed with an interface (SOLID, apply with judgement)

```ts
// before: every new payment method edits the same switch
function charge(method: string, amount: number): void {
  if (method === "card") { /* ... */ }
  else if (method === "paypal") { /* ... */ }
  // a new method means editing this function again
}

// after: each method implements PaymentMethod; new methods add a file
interface PaymentMethod {
  charge(amount: number): void;
}

class Card implements PaymentMethod {
  charge(amount: number): void { /* ... */ }
}

class PayPal implements PaymentMethod {
  charge(amount: number): void { /* ... */ }
}
```
