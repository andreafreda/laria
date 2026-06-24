---
name: codecraft
description: >-
  Write code the way a thoughtful human engineer would: plain, obvious, easy to
  follow, never machine-dense or over-abstracted. Use whenever writing or
  refactoring code in any project, or reviewing a diff for readability, or when
  the user mentions readability, simplicity, "clean code", "as if written by
  hand", or invokes /codecraft. Do not invoke it as the primary lens for
  performance-critical hot paths, urgent hotfixes, or security reviews; those
  need their own focus and readability is a later pass.
avoid_when: "performance-critical path, urgent hotfix, security review"
---

# codecraft

The premise: code must read as if a careful human wrote it. Not necessarily
short, but clear. Optimize for the next person (or the next session)
understanding it at a glance, not for cleverness or line count. These rules are
project-agnostic; apply them in any codebase and language.

## Not in scope

This skill is about how code reads, not what it does. It does not cover:

- **Performance or optimization** (profiling, complexity, caching strategy). Use
  a performance pass for that; do not trade clarity for speed under this skill.
- **Security review** (auth, injection, secrets, crypto). Use a dedicated
  security review.
- **Functional correctness or architecture decisions** (is the feature right,
  which design to pick). Those come first; readability polishes the result.

When a task is really about one of those, do that work; reach for codecraft when
the goal is making code clear and maintainable.

## The one rule, and how to break ties

**Obvious over clever** is the north star. Every other principle serves it. When
two principles pull against each other, resolve the tie like this:

- **Clarity beats brevity.** Three readable lines beat one dense line.
- **Clarity beats DRY.** A little duplication is better than an abstraction the
  reader has to chase. Extract a helper only when it names a real concept and the
  caller reads better for it (principle 6 over principle 4).
- **Clarity beats strict SOLID.** Do not add an interface, factory or layer for a
  single concrete case. Apply SOLID when a real second case or seam exists.
- **Explicit beats magic.** Prefer visible control flow to a decorator or
  metaclass that hides it, even if the magic is shorter.

If after this a choice is still genuinely unclear, pick the version a new teammate
would understand fastest.

## Principles

1. **Obvious over clever.** Prefer the plain solution a competent engineer would
   reach first. No tricks that need a comment to decode. If a one-liner needs a
   mental unpack, write the three readable lines instead.
2. **Name things fully.** Intention-revealing names (`monthly_category_matrix`,
   not `mcm`; `opening_balance`, not `ob`). If the project keeps a domain
   glossary, match it. No cryptic abbreviations.
3. **Explain the why, not the what.** Comments justify a non-obvious decision, a
   tradeoff, or a gotcha. Never narrate what the code already says. Keep the
   comment density of the surrounding code.
4. **Linear flow.** Read top to bottom like prose. Guard clauses for edge cases
   early; avoid deep nesting. One function does one job.
5. **Consistent shape.** Sibling functions look alike (same param order, same
   return shape, same error handling). Predictability is readability.
6. **Don't over-abstract.** A helper earns its place only when it removes real
   duplication or names a real concept. A little repetition is more readable than
   a premature abstraction the reader must chase.
7. **Length is fine; density is not.** A long file of short, obvious functions is
   good. A short file of dense, multi-purpose functions is not. Split by concept
   when a file mixes unrelated concerns, not to hit a line count.
8. **Make the contract visible.** Put types on public functions using the
   language's own system (Python type hints, TypeScript types, C# and Java typed
   signatures, Go typed params). The signature plus one line of intent should
   tell the reader how to use it without reading the body.
9. **Document every main method, human-first.** Every public or important
   function, class and module gets a doc comment written for a person: what it is
   for and when you would reach for it, not a restatement of the signature.
   Mention non-obvious inputs, outputs, side effects, and gotchas. Trivial
   one-line private helpers may skip it; anything a reader would stop to ask
   "what's this for?" must have it.
10. **Handle errors honestly.** Catch the specific exception you expect, not a
    blanket catch-all that also hides bugs you didn't anticipate. Never swallow an
    error silently; if you handle it, do something meaningful, and if you re-raise
    or log, include enough context to act on. Let truly unexpected failures
    surface rather than masking them behind a vague fallback.
11. **Keep side effects at the edges.** Separate pure logic (decisions,
    calculations, shaping data) from IO (database, network, files, clock). Pure
    functions are trivial to read and test; push the IO into thin wrappers around
    them.
12. **Write prose like a human, not like a model.** In doc comments, comments,
    commit messages and READMEs, avoid the dash as a clause connector, both the em
    dash and the spaced hyphen like `word - word - word`. Models lean on it far
    more than people do, so it reads as a tell of generated text; natural
    punctuation reads more human. Use a comma, a colon, parentheses, or a full
    stop. Hyphens inside compound words are fine (`case-insensitive`,
    `multi-step`, `read-only`). Avoid arrow glyphs in prose too; write "becomes"
    or use a colon.

## Examples (before and after)

Calibration. The moves are universal; apply each language's idioms.

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

Guard clauses over nesting (principle 4), Python:

```python
# before: the happy path is buried three levels deep
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

Visible contract and a doc comment (principles 8 and 9), TypeScript:

```ts
// before
function find(u: any, l: any) { /* ... */ }

// after: types state the contract, the comment states the intent
/** Find a user's most recent orders, newest first. Returns [] if they have none. */
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

## SOLID (apply with judgement, never at the cost of clarity)

Readability comes first (see the tie-break rules above), but still design with
SOLID in mind:

- **S, Single Responsibility.** Each module, class or function has one reason to
  change. A function that fetches, transforms and renders wants splitting.
- **O, Open/Closed.** Extend by adding a new implementation, not by editing
  stable code. Add a new provider or adapter behind an existing interface rather
  than branching the consumer.
- **L, Liskov.** Any implementation of an interface must be safely usable in its
  place, with the same contract, no surprising side effects or weaker guarantees.
- **I, Interface Segregation.** Small, focused interfaces. Don't force an
  implementer to stub methods it doesn't need.
- **D, Dependency Inversion.** Depend on abstractions, not concretions. Code
  against an interface (a provider, a repository, a backend), not a specific
  vendor or library buried in the call site.

Don't over-engineer to "be SOLID": no needless interfaces, factories, or layers
for a single concrete case. YAGNI wins ties.

## Smells to fix (roughly by impact)

Structural (fix first, they hide bugs or block change):

- A blanket `except`/`catch` where one specific error is meant, or an error
  caught and silently dropped.
- A function or class doing too much: it needs internal section comments, or its
  name has "and" in it. Split it (single responsibility).
- Duplicated logic, or shotgun surgery (one change forces edits across many
  files, which signals a missing seam).
- Deep nesting (beyond about three levels) and long boolean chains; flatten with
  guard clauses.
- Feature envy: logic that mostly touches another module's data belongs there.
- Leaky abstraction: an interface that exposes its implementation.

Readability (fix next, they slow the reader):

- Abbreviated or encoded names; single-letter vars outside tiny loops.
- A main method with no doc comment, or one that just echoes its name.
- Comments restating the code, or none where a why is needed.
- Magic numbers or strings: name them as constants.
- Boolean trap: a call like `f(true, false)` whose flags are unreadable at the
  call site. Prefer named args or distinct functions.
- Long parameter lists or data clumps: group related args into a small object.
- Primitive obsession: model a domain concept instead of passing bare strings or
  dicts everywhere.
- Clever comprehensions or expressions doing real work; unfold them.
- Inconsistent param or return shapes across sibling functions.
- A file carrying section banners (`# ---- accounts ----`) is usually several
  modules in a trench coat; each banner is a candidate split.
- Dead code: delete it, the history remembers.

## When refactoring

- **Keep the public API stable.** When you split a module, re-export the same
  names from a facade (for example a package `__init__`) so callers don't have to
  change. A readability refactor should cost the rest of the codebase nothing.
- **Lean on the tests.** Run them before and after; green with no test edits is
  the proof the behaviour and the interface are unchanged. If a refactor forces
  test changes, it is a behaviour change, so call it out, don't bury it.
- **One kind of change at a time.** Don't mix "move code" with "change logic" in
  one commit; reviewers can't tell a pure move from a silent fix otherwise.

### Technique: extract the mechanical half of repeated boilerplate

A common shape: the same boilerplate repeated across many functions, where only a
small inner part differs. A classic example is a set of "update only the fields
the caller passed" functions, where collecting the set fields, building the
update statement and running it is identical and only the per-field handling
differs. Resolve it without hiding the part that varies: keep the varying logic
explicit in each caller, and extract only the identical mechanical half into one
small named helper. The helper names the concept, the callers stay readable, and
no magic is introduced. Skip the helper when there is only one such function
(YAGNI).

## Check before committing

Read the diff as a stranger would. If any line makes you pause to decode it,
rewrite it plainer. Ask: "would a human reviewer say this reads naturally?"
Then a second pass: any structural smell? any SOLID violation that a cheap,
clarifying change would fix? Fix it now if it keeps the code simple; otherwise
note it. Last, check the prose: no dashes used as sentence punctuation (principle
12).
