# codecraft examples: JavaScript (vanilla, frontend)

Plain JavaScript, no build step or framework. Apply JS's own idioms: JSDoc to
state the contract a type system would (there is none at runtime), early returns,
exceptions or rejected promises for error flow, and a clear line between pure
logic and the DOM. Examples back the principles in `SKILL.md`, which holds the
rules. For React, see `reference/react.md`, which builds on this file; for typed
JS, see `reference/typescript.md`.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```js
// before: the name and the literal hide the intent
function calc(n, b) {
  return n + b * 0.22;
}

// after: the name states the job, the constant names the value
const TAX_RATE = 0.22;

function grossWithTax(net, taxableBase) {
  return net + taxableBase * TAX_RATE;
}
```

### Linear flow with guard clauses (principle 4)

```js
// before: the happy path is buried under nested conditions
function withdraw(account, amount) {
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
function withdraw(account, amount) {
  if (!account || !account.active) return false;
  if (amount > account.balance) return false;
  account.balance -= amount;
  return true;
}
```

### Make the contract visible with JSDoc (principle 8)

```js
// before: the caller cannot tell what goes in or comes out
function recentOrders(u, l) {
  /* ... */
}

// after: JSDoc states the contract a type system would, plus the intent
/**
 * A user's most recent orders, newest first. Returns [] if they have none.
 * @param {string} userId
 * @param {number} limit
 * @returns {Order[]}
 */
function recentOrders(userId, limit) {
  /* ... */
}
```

### Handle errors honestly (principle 9)

```js
// before: a blanket catch swallows every failure as null
async function loadUser(id) {
  try {
    return await api.get(`/users/${id}`);
  } catch {
    return null;
  }
}

// after: handle the case you expect, let the rest surface
async function loadUser(id) {
  try {
    return await api.get(`/users/${id}`);
  } catch (err) {
    // api.get rejects with an HttpError carrying a numeric `status`
    if (err instanceof HttpError && err.status === 404) return null;
    throw err;
  }
}
```

### Keep side effects at the edges: pure logic vs the DOM (principle 10)

```js
// before: formatting and DOM writes are tangled, the logic cannot be tested
function renderTotal(order) {
  const el = document.querySelector("#total");
  const value = order.total > 100 ? order.total * 0.9 : order.total;
  el.textContent = "$" + value.toFixed(2);
}

// after: a pure core computes the string, a thin shell touches the DOM
/** @param {Order} order @returns {string} the price label to display */
function totalLabel(order) {
  const value = order.total > 100 ? order.total * 0.9 : order.total;
  return "$" + value.toFixed(2);
}

function renderTotal(order) {
  document.querySelector("#total").textContent = totalLabel(order);
}
```

### Clarity beats DRY (tie-break rule)

```js
// before: a "clever" helper the reader must chase to understand either caller
function apply(obj, key, fn) {
  obj[key] = fn(obj[key]);
}
apply(order, "total", (v) => v * 1.22);
apply(order, "ref", (v) => v.toUpperCase());

// after: two honest lines, each readable on its own, no helper to chase
order.total = order.total * 1.22;
order.ref = order.ref.toUpperCase();
```

### Explicit beats magic (tie-break rule)

```js
// before: a Proxy magically re-renders on every property write; the trigger is invisible
const state = new Proxy({ count: 0 }, {
  set(obj, key, value) {
    obj[key] = value;
    rerender(); // hidden side effect on every assignment
    return true;
  },
});
state.count++;

// after: an explicit update function shows exactly when a render happens
const state = { count: 0 };

function setCount(next) {
  state.count = next;
  rerender();
}
setCount(state.count + 1);
```

### Dependency Inversion: inject the dependency (SOLID, apply with judgement)

```js
// before: welded to the browser's localStorage; impossible to test without a DOM
class Cart {
  save(items) {
    localStorage.setItem("cart", JSON.stringify(items));
  }
}

// after: depend on a small storage abstraction; inject localStorage in the browser,
// a fake in tests. Any object with getItem/setItem works.
class Cart {
  constructor(storage) {
    this.storage = storage;
  }
  save(items) {
    this.storage.setItem("cart", JSON.stringify(items));
  }
}
// browser: new Cart(localStorage); test: new Cart(fakeStorage)
```

## Language-specific notes

### Reach for types when the file grows

JSDoc carries the contract at the boundary, but on a module that keeps growing,
moving to TypeScript (see `reference/typescript.md`) makes the contract checked
rather than commented. Treat plain JS plus JSDoc as the lightweight default, not
a permanent ceiling.

### Boolean trap at the call site (readability smell)

```js
// before: createUser(true, false) is unreadable at the call site
function createUser(isAdmin, sendEmail) { /* ... */ }
createUser(true, false);

// after: an options object says what each value means
function createUser({ role, welcomeEmail }) { /* ... */ }
createUser({ role: "admin", welcomeEmail: false });
```
