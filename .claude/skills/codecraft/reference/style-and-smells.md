# codecraft examples: style principles and smells

The per-language files cover the Core spine. This file covers the principles that
are about style and judgement rather than a code shape, so one set of examples
serves every language: principles 1, 3, 5, 6, 7 and 11, plus worked examples for
several of the smells listed in `SKILL.md`. The rules live in `SKILL.md`;
these are illustrations. Examples are in a mix of languages; apply your own
language's idioms.

## Obvious over clever (principle 1)

```js
// before: a clever bit trick the reader has to decode
const isEven = (n) => !(n & 1);

// after: the plain check a competent reader grasps instantly
const isEven = (n) => n % 2 === 0;
```

```python
# before: one dense expression doing three things
result = [y for x in data if x.ok for y in x.items if y.price > 0]

# after: the same logic, unfolded so each step is obvious
result = []
for record in data:
    if not record.ok:
        continue
    for item in record.items:
        if item.price > 0:
            result.append(item)
```

## Explain the why, not the what (principle 3)

```python
# before: the comment narrates what the code already says
i += 1  # increment i

# after: the comment justifies a non-obvious decision
# The upstream API caps a page at 100 items, so we request in chunks.
page_size = 100
```

## Consistent sibling shape (principle 5)

```ts
// before: siblings disagree on argument order and return shape
function createUser(name: string, email: string): User { /* ... */ }
function updateUser(id: string, user: User): boolean { /* ... */ }
function deleteUser(user: User): void { /* ... */ }

// after: same id-first order, same User return, so the set is predictable
function createUser(draft: UserDraft): User { /* ... */ }
function updateUser(id: string, draft: UserDraft): User { /* ... */ }
function deleteUser(id: string): User { /* ... */ }
```

## Don't over-abstract (principle 6)

```python
# before: a generic framework for a single concrete case (no duplication exists yet)
class BaseRepository:
    def __init__(self, model, session, cache, serializer): ...
    def query(self, **filters): ...

class UserRepository(BaseRepository): ...  # the only subclass

# after: the plain, concrete version; abstract later if a second case appears
class UserRepository:
    def __init__(self, session):
        self.session = session
    def by_email(self, email: str) -> User | None: ...
```

## Length is fine, density is not (principle 7)

```python
# before: one dense line packs parse, filter, sort and format together
def report(rows):
    return "\n".join(f"{r['name']}: {r['n']}" for r in sorted((r for r in rows if r['n'] > 0), key=lambda r: -r['n']))

# after: a few named steps, each obvious, longer but clearer
def report(rows):
    active = [r for r in rows if r["n"] > 0]
    ranked = sorted(active, key=lambda r: r["n"], reverse=True)
    lines = [f"{r['name']}: {r['n']}" for r in ranked]
    return "\n".join(lines)
```

## Write prose like a human (principle 11)

```
# before: machine-flavoured prose, em dashes as connectors and an arrow glyph
// Loads the user - then validates it - and returns the result -> caller handles errors

# after: ordinary punctuation a person would use
// Loads the user, validates it, and returns the result. The caller handles errors.
```

## Smell: primitive obsession

```python
# before: a bare string stands in for a domain concept, so nothing is validated
def send_invoice(email: str) -> None: ...
send_invoice("not-an-email")  # accepted, fails later

# after: model the concept once; construction is the single validation point
class Email:
    def __init__(self, raw: str):
        if "@" not in raw:
            raise ValueError(f"invalid email: {raw!r}")
        self.value = raw

def send_invoice(email: Email) -> None: ...
```

## Smell: long parameter list / data clump

```ts
// before: a long positional list; the call site is a guessing game
function createEvent(title: string, startY: number, startM: number, startD: number,
                     endY: number, endM: number, endD: number) { /* ... */ }

// after: group the clump into a named concept
type DateRange = { start: Date; end: Date };
function createEvent(title: string, when: DateRange) { /* ... */ }
```

## Smell: feature envy

```python
# before: the method mostly pokes at another object's data; the logic lives in the wrong place
class Invoice:
    def total(self, order):
        return sum(line.price * line.qty for line in order.lines) + order.shipping

# after: the logic moves to the object whose data it uses
class Order:
    def total(self) -> float:
        return sum(line.price * line.qty for line in self.lines) + self.shipping
```

Note: this moves the call site from `invoice.total(order)` to `order.total()`, so
it is a design change, not a behaviour-preserving readability refactor. Treat it
as such (it touches the public surface), unlike the refactors in `SKILL.md` that
must keep the API stable.
