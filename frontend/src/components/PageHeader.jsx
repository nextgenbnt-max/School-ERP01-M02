export default function PageHeader({ title, description, actions, testid }) {
  return (
    <div className="mb-6 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center" data-testid={testid}>
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
