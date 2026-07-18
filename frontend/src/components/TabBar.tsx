export type TabId = "tasks" | "download" | "config";

const TABS: { id: TabId; label: string }[] = [
  { id: "tasks", label: "Tasks" },
  { id: "download", label: "Download" },
  { id: "config", label: "Config" },
];

export function TabBar({ active, onChange }: { active: TabId; onChange: (id: TabId) => void }) {
  return (
    <div className="flex border-b border-app-border px-2">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`cursor-pointer border-b-2 px-6 py-2.5 text-sm font-medium transition-colors ${
            active === tab.id
              ? "border-app-accent text-app-text"
              : "border-transparent text-app-muted hover:text-app-text"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
