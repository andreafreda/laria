# codecraft examples: Python

Apply Python's own idioms: type hints on public functions, docstrings on the
public surface, exceptions for error flow, comprehensions only when they stay
obvious. Examples back the principles in `SKILL.md`, which holds the rules.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```python
# before: the name and the literal hide the intent
def calc(n, b):
    return n + b * 0.22

# after: the name states the job, the constant names the value
TAX_RATE = 0.22

def gross_with_tax(net: float, taxable_base: float) -> float:
    return net + taxable_base * TAX_RATE
```

### Linear flow with guard clauses (principle 4)

```python
# before: the happy path is buried under nested conditions
def withdraw(account, amount):
    if account is not None:
        if account.active:
            if amount <= account.balance:
                account.balance -= amount
                return True
    return False

# after: reject the edge cases first, then the happy path reads straight
def withdraw(account, amount):
    if account is None or not account.active:
        return False
    if amount > account.balance:
        return False
    account.balance -= amount
    return True
```

### Make the contract visible, document it (principle 8)

```python
# before: no types, no intent; the caller must read the body
def find(u, l):
    ...

# after: hints state the contract, the docstring states the intent
def recent_orders(user_id: str, limit: int) -> list[Order]:
    """A user's most recent orders, newest first. Returns [] if they have none."""
    ...
```

### Handle errors honestly (principle 9)

```python
# before: a bare except hides every bug as "not found"
try:
    return load(record_id)
except Exception:
    return None

# after: catch the case you expect, let the rest surface
try:
    return load(record_id)
except FileNotFoundError:
    return None
```

### Keep side effects at the edges (principle 10)

```python
# before: pure decision and IO are tangled, neither is easy to test
def apply_discount(order_id: str) -> None:
    order = db.load(order_id)
    if order.total > 100:
        order.total *= 0.9
    db.save(order)

# after: a pure core decides, a thin shell does the IO
def discounted_total(total: float) -> float:
    """10% off orders above 100. Pure, so it is trivial to unit test."""
    return total * 0.9 if total > 100 else total

def apply_discount(order_id: str) -> None:
    order = db.load(order_id)
    order.total = discounted_total(order.total)
    db.save(order)
```

### Clarity beats DRY (tie-break rule)

```python
# before: a "clever" helper the reader must chase to understand either caller
def _apply(obj, key, fn):
    setattr(obj, key, fn(getattr(obj, key)))

_apply(order, "total", lambda v: v * 1.22)
_apply(order, "ref", str.upper)

# after: two honest lines, each readable on its own, no helper to chase
order.total = order.total * 1.22
order.ref = order.ref.upper()
```

### Explicit beats magic (tie-break rule)

```python
# before: a decorator hides the retry policy from the call site
@retry(times=3)
def fetch(url): ...

# after: the loop shows exactly what happens on failure
def fetch_with_retries(url):
    for attempt in range(3):
        try:
            return fetch(url)
        except TransientError:
            if attempt == 2:
                raise
```

### Dependency Inversion (SOLID, apply with judgement)

```python
from typing import Protocol

# the abstraction the high-level code depends on
class Notifier(Protocol):
    def notify(self, recipient: str, message: str) -> None: ...

# before: OrderService is welded to one concrete vendor
class OrderService:
    def __init__(self) -> None:
        self.mailer = SendGridClient()

# after: it depends on the Notifier abstraction; the vendor is injected
class OrderService:
    def __init__(self, notifier: Notifier) -> None:
        self.notifier = notifier

    def confirm(self, order: Order) -> None:
        self.notifier.notify(order.email, "Confirmed")
```

## Language-specific notes

Not every decorator is "magic". `@functools.lru_cache`, `@property` and
`@dataclass` are standard, well understood Python, prefer them. Unfold only a
decorator that hides control flow a reader needs to see (retries, transactions,
auth checks), as in the "explicit beats magic" example above.
