---
name: besimple
description: >-
  Write code the way a thoughtful human engineer would — plain, obvious, and easy
  to follow — not machine-dense or over-abstracted. A founding premise of LARIA.
  Use whenever writing or refactoring LARIA code (any file under core/,
  connector-ha/, ui/), reviewing a diff for readability, or when the user mentions
  readability, simplicity, "clean code", "as if written by hand", or invokes
  /besimple.
---

# besimple

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

## Smells to fix

- Abbreviated/encoded names; single-letter vars outside tiny loops.
- Comments restating the code, or none where a *why* is needed.
- Nesting deeper than ~3; long boolean chains; clever comprehensions doing real work.
- Duplicated SQL/string building repeated many times → name it once (only if it
  genuinely clarifies).
- A function that needs section comments inside it — it wants splitting.
- Inconsistent param/return shapes across sibling functions.

## Check before committing

Read the diff as a stranger would. If any line makes you pause to decode it,
rewrite it plainer. Ask: "would a human reviewer say this reads naturally?"
