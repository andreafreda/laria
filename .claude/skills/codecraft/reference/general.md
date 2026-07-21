# codecraft examples: language-agnostic

Use this file when you work in a language you do not know well, or one without a
dedicated example file here. The shape of the advice is the same everywhere; only
the syntax changes. Translate the pseudocode into the target language's idioms.

These examples back the principles in `SKILL.md`. The principles, tie-breaks,
Beck's four rules and the smell list all live there and still apply in full,
whatever the language; this file only adds worked examples. Read the principle in
`SKILL.md` first, then the example here.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```
# before: the name and the literal hide the intent
function calc(n, b):
    return n + b * 0.22

# after: the name states the job, the constant names the value
TAX_RATE = 0.22
function gross_with_tax(net, taxable_base):
    return net + taxable_base * TAX_RATE
```

### Linear flow with guard clauses (principle 4)

```
# before: the happy path is buried under nested conditions
function withdraw(account, amount):
    if account exists:
        if account is active:
            if amount <= account.balance:
                account.balance -= amount
                return true
    return false

# after: reject the edge cases first, then the happy path reads straight
function withdraw(account, amount):
    if account is null or not account.active:
        return false
    if amount > account.balance:
        return false
    account.balance -= amount
    return true
```

### Make the contract visible, document it (principle 8)

```
# before: opaque names and types; the caller must read the body
function find(u, l):
    ...

# after: the signature plus one line of intent tells the caller how to use it
# recent_orders: a user's most recent orders, newest first; empty if none.
function recent_orders(user_id: String, limit: Int) -> List<Order>:
    ...
```

### Handle errors honestly (principle 9)

```
# before: a blanket catch hides every bug as "not found"
try:
    return load(id)
catch anything:
    return null

# after: catch the case you expect, let the rest surface
try:
    return load(id)
catch FileNotFound:
    return null
# any other failure propagates with its real cause
```

### Keep side effects at the edges (principle 10)

```
# before: pure decision and IO are tangled, so neither is easy to test
function apply_discount(order_id):
    order = db.load(order_id)          # IO
    if order.total > 100:              # decision
        order.total = order.total * 0.9
    db.save(order)                     # IO

# after: a pure core decides, a thin shell does the IO
function discounted_total(total):      # pure, trivial to test
    if total > 100:
        return total * 0.9
    return total

function apply_discount(order_id):     # thin IO shell
    order = db.load(order_id)
    order.total = discounted_total(order.total)
    db.save(order)
```

### Clarity beats DRY (tie-break rule)

```
# before: a "clever" helper the reader must chase to understand either caller
function apply(obj, key, fn):
    obj[key] = fn(obj[key])
apply(order, "total", multiply_by_1_22)
apply(order, "ref", to_upper)

# after: two honest lines, each readable on its own, no helper to chase
order.total = order.total * 1.22
order.ref = to_upper(order.ref)
```

### Explicit beats magic (tie-break rule)

```
# before: a decorator/aspect hides the retry policy from the call site
@retry(times = 3)
function fetch(url):
    ...

# after: the loop shows exactly what happens on failure
function fetch_with_retries(url):
    for attempt in 0..2:
        try:
            return fetch(url)
        catch TransientError:
            if attempt == 2:
                reraise
```

### Dependency Inversion (SOLID, apply with judgement)

```
# before: the order service is welded to one email vendor
class OrderService:
    function init():
        self.mailer = SendGridClient()      # concrete vendor
    function confirm(order):
        self.mailer.send(order.email, "Confirmed")

# after: it depends on a Notifier abstraction; the vendor is injected
interface Notifier:
    function notify(recipient, message)

class OrderService:
    function init(notifier: Notifier):       # any Notifier works
        self.notifier = notifier
    function confirm(order):
        self.notifier.notify(order.email, "Confirmed")
```

## Language-specific notes

These are the other SOLID shapes the notes in `SKILL.md` point at. Reach for them
when a real second case or seam exists, never for a single concrete case (YAGNI).

### Single Responsibility (SOLID)

One reason to change. Split a class that both computes a report and emails it into
a report builder and a sender; a change to the email transport must not risk the
report maths.

### Open/Closed (SOLID)

```
# before: every new shape edits the same function
function area(shape):
    if shape.kind == "circle": return 3.14159 * shape.r * shape.r
    if shape.kind == "square": return shape.side * shape.side
    # adding a triangle means editing this function again

# after: each shape implements an interface; new shapes add a file
interface Shape:
    function area()

class Circle implements Shape:
    function area(): return 3.14159 * self.r * self.r

class Square implements Shape:
    function area(): return self.side * self.side
```
