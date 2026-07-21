# codecraft examples: C#

Apply C#'s own idioms: typed signatures, XML doc comments on the public surface,
specific exception types over catch-all, interfaces plus dependency injection
over new-ing concretes. Examples back the principles in `SKILL.md`, which holds
the rules.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```csharp
// before: the name and the literal hide the intent
double Calc(double n, double b) => n + b * 0.22;

// after: the name states the job, the constant names the value
const double TaxRate = 0.22;

double GrossWithTax(double net, double taxableBase) => net + taxableBase * TaxRate;
```

### Linear flow with guard clauses (principle 4)

```csharp
// before: the happy path is buried under nested conditions
public bool Withdraw(Account account, int amount) {
    if (account != null) {
        if (account.Active) {
            if (amount <= account.Balance) {
                account.Balance -= amount;
                return true;
            }
        }
    }
    return false;
}

// after: reject the edge cases first, then the happy path reads straight
public bool Withdraw(Account account, int amount) {
    if (account is null || !account.Active) return false;
    if (amount > account.Balance) return false;
    account.Balance -= amount;
    return true;
}
```

### Make the contract visible, document it (principle 8)

```csharp
// before: object in, object out; the caller learns nothing
public object Handle(object req) { /* ... */ }

// after: typed signature plus an XML doc comment of intent
/// <summary>A user's most recent orders, newest first. Empty if they have none.</summary>
public IReadOnlyList<Order> RecentOrders(string userId, int limit) { /* ... */ }
```

### Handle errors honestly (principle 9)

```csharp
// before: a blanket catch hides every bug as "not found"
try { return Load(id); }
catch { return null; }

// after: catch the case you expect, let the rest surface
try { return Load(id); }
catch (FileNotFoundException) { return null; }
```

### Keep side effects at the edges (principle 10)

```csharp
// before: the decision and the IO are tangled, neither is easy to test
public async Task ApplyDiscountAsync(string orderId) {
    var order = await _db.LoadAsync(orderId);
    if (order.Total > 100) order.Total *= 0.9m;
    await _db.SaveAsync(order);
}

// after: a pure method decides, a thin shell does the IO
/// <summary>10% off orders above 100. Pure, so it is trivial to unit test.</summary>
static decimal DiscountedTotal(decimal total) => total > 100 ? total * 0.9m : total;

public async Task ApplyDiscountAsync(string orderId) {
    var order = await _db.LoadAsync(orderId);
    order.Total = DiscountedTotal(order.Total);
    await _db.SaveAsync(order);
}
```

### Clarity beats DRY (tie-break rule)

```csharp
// before: a reflection helper the reader must chase, and it loses type safety
void Apply(object obj, string prop, Func<object, object> fn) {
    var p = obj.GetType().GetProperty(prop);
    p.SetValue(obj, fn(p.GetValue(obj)));
}
Apply(order, "Total", v => (decimal)v * 1.22m);

// after: two honest lines, type-checked, no reflection to chase
order.Total = order.Total * 1.22m;
order.Ref = order.Ref.ToUpper();
```

The reflective "before" also fails at runtime on `init` or read-only properties,
not just at the type level, so it is buggier as well as harder to read.

### Explicit beats magic (tie-break rule)

```csharp
// before: an AOP [Retry] attribute hides the retry policy from the call site
[Retry(3)]
public Response Fetch(string url) { /* ... */ }

// after: the loop shows exactly what happens on failure (3 attempts, no more)
public Response FetchWithRetries(string url) {
    for (int attempt = 0; attempt < 3; attempt++) {
        try {
            return Fetch(url);
        } catch (TransientException) {
            if (attempt == 2) throw;
        }
    }
    throw new InvalidOperationException("unreachable");
}
```

### Dependency Inversion: inject the abstraction (SOLID, apply with judgement)

```csharp
// the abstraction the high-level code depends on
public interface INotifier {
    void Notify(string recipient, string message);
}

// before: OrderService is welded to one concrete vendor
public class OrderService {
    private readonly SendGridClient _mailer = new();
}

// after: depend on INotifier; the vendor is injected by the container
public class OrderService {
    private readonly INotifier _notifier;
    public OrderService(INotifier notifier) => _notifier = notifier;
    public void Confirm(Order o) => _notifier.Notify(o.Email, "Confirmed");
}
```

## Language-specific notes

### Open/Closed with an interface (SOLID, apply with judgement)

```csharp
// before: every new shape edits the same switch
public double Area(Shape s) => s.Kind switch {
    "circle" => Math.PI * s.R * s.R,
    "square" => s.Side * s.Side,
    _ => throw new ArgumentException(nameof(s)),
};

// after: each shape implements IShape; new shapes add a file, no edit here
public interface IShape {
    double Area();
}

public class Circle : IShape {
    public double R { get; init; }
    public double Area() => Math.PI * R * R;
}

public class Square : IShape {
    public double Side { get; init; }
    public double Area() => Side * Side;
}
```
