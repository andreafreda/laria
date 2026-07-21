# codecraft examples: React

This is an extension file, not a full Core. The eight Core principles
(naming, guard clauses, visible contract, honest errors, side effects at the
edges, clarity beats DRY, explicit beats magic, Dependency Inversion) apply to
React code through plain JavaScript and TypeScript. For those, read
`reference/javascript.md` (vanilla JS, JSDoc contracts, DOM side effects) and
`reference/typescript.md` (typed contracts). The rules themselves live in
`SKILL.md`.

Below are the React-specific shapes those principles take. Examples are in TSX;
in plain JS the same shapes hold with JSDoc or PropTypes for the contract.

## Component contract: typed props, fully named (principles 2, 8)

```tsx
// before: untyped props and a boolean trap; the call site reads createCard(true, false)
function Card(props: any) { /* ... */ }

// after: the props type is the component's contract; a variant union beats flags
type CardProps = {
  title: string;
  variant: "default" | "highlighted";
  dismissible: boolean;
};

/** A content card. `variant` controls emphasis; `dismissible` shows a close button. */
function Card({ title, variant, dismissible }: CardProps) { /* ... */ }
```

## Guard clauses for loading and error states (principle 4)

```tsx
// before: the happy-path markup is buried under nested ternaries
function UserPanel({ query }: { query: UserQuery }) {
  return (
    <div>
      {query.isLoading ? (
        <Spinner />
      ) : query.error ? (
        <Error message={query.error.message} />
      ) : (
        <Profile user={query.data} />
      )}
    </div>
  );
}

// after: return early for each edge state, then the happy path reads straight
function UserPanel({ query }: { query: UserQuery }) {
  if (query.isLoading) return <Spinner />;
  if (query.error) return <Error message={query.error.message} />;
  return <Profile user={query.data} />;
}
```

## Keep logic out of the JSX (principles 4, 10)

```tsx
// before: computation inline in the markup; the template is hard to scan
function OrderRow({ order }: { order: Order }) {
  return (
    <tr>
      <td>{order.items.reduce((s, i) => s + i.price * i.qty, 0).toFixed(2)}</td>
      <td>{order.placedAt.toLocaleDateString("en-GB")}</td>
    </tr>
  );
}

// after: derive named values above the return, keep the JSX a thin template
function OrderRow({ order }: { order: Order }) {
  const total = order.items.reduce((sum, i) => sum + i.price * i.qty, 0);
  const placed = order.placedAt.toLocaleDateString("en-GB");
  return (
    <tr>
      <td>{total.toFixed(2)}</td>
      <td>{placed}</td>
    </tr>
  );
}
```

## Explicit beats magic: derive during render, do not sync with an effect (tie-break)

A `useEffect` that mirrors one piece of state into another hides the data flow and
can render a stale value for one frame. If a value can be computed from props or
state, compute it during render.

```tsx
// before: an effect "magically" keeps fullName in sync; the flow is invisible
function NameTag({ first, last }: { first: string; last: string }) {
  const [fullName, setFullName] = useState("");
  useEffect(() => {
    setFullName(`${first} ${last}`);
  }, [first, last]);
  return <span>{fullName}</span>;
}

// after: derive it directly; there is nothing to keep in sync
function NameTag({ first, last }: { first: string; last: string }) {
  const fullName = `${first} ${last}`;
  return <span>{fullName}</span>;
}
```

## Extract a hook only when it names a real concept (principles 6, and clarity beats DRY)

```tsx
// before: a "useHelpers" grab-bag hook that hides unrelated logic behind one name
function useHelpers(userId: string) {
  const user = useUser(userId);
  const theme = useContext(ThemeContext);
  const [open, setOpen] = useState(false);
  return { user, theme, open, setOpen };
}

// after: keep unrelated concerns visible; extract a hook only when it names one thing
function UserMenu({ userId }: { userId: string }) {
  const user = useUser(userId);
  const theme = useContext(ThemeContext);
  // a hook earns its place when it wraps a real, reusable concept, e.g. useDisclosure()
  const [open, setOpen] = useState(false);
  return (
    <Menu theme={theme} open={open} onToggle={() => setOpen((v) => !v)}>
      {user?.name}
    </Menu>
  );
}
```
