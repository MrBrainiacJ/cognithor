const TOOL_LABELS = {
  web_search: "Suche im Web",
  search_and_read: "Lese Webseite",
  exec_command: "Fuehre Befehl aus",
  shell: "Fuehre Befehl aus",
  read_file: "Lese Datei",
  write_file: "Schreibe Datei",
  list_directory: "Liste Verzeichnis auf",
  create_file: "Erstelle Datei",
  delete_file: "Loesche Datei",
  move_file: "Verschiebe Datei",
  memory_store: "Speichere in Memory",
  memory_search: "Durchsuche Memory",
  vault_store: "Speichere im Vault",
  vault_search: "Durchsuche Vault",
  document_export: "Erstelle Dokument",
  canvas_push: "Erstelle Canvas",
  canvas_eval: "Aktualisiere Canvas",
  vision: "Analysiere Bild",
  generate_image: "Generiere Bild",
  code_run: "Fuehre Code aus",
  synthesize: "Generiere Audio",
};

function getToolLabel(name) {
  if (!name) return "Verarbeite...";
  return TOOL_LABELS[name] || name.replace(/_/g, " ");
}

export function ToolIndicator({ tool }) {
  if (!tool) return null;

  return (
    <div className="cc-tool-bar">
      <span className="cc-tool-spinner" />
      <span className="cc-tool-label">{getToolLabel(tool.name)}</span>
    </div>
  );
}
