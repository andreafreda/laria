---
name: codecraft
description: >-
  Write code the way a thoughtful human engineer would: plain, obvious, easy to
  follow, never machine-dense or over-abstracted. A founding premise of LARIA.
  Use whenever writing or refactoring LARIA code (any file under core/,
  connector-ha/, ui/), reviewing a diff for readability, or when the user mentions
  readability, simplicity, "clean code", "as if written by hand", or invokes
  /codecraft.
---

# codecraft

Founding premise of LARIA: the code must read as if a careful human wrote it.
Not necessarily short, but clear. Optimize for the next person (or the next
session) understanding it at a glance, not for cleverness or line count.

## Principles

1. **Obvious over clever.** Prefer the plain solution a competent engineer would
   reach first. No tricks that need a comment to decode. If a one-liner needs a
   mental unpack, write the three readable lines instead.
2. **Name things fully.** Intention-revealing names (`monthly_category_matrix`,
   not `mcm`; `opening_balance`, not `ob`). Match the domain glossary
   (`docs/glossary.md`). No cryptic abbreviations.
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
8. **Type hints and docstrings** on public functions: the signature and one line
   of intent should tell the reader how to use it without reading the body.
9. **Document every main method, human-first.** Every public or important
   function, class and module gets a docstring written for a person: say plainly
   what it is for and when you would reach for it (the intent and the role it
   plays), not a restatement of the signature. Mention non-obvious inputs and
   outputs, side effects, and gotchas. A newcomer should understand why this
   exists from the docstring alone. Trivial one-line private helpers may skip it;
   anything a reader would stop to ask "what's this for?" must have it.
10. **No dashes as sentence punctuation in prose.** In docstrings, comments,
    commit messages, READMEs and any written text, do not join clauses with a
    dash, neither an em dash nor a spaced hyphen like `word - word - word`. Use a
    comma, a colon, parentheses, or a full stop instead. Hyphens inside compound
    words are fine (`case-insensitive`, `multi-step`, `read-only`). Avoid arrow
    glyphs in prose too; write "becomes" or use a colon.

## SOLID (apply with judgement, never at the cost of clarity)

Readability comes first, but still design with SOLID in mind:

- **S, Single Responsibility.** Each module, class or function has one reason to
  change. A function that fetches, transforms and renders wants splitting.
- **O, Open/Closed.** Extend via new implementations, not by editing stable code.
  LARIA's seams already do this: add an `LLMProvider`, `MemoryBackend` or `Tool`,
  don't patch the engine.
- **L, Liskov.** Any implementation of an interface must be safely usable in its
  place, with the same contract, no surprising side effects or weaker guarantees.
- **I, Interface Segregation.** Small, focused interfaces. Don't force an
  implementer to stub methods it doesn't need.
- **D, Dependency Inversion.** Depend on abstractions, not concretions. The
  engine talks to `LLMProvider` and `MemoryBackend`, never to Anthropic or mem0
  directly.

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
- Duplicated SQL or string building repeated many times: name it once (only if it
  genuinely clarifies; see "Optional-field updates" below).
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

### Optional-field updates

A recurring shape across CRUD modules: "update only the fields the caller
passed". The mechanical half (collect non-None fields, build the `SET` clause,
run the statement) is identical everywhere; only the per-field coercion differs.
Resolve the duplication without hiding the coercion: keep each caller's coercion
explicit, build a plain `{column: value}` dict, then hand that to one small named
helper that turns it into the `SET` clause and params. The helper names the
concept, the caller stays readable, and no magic is introduced. Skip the helper
only when there is a single such function in the whole codebase (YAGNI).

## When refactoring

- **Keep the public API stable.** When you split a module, re-export the same
  names from a facade (package `__init__`) so callers don't have to change. A
  readability refactor should cost the rest of the codebase nothing.
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
Last, check the prose: no dashes used as sentence punctuation (principle 10).
