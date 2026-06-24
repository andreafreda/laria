---
name: simplecode
description: >-
  Write code the way a thoughtful human engineer would — plain, obvious, and easy
  to follow — not machine-dense or over-abstracted. A founding premise of LARIA.
  Use whenever writing or refactoring LARIA code (any file under core/,
  connector-ha/, ui/), reviewing a diff for readability, or when the user mentions
  readability, simplicity, "clean code", "as if written by hand", or invokes
  /simplecode.
---

# simplecode

Founding premise of LARIA: the code must read as if a careful human wrote it.
Not necessarily short — **clear**. Optimize for the next person (or the next
session) understanding it at a glance, not for cleverness or line count.

## Principles

1. **Obvious over clever.** Prefer the plain solution a competent engineer would
   reach first. No tricks that need a comment to decode. If a one-liner needs a
   mental unpack, write the three readable lines instead.
2. **Name things fully.** Intention-revealing names (`monthly_category_matrix`,
   not `mcm`; `opening_balance`, not `ob`). Match the domain glossary
   (`docs/glossary.md`). No cryptic abbreviations.
3. **Explain *why*, not *what*.** Comments justify a non-obvious decision, a
   tradeoff, or a gotcha. Never narrate what the code already says. Keep the
   comment density of the surrounding code.
4. **Linear flow.** Read top to bottom like prose. Guard clauses for edge cases
   early; avoid deep nesting. One function = one job.
5. **Consistent shape.** Sibling functions look alike (same param order, same
   return shape, same error handling). Predictability is readability.
6. **Don't over-abstract.** A helper earns its place only when it removes real
   duplication or names a real concept. A little repetition is more readable than
   a premature abstraction the reader must chase. Explicit beats magic
   (decorators/metaclasses) when the magic hides control flow.
7. **Length is fine; density is not.** A long file of short, obvious functions is
   good. A short file of dense, multi-purpose functions is not. Split by concept
   when a file mixes unrelated concerns — not to hit a line count.
8. **Type hints + docstrings** on public functions: the signature and one line of
   intent should tell the reader how to use it without reading the body.
9. **Document every main method, human-first.** Every public/important function,
   class and module gets a docstring written for a *person*: say plainly what it
   is for and when you'd reach for it — the intent and the role it plays — not a
   restatement of the signature. Mention non-obvious inputs/outputs, side
   effects, and gotchas. A newcomer should understand *why this exists* from the
   docstring alone. Trivial one-line private helpers may skip it; anything a
   reader would stop to ask "what's this for?" must have it.

## SOLID (apply with judgement, never at the cost of clarity)

Readability comes first, but still design with SOLID in mind:

- **S — Single Responsibility.** Each module/class/function has one reason to
  change. A function that fetches, transforms and renders wants splitting.
- **O — Open/Closed.** Extend via new implementations, not by editing stable
  code. LARIA's seams already do this: add an `LLMProvider` / `MemoryBackend` /
  `Tool`, don't patch the engine.
- **L — Liskov.** Any implementation of an interface must be safely usable in its
  place — same contract, no surprising side effects or weaker guarantees.
- **I — Interface Segregation.** Small, focused interfaces. Don't force an
  implementer to stub methods it doesn't need.
- **D — Dependency Inversion.** Depend on abstractions, not concretions. The
  engine talks to `LLMProvider`/`MemoryBackend`, never to Anthropic/mem0 directly.

Don't over-engineer to "be SOLID": no needless interfaces, factories, or layers
for a single concrete case. Apply the principle when a real second case (or a
real seam) exists — YAGNI wins ties.

## Smells to fix

- Abbreviated/encoded names; single-letter vars outside tiny loops.
- Comments restating the code, or none where a *why* is needed.
- A main method with no docstring, or a docstring that just echoes its name
  instead of explaining what it's for.
- Nesting deeper than ~3; long boolean chains; clever comprehensions doing real work.
- Duplicated SQL/string building repeated many times → name it once (only if it
  genuinely clarifies).
- A function that needs section comments inside it — it wants splitting.
- Inconsistent param/return shapes across sibling functions.

### Classic code smells (avoid)

- **Long parameter lists / data clumps** → group related args into a small object.
- **Feature envy** → logic that mostly touches another module's data belongs there.
- **Primitive obsession** → model a domain concept instead of passing bare
  strings/dicts everywhere.
- **Shotgun surgery** → one change forcing edits in many files = missing seam.
- **God object / leaky abstraction** → a class that knows too much, or an
  interface exposing its implementation.
- **Magic numbers/strings** → name them as constants.
- **Dead code, duplicated logic, deep conditional nesting** → remove, extract,
  flatten.
- **Boolean trap** → a call like `f(true, false)` whose flags are unreadable at
  the call site; prefer named args or distinct functions.

## Check before committing

Read the diff as a stranger would. If any line makes you pause to decode it,
rewrite it plainer. Ask: "would a human reviewer say this reads naturally?"
Then a second pass: any code smell? any SOLID violation that a cheap, clarifying
change would fix? Fix it now if it keeps the code simple; otherwise note it.
