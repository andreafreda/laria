# codecraft examples: Java

Apply Java's own idioms: typed signatures, Javadoc on the public surface, specific
exceptions over catch-all, constructor injection over new-ing dependencies inside
a class. Examples back the principles in `SKILL.md`, which holds the rules.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```java
// before: the name and the literal hide the intent
double calc(double n, double b) {
    return n + b * 0.22;
}

// after: the name states the job, the constant names the value
static final double TAX_RATE = 0.22;

double grossWithTax(double net, double taxableBase) {
    return net + taxableBase * TAX_RATE;
}
```

### Linear flow with guard clauses (principle 4)

```java
// before: the happy path is buried under nested conditions
boolean withdraw(Account account, int amount) {
    if (account != null) {
        if (account.isActive()) {
            if (amount <= account.getBalance()) {
                account.debit(amount);
                return true;
            }
        }
    }
    return false;
}

// after: reject the edge cases first, then the happy path reads straight
boolean withdraw(Account account, int amount) {
    if (account == null || !account.isActive()) return false;
    if (amount > account.getBalance()) return false;
    account.debit(amount);
    return true;
}
```

### Make the contract visible, document it (principle 8)

```java
// before: Object in, Object out; the signature tells the caller nothing
public Object handle(Object req) { /* ... */ }

// after: the signature alone tells the caller how to use it
/** Validate and book a reservation; throws SlotTakenException if the slot is gone. */
public Booking book(ReservationRequest request) { /* ... */ }
```

### Handle errors honestly (principle 9)

```java
// before: catching Exception buries the real cause
try {
    return load(id);
} catch (Exception e) {
    return null;
}

// after: catch the case you expect, let the rest surface
try {
    return load(id);
} catch (FileNotFoundException e) {
    return null;
}
```

### Keep side effects at the edges (principle 10)

```java
// before: the decision and the IO are tangled, neither is easy to test
void applyDiscount(String orderId) {
    Order order = db.load(orderId);
    if (order.getTotal() > 100) {
        order.setTotal(order.getTotal() * 0.9);
    }
    db.save(order);
}

// after: a pure method decides, a thin shell does the IO
/** 10% off orders above 100. Pure, so it is trivial to unit test. */
static double discountedTotal(double total) {
    return total > 100 ? total * 0.9 : total;
}

void applyDiscount(String orderId) {
    Order order = db.load(orderId);
    order.setTotal(discountedTotal(order.getTotal()));
    db.save(order);
}
```

### Clarity beats DRY (tie-break rule)

```java
// before: a reflective helper the reader must chase, and it loses type safety
<T> void apply(Object obj, String field, UnaryOperator<T> fn) throws Exception {
    Field f = obj.getClass().getDeclaredField(field);
    f.setAccessible(true);
    f.set(obj, fn.apply((T) f.get(obj)));
}
apply(order, "total", (Double v) -> v * 1.22);

// after: two honest lines, type-checked, no reflection to chase
order.setTotal(order.getTotal() * 1.22);
order.setRef(order.getRef().toUpperCase());
```

### Explicit beats magic (tie-break rule)

```java
// before: a Spring @Retryable annotation hides the retry policy from the call site
@Retryable(maxAttempts = 3)
public Response fetch(String url) { /* ... */ }

// after: the loop shows exactly what happens on failure
public Response fetchWithRetries(String url) {
    for (int attempt = 0; attempt < 3; attempt++) {
        try {
            return fetch(url);
        } catch (TransientException e) {
            if (attempt == 2) throw e;
        }
    }
    throw new IllegalStateException("unreachable");
}
```

### Dependency Inversion: constructor injection (SOLID, apply with judgement)

```java
// the abstraction the high-level code depends on
interface Notifier {
    void notify(String recipient, String message);
}

// before: OrderService is welded to one concrete vendor
class OrderService {
    private final SendGridClient mailer = new SendGridClient();
}

// after: depend on Notifier; the vendor is injected
class OrderService {
    private final Notifier notifier;
    OrderService(Notifier notifier) { this.notifier = notifier; }
    void confirm(Order o) { notifier.notify(o.email(), "Confirmed"); }
}
```

## Language-specific notes

### Single Responsibility: split the class (SOLID, apply with judgement)

```java
// before: one class computes a report AND emails it; two reasons to change
class ReportService {
    String build(Data d) { /* report maths */ }
    void email(String report, String to) { /* SMTP */ }
}

// after: each class has one reason to change
class ReportBuilder {
    String build(Data d) { /* report maths */ }
}

class ReportMailer {
    void send(String report, String to) { /* SMTP */ }
}
```
