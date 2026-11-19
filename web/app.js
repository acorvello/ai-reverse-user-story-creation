const navigationButtons = Array.from(document.querySelectorAll("[data-page]"));
const pageViews = Array.from(document.querySelectorAll("[data-view]"));
const breadcrumb = document.querySelector("#breadcrumb-current");
const scanForm = document.querySelector("#scan-form");
const scanButton = document.querySelector("#scan-button");
const scanFeedback = document.querySelector("#scan-feedback");
const scanStats = document.querySelector("#scan-stats");
const fileTable = document.querySelector("#file-table-wrap");
const fileList = document.querySelector("#file-list");
const emptyState = document.querySelector("#empty-state");
const resultCount = document.querySelector("#result-count");
const historyList = document.querySelector("#history-list");
const historyEmpty = document.querySelector("#history-empty");
const datasetPanel = document.querySelector("#dataset-panel");
const generateDatasetButton = document.querySelector("#generate-dataset");
const datasetFeedback = document.querySelector("#dataset-feedback");
const settingsForm = document.querySelector("#settings-form");
const settingsFeedback = document.querySelector("#settings-feedback");
const settingsSaveButton = document.querySelector("#settings-save");
const ollamaBaseUrlInput = document.querySelector("#ollama-base-url");
const ollamaModelSelect = document.querySelector("#ollama-model");
const ollamaTestButton = document.querySelector("#ollama-test");
const ollamaFeedback = document.querySelector("#ollama-feedback");
const ollamaStatus = document.querySelector("#ollama-status");
const ollamaStatusText = document.querySelector("#ollama-status-text");

const pageNames = {
  overview: "Visão geral",
  analyze: "Analisar repositório",
  history: "Histórico de análises",
  settings: "Configurações",
};

function getHistory() {
  return JSON.parse(sessionStorage.getItem("reverse-story-history") || "[]");
}

function setPage(page) {
  pageViews.forEach((view) => {
    view.hidden = view.dataset.view !== page;
  });
  navigationButtons.forEach((button) => {
    const active = button.dataset.page === page;
    button.classList.toggle("active", active);
    if (active) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });
  breadcrumb.textContent = pageNames[page];
  if (page === "history") renderHistory();
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function makeCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function setEmptyState(title, description) {
  emptyState.querySelector("strong").textContent = title;
  emptyState.querySelector("span:last-of-type").textContent = description;
}

function renderScan(result) {
  document.querySelector("#overview-date").textContent = new Date().toLocaleString("pt-BR");
  document.querySelector("#overview-files").textContent =
    `${result.file_count} ${result.file_count === 1 ? "arquivo" : "arquivos"}`;
  const rootSummary = document.querySelector("#overview-root");
  rootSummary.textContent = result.root;
  rootSummary.title = result.root;

  document.querySelector("#stat-files").textContent = result.file_count.toLocaleString("pt-BR");
  document.querySelector("#stat-extensions").textContent =
    Object.keys(result.extensions).length.toLocaleString("pt-BR");
  document.querySelector("#stat-size").textContent = formatBytes(result.total_size_bytes);
  scanStats.hidden = false;
  resultCount.textContent =
    `${result.file_count.toLocaleString("pt-BR")} ${result.file_count === 1 ? "arquivo" : "arquivos"}`;

  fileList.replaceChildren();
  result.files.forEach((file) => {
    const row = document.createElement("tr");
    row.append(makeCell(file.path), makeCell(file.extension), makeCell(formatBytes(file.size_bytes)));
    fileList.append(row);
  });

  fileTable.hidden = result.files.length === 0;
  datasetPanel.hidden = result.file_count === 0;
  generateDatasetButton.disabled = result.file_count === 0;
  datasetFeedback.className = "";
  datasetFeedback.textContent = "Uma linha por feature; CSV salvo na pasta datasets.";
  emptyState.hidden = result.files.length > 0;
  if (result.files.length === 0) {
    setEmptyState(
      "Nenhum arquivo compatível encontrado",
      "A pasta foi lida, mas não contém arquivos reconhecidos pelo scanner.",
    );
  }

  const history = getHistory();
  history.unshift({
    root: result.root,
    file_count: result.file_count,
    date: new Date().toISOString(),
  });
  sessionStorage.setItem("reverse-story-history", JSON.stringify(history.slice(0, 30)));
}

function renderHistory() {
  const history = getHistory();
  historyList.replaceChildren();
  historyEmpty.hidden = history.length > 0;

  history.forEach((item) => {
    const article = document.createElement("article");
    article.className = "history-item";

    const icon = document.createElement("span");
    icon.className = "summary-icon lavender";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "▤";

    const copy = document.createElement("div");
    copy.className = "history-copy";
    const root = document.createElement("strong");
    root.textContent = item.root;
    root.title = item.root;
    const details = document.createElement("span");
    const date = new Date(item.date).toLocaleString("pt-BR");
    details.textContent = `${item.file_count} arquivos · ${date}`;
    copy.append(root, details);

    const status = document.createElement("span");
    status.textContent = "Concluída";
    article.append(icon, copy, status);
    historyList.append(article);
  });
}

function populateSettings(config) {
  const scan = config.scan;
  ollamaBaseUrlInput.value = config.ollama.base_url;
  setModelPlaceholder(config.ollama.model, "Teste a conexão para carregar os modelos.");
  settingsForm.elements.max_file_bytes.value = scan.max_file_bytes;
  settingsForm.elements.include_extensions.value = scan.include_extensions.join(", ");
  settingsForm.elements.ignore_dirs.value = scan.ignore_dirs.join(", ");
  settingsForm.elements.sensitive_patterns.value = scan.sensitive_patterns.join(", ");
}

function setOllamaStatus(state, message) {
  ollamaStatus.dataset.state = state;
  ollamaStatusText.textContent = message;
}

function setModelPlaceholder(model, emptyMessage) {
  const option = document.createElement("option");
  option.value = model;
  option.textContent = model || emptyMessage;
  ollamaModelSelect.replaceChildren(option);
  ollamaModelSelect.value = model;
  ollamaModelSelect.disabled = true;
}

function populateOllamaModels(models, selectedModel) {
  if (!Array.isArray(models) || models.some((model) => typeof model !== "string")) {
    throw new Error("O Ollama retornou uma lista de modelos inválida.");
  }
  if (models.length === 0) {
    setModelPlaceholder(selectedModel, "Nenhum modelo compatível instalado.");
    return false;
  }

  ollamaModelSelect.replaceChildren();
  models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    ollamaModelSelect.append(option);
  });
  ollamaModelSelect.value = models.includes(selectedModel) ? selectedModel : models[0];
  ollamaModelSelect.disabled = false;
  return true;
}

function splitList(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

async function testOllamaConnection({ silent = false } = {}) {
  const selectedModel = ollamaModelSelect.value;
  ollamaTestButton.disabled = true;
  setOllamaStatus("checking", "Verificando conexão...");
  setModelPlaceholder(selectedModel, "Verificando modelos...");
  ollamaFeedback.className = "settings-feedback";
  ollamaFeedback.textContent = silent
    ? "Verificando conexão com o Ollama local..."
    : "Consultando os modelos disponíveis no Ollama local...";

  try {
    const response = await fetch("/api/ollama/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_url: ollamaBaseUrlInput.value.trim() }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível conectar ao Ollama.");
    if (!populateOllamaModels(result.models, selectedModel)) {
      setOllamaStatus("connected", "Conectado");
      ollamaFeedback.textContent = "Ollama conectado, mas nenhum modelo compatível com geração foi encontrado.";
      return;
    }

    setOllamaStatus("connected", "Conectado");
    ollamaFeedback.classList.add("is-success");
    ollamaFeedback.textContent = `${result.models.length} modelo(s) disponível(is).`;
  } catch (error) {
    setOllamaStatus("disconnected", "Não conectado");
    setModelPlaceholder(selectedModel, "Teste a conexão para carregar os modelos.");
    ollamaFeedback.classList.add("is-error");
    ollamaFeedback.textContent = error.message || "Falha ao conectar ao Ollama local.";
  } finally {
    ollamaTestButton.disabled = false;
  }
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    const config = await response.json();
    if (!response.ok) throw new Error(config.error || "Não foi possível carregar as configurações.");
    populateSettings(config);
    settingsFeedback.className = "settings-feedback";
    settingsFeedback.textContent = "Configurações carregadas de conf/settings.json.";
    await testOllamaConnection({ silent: true });
  } catch (error) {
    settingsFeedback.className = "settings-feedback is-error";
    settingsFeedback.textContent = error.message || "Falha ao carregar as configurações locais.";
  }
}

navigationButtons.forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.page));
});

document.querySelectorAll("[data-go]").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.go));
});

ollamaTestButton.addEventListener("click", () => testOllamaConnection());

ollamaBaseUrlInput.addEventListener("input", () => {
  const selectedModel = ollamaModelSelect.value;
  setOllamaStatus("disconnected", "Conexão não verificada");
  setModelPlaceholder(selectedModel, "Teste a conexão para carregar os modelos.");
  ollamaFeedback.className = "settings-feedback";
  ollamaFeedback.textContent = "Teste a conexão para atualizar a lista de modelos.";
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  settingsSaveButton.disabled = true;
  settingsFeedback.className = "settings-feedback";
  settingsFeedback.textContent = "Salvando configurações...";

  const payload = {
    scan: {
      max_file_bytes: Number(settingsForm.elements.max_file_bytes.value),
      include_extensions: splitList(settingsForm.elements.include_extensions.value)
        .map((extension) => extension.toLowerCase()),
      ignore_dirs: splitList(settingsForm.elements.ignore_dirs.value),
      sensitive_patterns: splitList(settingsForm.elements.sensitive_patterns.value),
    },
    ollama: {
      base_url: settingsForm.elements.ollama_base_url.value.trim(),
      model: settingsForm.elements.ollama_model.value.trim(),
    },
  };

  try {
    const response = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const config = await response.json();
    if (!response.ok) throw new Error(config.error || "Não foi possível salvar as configurações.");
    populateSettings(config);
    settingsFeedback.classList.add("is-success");
    settingsFeedback.textContent = "Configurações salvas em conf/settings.json.";
    await testOllamaConnection({ silent: true });
  } catch (error) {
    settingsFeedback.classList.add("is-error");
    settingsFeedback.textContent = error.message || "Falha ao salvar as configurações.";
  } finally {
    settingsSaveButton.disabled = false;
  }
});

scanForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const root = new FormData(scanForm).get("root").trim();
  scanButton.disabled = true;
  scanButton.classList.add("is-loading");
  scanButton.querySelector(".button-label").textContent = "Inspecionando...";
  scanStats.hidden = true;
  fileTable.hidden = true;
  datasetPanel.hidden = true;
  generateDatasetButton.disabled = true;
  fileList.replaceChildren();
  resultCount.textContent = "Analisando...";
  emptyState.hidden = false;
  setEmptyState("Inspeção em andamento", "Aguarde enquanto o scanner lê os arquivos locais.");
  scanFeedback.className = "form-feedback";
  scanFeedback.textContent = "Lendo arquivos locais com os filtros do scanner...";

  try {
    const response = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível analisar o repositório.");

    renderScan(result);
    scanFeedback.classList.add("is-success");
    scanFeedback.textContent = "Inspeção concluída. A lista inclui apenas arquivos compatíveis com o scanner.";
  } catch (error) {
    scanFeedback.classList.add("is-error");
    scanFeedback.textContent = error.message || "Falha ao conectar com o servidor local.";
    resultCount.textContent = "Falha na análise";
    setEmptyState("Inspeção não concluída", "Corrija o caminho e tente novamente.");
  } finally {
    scanButton.disabled = false;
    scanButton.classList.remove("is-loading");
    scanButton.querySelector(".button-label").textContent = "Inspecionar código";
  }
});

generateDatasetButton.addEventListener("click", async () => {
  const root = new FormData(scanForm).get("root").trim();
  generateDatasetButton.disabled = true;
  generateDatasetButton.classList.add("is-loading");
  generateDatasetButton.querySelector(".button-label").textContent = "Gerando dataset...";
  datasetFeedback.className = "";
  datasetFeedback.textContent = "Consultando o Ollama local e extraindo features dos módulos...";

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível gerar o dataset.");
    datasetFeedback.classList.add("is-success");
    datasetFeedback.textContent =
      `${result.record_count} registros · modelo ${result.model} · arquivo ${result.output_path}`;
  } catch (error) {
    datasetFeedback.classList.add("is-error");
    datasetFeedback.textContent = error.message || "Falha ao gerar o dataset.";
  } finally {
    generateDatasetButton.disabled = false;
    generateDatasetButton.classList.remove("is-loading");
    generateDatasetButton.querySelector(".button-label").textContent = "Gerar dataset CSV";
  }
});

setPage("overview");
loadSettings();
