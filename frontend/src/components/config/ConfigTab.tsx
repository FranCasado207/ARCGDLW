import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { openFolder, pickFile } from "../../lib/native";
import { Button } from "../ui/Button";
import { FieldLabel, TextArea, TextField } from "../ui/Field";

export function ConfigTab() {
  const [path, setPath] = useState<string | null>(null);
  const [exists, setExists] = useState(false);
  const [content, setContent] = useState("");
  const [status, setStatus] = useState<{ text: string; ok: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const config = await api.getConfig();
    setPath(config.path);
    setExists(config.exists);
    setContent(config.content);
    setStatus(
      config.exists
        ? { text: `✔ Found: ${config.path}`, ok: true }
        : { text: "✘ No config file found", ok: false },
    );
  }

  useEffect(() => {
    load();
  }, []);

  async function browse() {
    const chosen = await pickFile(path ?? undefined, ["json", "conf"]);
    if (!chosen) return;
    await api.updateSettings({ gallery_dl_config: chosen });
    await load();
  }

  async function createDefault() {
    setError(null);
    try {
      const { path: created } = await api.createDefaultConfig();
      await load();
      setStatus({ text: `Default config created at: ${created}`, ok: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function openConfigFolder() {
    const paths = await api.getPaths();
    if (paths.config_dir) await openFolder(paths.config_dir);
  }

  async function openAppFolder() {
    const paths = await api.getPaths();
    await openFolder(paths.app_data_dir);
  }

  async function save() {
    setError(null);
    try {
      const { path: saved } = await api.saveConfig(content);
      setStatus({ text: `✔ Saved: ${saved}`, ok: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <div>
        <h1 className="text-xl font-bold text-app-text">gallery-dl Configuration</h1>
        <p className="mt-1 text-xs text-app-muted">
          Edit the gallery-dl config file. Changes apply to all downloads and tasks.
        </p>
      </div>
      <div className="h-px bg-app-border" />

      <div>
        <FieldLabel>Config file</FieldLabel>
        <div className="flex gap-2">
          <TextField value={path ?? ""} placeholder="No config file selected" readOnly />
          <Button onClick={browse}>Browse…</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {status && (
          <span className={`text-xs ${status.ok ? "text-green-500" : "text-red-500"}`}>{status.text}</span>
        )}
        <div className="flex-1" />
        <Button title="Runs: gallery-dl --config-create" onClick={createDefault}>
          Create Default Config
        </Button>
        <Button disabled={!path} onClick={openConfigFolder}>
          Open Folder
        </Button>
        <Button
          title="Opens ARCGDLW's own settings/data folder (app_settings.json, tasks.json, previews) — not the gallery-dl config folder."
          onClick={openAppFolder}
        >
          Open ARCGDLW Folder
        </Button>
      </div>

      <div className="h-px bg-app-border" />

      {error && <p className="text-xs text-red-500">{error}</p>}

      <FieldLabel>Config content (JSON)</FieldLabel>
      <TextArea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="min-h-0 flex-1 resize-none font-mono text-[13px]"
      />

      <div className="flex justify-end gap-2">
        <Button onClick={load}>Reload</Button>
        <Button variant="primary" onClick={save}>
          Save
        </Button>
      </div>

      {!exists && (
        <p className="text-xs text-app-muted">
          No config file exists yet at the shown path — edit and Save to create one, or use "Create Default
          Config".
        </p>
      )}
    </div>
  );
}
