import { useEffect, useState } from "react";
import { getBackendInfo } from "./api/backend";
import { TabBar, type TabId } from "./components/TabBar";
import { ConfigTab } from "./components/config/ConfigTab";
import { DownloadTab } from "./components/download/DownloadTab";
import { TasksTab } from "./components/tasks/TasksTab";

type BackendState = { status: "connecting" } | { status: "ready" } | { status: "error"; message: string };

function useBackendReady(): BackendState {
  const [state, setState] = useState<BackendState>({ status: "connecting" });

  useEffect(() => {
    getBackendInfo()
      .then(() => setState({ status: "ready" }))
      .catch((e) => setState({ status: "error", message: e instanceof Error ? e.message : String(e) }));
  }, []);

  return state;
}

export default function App() {
  const backend = useBackendReady();
  const [tab, setTab] = useState<TabId>("tasks");

  if (backend.status !== "ready") {
    return (
      <div className="flex h-screen w-screen items-center justify-center text-sm text-app-muted">
        {backend.status === "connecting" ? "Starting backend…" : `Backend error: ${backend.message}`}
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-app-bg">
      <TabBar active={tab} onChange={setTab} />
      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === "tasks" && <TasksTab />}
        {tab === "download" && <DownloadTab />}
        {tab === "config" && <ConfigTab />}
      </div>
    </div>
  );
}
