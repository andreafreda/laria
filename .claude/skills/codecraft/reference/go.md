# codecraft examples: Go

Apply Go's own idioms: return errors, do not panic for expected failure; wrap
errors with context; accept interfaces, return concrete types; keep zero values
useful. Examples back the principles in `SKILL.md`, which holds the rules.

The "Core" section is the same set of examples in every language file, in the
same order, so you can calibrate across languages.

## Core

### Name things fully, name the magic number (principle 2)

```go
// before: the name and the literal hide the intent
func calc(n, b float64) float64 {
    return n + b*0.22
}

// after: the name states the job, the constant names the value
const TaxRate = 0.22

func GrossWithTax(net, taxableBase float64) float64 {
    return net + taxableBase*TaxRate
}
```

### Linear flow with guard clauses (principle 4)

```go
// before: the happy path is buried under nested conditions
func Withdraw(a *Account, amount int) bool {
    if a != nil {
        if a.Active {
            if amount <= a.Balance {
                a.Balance -= amount
                return true
            }
        }
    }
    return false
}

// after: reject the edge cases first, then the happy path reads straight
func Withdraw(a *Account, amount int) bool {
    if a == nil || !a.Active {
        return false
    }
    if amount > a.Balance {
        return false
    }
    a.Balance -= amount
    return true
}
```

### Make the contract visible, document it (principle 8)

```go
// before: opaque parameters and return; the caller must read the body
func Handle(req interface{}) interface{} { /* ... */ }

// after: typed signature plus a doc comment in Go's convention
// RecentOrders returns a user's most recent orders, newest first.
// It returns an empty slice if the user has none.
func RecentOrders(userID string, limit int) []Order { /* ... */ }
```

### Handle errors honestly: wrap with context (principle 9)

```go
// before: the error is returned bare, the caller cannot tell what failed
func loadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    return parse(data)
}

// after: wrap with context so the cause is actionable up the stack
func loadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("read config %q: %w", path, err)
    }
    return parse(data)
}
```

### Keep side effects at the edges (principle 10)

```go
// before: the decision and the IO are tangled
func ApplyDiscount(db *DB, id string) error {
    order, err := db.Load(id)
    if err != nil {
        return err
    }
    if order.Total > 100 {
        order.Total = order.Total * 0.9
    }
    return db.Save(order)
}

// after: a pure function decides, the shell does the IO
// discountedTotal is pure, so it is trivial to test.
func discountedTotal(total float64) float64 {
    if total > 100 {
        return total * 0.9
    }
    return total
}

func ApplyDiscount(db *DB, id string) error {
    order, err := db.Load(id)
    if err != nil {
        return err
    }
    order.Total = discountedTotal(order.Total)
    return db.Save(order)
}
```

### Clarity beats DRY (tie-break rule)

```go
// before: a reflection helper the reader must chase, and it loses type safety
func apply(obj any, field string, fn func(any) any) {
    v := reflect.ValueOf(obj).Elem().FieldByName(field)
    v.Set(reflect.ValueOf(fn(v.Interface())))
}
apply(order, "Total", func(v any) any { return v.(float64) * 1.22 })

// after: two honest lines, type-checked, no reflection to chase
order.Total = order.Total * 1.22
order.Ref = strings.ToUpper(order.Ref)
```

### Explicit beats magic (tie-break rule)

```go
// before: panic/recover used as control flow hides the real path
func Withdraw(a *Account, amount int) (ok bool) {
    defer func() {
        if recover() != nil {
            ok = false
        }
    }()
    if amount > a.Balance {
        panic("insufficient")
    }
    a.Balance -= amount
    return true
}

// after: an explicit error return; the caller sees every outcome, and the nil
// guard from the guard-clause example is kept rather than masked by recover
func Withdraw(a *Account, amount int) error {
    if a == nil {
        return errors.New("withdraw from nil account")
    }
    if amount > a.Balance {
        return fmt.Errorf("insufficient funds: have %d, need %d", a.Balance, amount)
    }
    a.Balance -= amount
    return nil
}
```

### Dependency Inversion: accept an interface (SOLID, apply with judgement)

```go
// the small abstraction the high-level code depends on
type Notifier interface {
    Notify(recipient, message string) error
}

// before: OrderService is welded to one concrete notifier
type OrderService struct {
    mailer *SendGridClient
}

// after: depend on Notifier; tests pass a fake, prod passes the vendor
type OrderService struct {
    notifier Notifier
}

func (s *OrderService) Confirm(o Order) error {
    return s.notifier.Notify(o.Email, "Confirmed")
}
```
