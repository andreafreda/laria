---
name: codecraft
description: >-
  Write code the way a thoughtful human engineer would: plain, obvious, easy to
  follow, never machine-dense or over-abstracted. Use whenever writing or
  refactoring code in any project, reviewing a diff for readability, or when the
  user mentions readability, simplicity, "clean code", "as if written by hand",
  or invokes /codecraft.
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
   a premature abstraction the reader must chase. Explicit beats magic
   (decorators, metaclasses) when the magic hides control flow.
7. **Length is fine; density is not.** A long file of short, obvious functions is
   good. A short file of dense, multi-purpose functions is not. Split by concept
   when a file mixes unrelated concerns, not to hit a line count.
8. **Types and docstrings** on public functions: the signature and one line of
   intent should tell the reader how to use it without reading the body. Use the
   language's own type system (Python type hints, TypeScript types, C# types,
   typed signatures in Go, and so on); the principle is "make the contract
   visible in the signature", not any one language's syntax.
9. **Document every main method, human-first.** Every public or important
   function, class and module gets a docstring written for a person: say plainly
   what it is for and when you would reach for it (the intent and the role it
   plays), not a restatement of the signature. Mention non-obvious inputs and
   outputs, side effects, and gotchas. A newcomer should understand why this
   exists from the docstring alone. Trivial one-line private helpers may skip it;
   anything a reader would stop to ask "what's this for?" must have it.
10. **Handle errors honestly.** Catch the specific exception you expect, not a
    blanket catch-all that also hides bugs you didn't anticipate. Never swallow
    an error silently; if you handle it, do something meaningful, and if you
    re-raise or log, include enough context to act on. Let truly unexpected
    failures surface rather than masking them behind a vague fallback.
11. **Keep side effects at the edges.** Separate pure logic (decisions,
    calculations, shaping data) from IO (database, network, files, clock). Pure
    functions are trivial to read and test; push the IO into thin wrappers around
    them. A function that both computes and persists is harder to reason about
    than two that each do one thing.
12. **Write prose like a human, not like a model.** In docstrings, comments,
    commit messages and READMEs, avoid the dash as a clause connector, both the
    em dash and the spaced hyphen like `word - word - word`. Models lean on it
    far more than people do, so it reads as a tell of generated text; natural
    punctuation reads more human. Use a comma, a colon, parentheses, or a full
    stop instead. Hyphens inside compound words are fine (`case-insensitive`,
    `multi-step`, `read-only`). Avoid arrow glyphs in prose too; write "becomes"
    or use a colon.

## Examples (before and after)

Concrete calibration. The language is Python, but the moves are universal: apply
the same idea with each language's idioms.

Naming and magic numbers (principle 2):

```python
# before: the name and the literal hide the intent
def calc(n, b):
    return n + b * 0.22

# after: the name states the job, the constant names the value
TAX_RATE = 0.22
def gross_with_tax(net: float, taxable_base: float) -> float:
    return net + taxable_base * TAX_RATE
```

Nesting and guard clauses (principle 4):

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

## SOLID (apply with judgement, never at the cost of clarity)

Readability comes first, but still design with SOLID in mind:

- **S, Single Responsibility.** Each module, class or function has one reason to
  change. A function that fetches, transforms and renders wants splitting.
- **O, Open/Closed.** Extend by adding a new implementation, not by editing
  stable code. For example, add a new provider or adapter behind an existing
  interface rather than branching the consumer.
- **L, Liskov.** Any implementation of an interface must be safely usable in its
  place, with the same contract, no surprising side effects or weaker guarantees.
- **I, Interface Segregation.** Small, focused interfaces. Don't force an
  implementer to stub methods it doesn't need.
- **D, Dependency Inversion.** Depend on abstractions, not concretions. Code
  against an interface (a provider, a repository, a backend), not a specific
  vendor or library buried in the call site.

Don't over-engineer to "be SOLID": no needless interfaces, factories, or layers
for a single concrete case. Apply the principle when a real second case (or a
real seam) exists. YAGNI wins ties.

## Smells to fix

- Abbreviated or encoded names; single-letter vars outside tiny loops.
- Comments restating the code, or none where a why is needed.
- A main method with no docstring, or a docstring that just echoes its name
  instead of explaining what it is for.
- Nesting deeper than about three levels; long boolean chains; clever
  comprehensions doing real work.
- A blanket `except Exception` (or bare `except`) used where one specific
  exception is meant; an exception caught and silently dropped.
- A function that needs section comments inside it: it wants splitting.
- A file carrying section banners (`# ---- accounts ----`, `# ---- reports ----`)
  is usually several modules in a trench coat. Each banner is a candidate split.
- Inconsistent param or return shapes across sibling functions.

### Classic code smells (avoid)

- **Long parameter lists or data clumps:** group related args into a small object.
- **Feature envy:** logic that mostly touches another module's data belongs there.
- **Primitive obsession:** model a domain concept instead of passing bare strings
  or dicts everywhere.
- **Shotgun surgery:** one change forcing edits in many files means a missing seam.
- **God object or leaky abstraction:** a class that knows too much, or an
  interface exposing its implementation.
- **Magic numbers or strings:** name them as constants.
- **Dead code, duplicated logic, deep conditional nesting:** remove, extract,
  flatten.
- **Boolean trap:** a call like `f(true, false)` whose flags are unreadable at the
  call site. Prefer named args or distinct functions.

### Mechanical duplication with a varying core

A common shape: the same boilerplate repeated across many functions, where only a
small inner part differs. A classic example is a set of "update only the fields
the caller passed" functions, where collecting the set fields, building the
update statement and running it is identical and only the per-field handling
differs. Resolve it without hiding the part that varies: keep the varying logic
explicit in each caller, and extract only the identical mechanical half into one
small named helper. The helper names the concept, the callers stay readable, and
no magic is introduced. Skip the helper when there is only one such function
(YAGNI).

## When refactoring

- **Keep the public API stable.** When you split a module, re-export the same
  names from a facade (for example a package `__init__`) so callers don't have to
  change. A readability refactor should cost the rest of the codebase nothing.
- **Lean on the tests.** Run them before and after; green with no test edits is
  the proof the behaviour and the interface are unchanged. If a refactor forces
  test changes, it is a behaviour change, so call it out, don't bury it.
- **One kind of change at a time.** Don't mix "move code" with "change logic" in
  one commit; reviewers can't tell a pure move from a silent fix otherwise.

## Check before committing

Read the diff as a stranger would. If any line makes you pause to decode it,
rewrite it plainer. Ask: "would a human reviewer say this reads naturally?"
Then a second pass: any code smell? any SOLID violation that a cheap, clarifying
change would fix? Fix it now if it keeps the code simple; otherwise note it.
Last, check the prose: no dashes used as sentence punctuation (principle 12).
