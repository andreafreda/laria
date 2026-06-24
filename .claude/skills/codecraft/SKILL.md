---
name: codecraft
description: >-
  Write code the way a thoughtful human engineer would: plain, obvious, easy to
  follow, never machine-dense or over-abstracted. Use whenever writing or
  refactoring code in any project, or reviewing a diff for readability, or when
  the user mentions readability, simplicity, "clean code", "as if written by
  hand", or invokes /codecraft. Skip it as the primary lens when the task's main
  goal is a performance hot path, an urgent hotfix, or a security review; there
  readability is a later pass.
---

# codecraft

The premise: code must read as if a careful human wrote it. Not necessarily
short, but clear. Optimize for the next person (or the next session)
understanding it at a glance, not for cleverness or line count. These rules are
project-agnostic; apply them in any codebase and language.

## Not in scope

This skill is about how code reads, not what it does. It does not drive
performance and optimization, security review, or feature and architecture
decisions; those come first and have their own focus. The SOLID and seam notes
below are secondary lenses to keep a readability change honest, not an invitation
to redesign the system. Reach for codecraft when the goal is making code clear
and maintainable.

## The one rule, and how to break ties

**Obvious over clever** is the north star; every other principle serves it. When
two principles pull against each other:

- **Clarity beats brevity.** Three readable lines beat one dense line.
- **Clarity beats DRY.** A little duplication is better than an abstraction the
  reader has to chase. Extract a helper only when it names a real concept and the
  caller reads better for it (principle 6).
- **Clarity beats strict SOLID.** No interface, factory or layer for a single
  concrete case; apply SOLID when a real second case or seam exists.
- **Explicit beats magic.** Prefer visible control flow to a decorator or
  metaclass that hides it, even if the magic is shorter.

Still unclear? Pick the version a new teammate would understand fastest.

## Principles

1. **Obvious over clever.** Prefer the plain solution a competent engineer reaches
   first. If a one-liner needs a mental unpack, write the three readable lines.
2. **Name things fully.** Intention-revealing names (`monthly_category_matrix`,
   not `mcm`). Match the project's domain glossary if it has one. No cryptic
   abbreviations.
3. **Explain the why, not the what.** Comments justify a non-obvious decision, a
   tradeoff, or a gotcha. Never narrate what the code already says.
4. **Linear flow.** Read top to bottom like prose. Guard clauses for edge cases
   early; avoid deep nesting. One function does one job.
5. **Consistent shape.** Sibling functions look alike: same param order, same
   return shape, same error handling. Predictability is readability.
6. **Don't over-abstract.** A helper earns its place only when it removes real
   duplication or names a real concept, not before.
7. **Length is fine; density is not.** Many short obvious functions beat few dense
   ones. Split a file when it mixes unrelated concerns; a function past roughly 40
   lines (more than one screen) is a split candidate.
8. **Make the contract visible.** Type public functions using the language's own
   system (Python hints, TypeScript and C# and Java typed signatures, Go typed
   params). The signature plus one line of intent should tell the reader how to
   use it without reading the body.
9. **Document the public surface, human-first.** Give public or exported symbols,
   and any function past roughly 40 lines, a doc comment
   saying what it is for and when to reach for it (not a restatement of the
   signature); note non-obvious inputs, outputs, side effects and gotchas. For
   private one-liners follow the project's existing convention: if it documents
   sparingly, do the same.
10. **Handle errors honestly.** Catch the specific error you expect, not a blanket
    catch-all that hides bugs. Never swallow an error silently; if you log or
    re-raise, include enough context to act on. Let unexpected failures surface.
11. **Keep side effects at the edges.** Separate pure logic (decisions,
    calculations, shaping data) from IO (database, network, files, clock). Pure
    functions are trivial to read and test; wrap the IO thinly around them.
12. **Write prose like a human.** In doc comments, comments, commit messages and
    READMEs, do not use a dash as a clause connector (em dash or spaced
    `word - word`); it reads as machine-generated. Use a comma, colon, parentheses
    or full stop, and avoid arrow glyphs. Hyphens inside words are fine
    (`case-insensitive`, `read-only`).

## Examples (before and after)

Calibration across languages; apply each language's idioms.

Naming and magic numbers (principle 2), Python:

```python
# before: the name and the literal hide the intent
def calc(n, b):
    return n + b * 0.22

# after: the name states the job, the constant names the value
TAX_RATE = 0.22
def gross_with_tax(net: float, taxable_base: float) -> float:
    return net + taxable_base * TAX_RATE
```

Guard clauses over nesting (principle 4), Go:

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

Visible contract and a doc comment (principles 8 and 9), TypeScript:

```ts
// before
function find(u: any, l: any) { /* ... */ }

// after: types state the contract, the comment states the intent
/** A user's most recent orders, newest first. Returns [] if they have none. */
function recentOrders(userId: string, limit: number): Order[] { /* ... */ }
```

Handle errors honestly (principle 10), C#:

```csharp
// before: a blanket catch hides every bug as "not found"
try { return Load(id); }
catch { return null; }

// after: catch the case you expect, let the rest surface
try { return Load(id); }
catch (FileNotFoundException) { return null; }
```

Make the contract visible (principle 8), Java:

```java
// before
public Object handle(Object req) { ... }

// after: the signature alone tells the caller how to use it
/** Validate and book a reservation; throws SlotTakenException if the slot is gone. */
public Booking book(ReservationRequest request) { ... }
```

## SOLID (apply with judgement)

Readability comes first (see the tie-break rules), but still design with SOLID in
mind, and never add ceremony for a single case (YAGNI):

- **S, Single Responsibility:** one reason to change per module, class, function.
- **O, Open/Closed:** extend by adding an implementation behind an interface, not
  by branching stable code.
- **L, Liskov:** an implementation is safely usable wherever its interface is,
  same contract, no weaker guarantees.
- **I, Interface Segregation:** small focused interfaces; no forced stub methods.
- **D, Dependency Inversion:** depend on an abstraction (a provider, a
  repository), not a concrete vendor or library at the call site.

## Smells to fix

The principles above say what good looks like; these are extra detection signals
not already covered by a numbered principle. Fix the structural ones first, they
hide bugs or block change.

Structural:

- A function or class doing too much: it needs internal section comments, or has
  "and" in its name.
- Duplicated logic, or shotgun surgery (one change forces edits across many files,
  signalling a missing seam).
- Feature envy: logic that mostly touches another module's data belongs there.
- Leaky abstraction: an interface exposing its implementation.

Readability:

- Boolean trap: `f(true, false)` is unreadable at the call site; use named args or
  distinct functions.
- Long parameter lists or data clumps: group related args into a small object.
- Primitive obsession: model the concept instead of passing bare strings or dicts.
- Clever comprehensions or expressions doing real work; unfold them.
- Magic numbers or strings: name them as constants.
- A file with section banners (`# ---- accounts ----`) is several modules in a
  trench coat; each banner is a candidate split.
- Test code treated as second class: unclear test names (a name should state the
  behaviour), no arrange-act-assert shape, or shared fixtures that hide what each
  test sets up. Tests are read more than most code.
- Dead code: delete it.

## When refactoring

- **Keep the public API stable.** When you split a module, re-export the same
  names from a facade so callers don't change. A readability refactor should cost
  the rest of the codebase nothing.
- **Lean on the tests.** Green before and after with no test edits proves the
  behaviour and interface are unchanged. If a refactor forces test changes, that
  is a behaviour change: call it out.
- **One kind of change per commit.** Don't mix moving code with changing logic;
  reviewers can't tell a pure move from a silent fix otherwise.

### Technique: extract the mechanical half of repeated boilerplate

A common shape: the same boilerplate across many functions where only a small
inner part differs (for example, a set of "update only the fields the caller
passed" functions, identical except for the per-field handling). Keep the varying
logic explicit in each caller and extract only the identical mechanical half into
one small named helper. The helper names the concept, callers stay readable, no
magic appears. Skip it when there is only one such function (YAGNI).

## Check before committing

Read the diff as a stranger would; rewrite any line that makes you pause to
decode it. Then scan for a structural smell or a SOLID violation a cheap change
would fix, and fix it if it keeps the code simple.
