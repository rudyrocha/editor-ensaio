"use strict";

const state = { data: null, items: [], polling: null, overview: null, processType: null };
const tracksEl = document.getElementById("tracks");
const errorBox = document.getElementById("errorBox");
const successBox = document.getElementById("successBox");
const summaryEl = document.getElementById("summary");
const closeButton = document.getElementById("closeButton");
const saveButton = document.getElementById("saveButton");
const finalizeButton = document.getElementById("finalizeButton");
const moveRaw = document.getElementById("moveRaw");
const progressPanel = document.getElementById("progressPanel");
const progressTitle = document.getElementById("progressTitle");
const progressText = document.getElementById("progressText");
const logBox = document.getElementById("logBox");
const spinner = document.getElementById("spinner");
const startAnalysisButton = document.getElementById("startAnalysisButton");
const identifyButton = document.getElementById("identifyButton");
const rawStatus = document.getElementById("rawStatus");
const referenceStatus = document.getElementById("referenceStatus");
const reviewWorkspace = document.getElementById("reviewWorkspace");
const actionsFooter = document.getElementById("actionsFooter");
const closeTopButton = document.getElementById("closeTopButton");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  successBox.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function showSuccess(message) {
  successBox.textContent = message;
  successBox.classList.remove("hidden");
  errorBox.classList.add("hidden");
}
function clearMessages() {
  errorBox.classList.add("hidden");
  successBox.classList.add("hidden");
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
}
function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}m${String(secs).padStart(2, "0")}`;
}
function formatClock(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h ? `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
function pauseOtherAudios(currentAudio) {
  document.querySelectorAll("audio").forEach(audio => {
    if (audio !== currentAudio && !audio.paused) audio.pause();
  });
}
function originalSegmentDuration(data) {
  return Math.max(0, Number(data.original.fim_corte_original) - Number(data.original.inicio_corte_original));
}
function previewStartOffset(data) {
  const preview = data.original.preview || {};
  const stored = Number(preview.offset_inicio_corte);
  return Number.isFinite(stored) ? stored : 0;
}
function adjustedStartPhysical(data) {
  return previewStartOffset(data) + Number(data.ajuste_inicio || 0);
}
function adjustedEndPhysical(data) {
  return previewStartOffset(data) + originalSegmentDuration(data) - Number(data.ajuste_fim || 0);
}
function adjustedDuration(data) {
  return Math.max(0, adjustedEndPhysical(data) - adjustedStartPhysical(data));
}
function timelineToPhysical(data, timelineSeconds) {
  return adjustedStartPhysical(data) + Number(timelineSeconds || 0);
}
function physicalToTimeline(data, physicalSeconds) {
  return Number(physicalSeconds || 0) - adjustedStartPhysical(data);
}
function setPhysicalPosition(audio, seconds) {
  const apply = () => {
    const duration = Number.isFinite(audio.duration) ? audio.duration : null;
    const target = duration == null ? Math.max(0, seconds) : clamp(seconds, 0, Math.max(0, duration - 0.05));
    try { audio.currentTime = target; } catch (_) {}
  };
  if (audio.readyState >= 1) {
    apply();
    return Promise.resolve();
  }
  return new Promise(resolve => {
    const onLoaded = () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      apply();
      resolve();
    };
    audio.addEventListener("loadedmetadata", onLoaded, { once: true });
    audio.load();
  });
}
function playTimelineRange(audio, data, startSeconds, stopSeconds = null) {
  pauseOtherAudios(audio);
  const endPhysical = stopSeconds == null ? adjustedEndPhysical(data) : timelineToPhysical(data, stopSeconds);
  audio.dataset.stopPhysical = String(endPhysical);
  return setPhysicalPosition(audio, timelineToPhysical(data, startSeconds))
    .then(() => audio.play().catch(() => {}));
}
function bindPlayer(card) {
  const audio = card.querySelector("audio");
  const playButton = card.querySelector(".play-toggle");
  const seekBar = card.querySelector(".seek-bar");
  const currentTimeEl = card.querySelector(".current-time");
  const totalTimeEl = card.querySelector(".total-time");
  let seeking = false;
  let initialized = false;

  const currentData = () => getCardData(card);

  const configure = () => {
    const data = currentData();
    const duration = adjustedDuration(data);
    const startPhysical = adjustedStartPhysical(data);
    const endPhysical = adjustedEndPhysical(data);
    seekBar.min = "0";
    seekBar.max = String(Math.max(1, Math.round(duration * 10)));
    totalTimeEl.textContent = formatClock(duration);

    const outsideAdjustedRange = audio.currentTime < startPhysical - 0.05 || audio.currentTime > endPhysical + 0.05;
    if (!initialized || outsideAdjustedRange) {
      initialized = true;
      audio.dataset.stopPhysical = "";
      setPhysicalPosition(audio, startPhysical);
      seekBar.value = "0";
      currentTimeEl.textContent = "00:00";
    } else {
      const timeline = clamp(physicalToTimeline(data, audio.currentTime), 0, duration);
      seekBar.value = String(Math.round(timeline * 10));
      currentTimeEl.textContent = formatClock(timeline);
    }
  };

  const syncFromAudio = () => {
    const data = currentData();
    const duration = adjustedDuration(data);
    const timeline = clamp(physicalToTimeline(data, audio.currentTime || 0), 0, duration);
    currentTimeEl.textContent = formatClock(timeline);
    if (!seeking) seekBar.value = String(Math.round(timeline * 10));
    const stop = Number(audio.dataset.stopPhysical);
    if (audio.dataset.stopPhysical !== "" && Number.isFinite(stop) && audio.currentTime >= stop - 0.03) {
      audio.pause();
      audio.dataset.stopPhysical = "";
      setPhysicalPosition(audio, Math.min(stop, adjustedEndPhysical(data)));
      syncFromAudio();
    }
  };

  const seekToSlider = () => {
    const data = currentData();
    const timeline = clamp(Number(seekBar.value) / 10, 0, adjustedDuration(data));
    audio.dataset.stopPhysical = "";
    setPhysicalPosition(audio, timelineToPhysical(data, timeline));
  };

  playButton.addEventListener("click", () => {
    const data = currentData();
    const startPhysical = adjustedStartPhysical(data);
    const endPhysical = adjustedEndPhysical(data);
    if (audio.paused) {
      pauseOtherAudios(audio);
      audio.dataset.stopPhysical = String(endPhysical);
      const outsideAdjustedRange = audio.currentTime < startPhysical - 0.05 || audio.currentTime >= endPhysical - 0.05 || audio.ended;
      const ready = outsideAdjustedRange ? setPhysicalPosition(audio, startPhysical) : Promise.resolve();
      ready.then(() => audio.play().catch(() => {}));
    } else {
      audio.pause();
    }
  });
  audio.addEventListener("play", () => {
    const data = currentData();
    pauseOtherAudios(audio);
    if (audio.dataset.stopPhysical === "") audio.dataset.stopPhysical = String(adjustedEndPhysical(data));
    playButton.textContent = "❚❚";
    playButton.setAttribute("aria-label", "Pausar");
  });
  audio.addEventListener("pause", () => {
    playButton.textContent = "▶";
    playButton.setAttribute("aria-label", "Reproduzir");
  });
  audio.addEventListener("loadedmetadata", configure);
  audio.addEventListener("durationchange", configure);
  audio.addEventListener("timeupdate", syncFromAudio);
  audio.addEventListener("ended", () => {
    audio.dataset.stopPhysical = "";
    playButton.textContent = "▶";
  });
  seekBar.addEventListener("pointerdown", () => { seeking = true; });
  seekBar.addEventListener("input", () => {
    seeking = true;
    const data = currentData();
    const timeline = clamp(Number(seekBar.value) / 10, 0, adjustedDuration(data));
    currentTimeEl.textContent = formatClock(timeline);
    seekToSlider();
  });
  const finishSeek = () => {
    seekToSlider();
    seeking = false;
    syncFromAudio();
  };
  seekBar.addEventListener("change", finishSeek);
  seekBar.addEventListener("pointerup", finishSeek);
  seekBar.addEventListener("keyup", event => {
    if (["ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"].includes(event.key)) finishSeek();
  });
  card.refreshPlayer = configure;
  if (audio.readyState >= 1) configure();
}
function songOptions(current) {
  const known = state.data.musicas.some(item => item === current);
  const options = [`<option value="">Selecione…</option>`]
    .concat(state.data.musicas.map(title => `<option value="${escapeHtml(title)}" ${title === current ? "selected" : ""}>${escapeHtml(title)}</option>`));
  options.push(`<option value="__OUTRA__" ${current && !known ? "selected" : ""}>Outra música…</option>`);
  return options.join("");
}
function qualityOptions(item) {
  return state.data.qualidades.map((quality, index) => `
    <label title="Nível ${index + 1}">
      <input type="radio" name="quality-${item.ordem}" value="${escapeHtml(quality)}" ${item.qualidade === quality ? "checked" : ""}>
      <span>${escapeHtml(quality)}</span>
    </label>`).join("");
}
function recognitionMarkup(item) {
  const suggested = String(item.titulo_sugerido || "").trim();
  if (!suggested) return "";
  const score = Math.round(Number(item.score_identificacao || 0) * 100);
  const second = String(item.segunda_opcao || "").trim();
  const secondScore = Math.round(Number(item.score_segunda_opcao || 0) * 100);
  const applied = Boolean(item.identificacao_aplicada);
  const detail = second ? ` · alternativa: ${escapeHtml(second)} ${secondScore}%` : "";
  const status = applied ? "preenchido automaticamente" : "sugestão para confirmação";
  return `<div class="recognition-note"><b>Reconhecimento:</b> ${escapeHtml(suggested)} · similaridade ${score}%${detail}<br><span>${status}. Se o título final for alterado, a correção será registrada para aprendizado.</span></div>`;
}

function renderTrack(item) {
  const known = state.data.musicas.includes(item.titulo);
  const customVisible = item.titulo && !known;
  const preview = item.preview || {};
  return `
  <article class="track-card ${item.incluir ? "" : "excluded"}" data-order="${item.ordem}">
    <div class="track-head">
      <div class="track-number">${String(item.ordem).padStart(2, "0")}</div>
      <div class="track-title-summary">
        <strong class="summary-title">${escapeHtml(item.titulo || "Faixa sem identificação")}</strong>
        <small>${escapeHtml(item.classificacao || "trecho")} · corte sugerido ${formatClock(item.inicio_corte_original)}–${formatClock(item.fim_corte_original)}</small>
      </div>
      <label class="check-label"><input class="include" type="checkbox" ${item.incluir ? "checked" : ""}> Incluir</label>
    </div>
    <div class="track-body">
      <div>
        <audio class="audio-engine" preload="metadata" src="${escapeHtml(item.audio_url)}"></audio>
        <div class="custom-player">
          <button class="play-toggle" type="button" aria-label="Reproduzir">▶</button>
          <span class="seek-time current-time">00:00</span>
          <input class="seek-bar" type="range" min="0" max="1000" value="0" step="1" aria-label="Linha do tempo do áudio">
          <span class="seek-time total-time">--:--</span>
        </div>
        <div class="audio-tools">
          <button class="mini jump-start" type="button">Ir ao início ajustado</button>
          <button class="mini jump-end" type="button">Ouvir 10s finais</button>
        </div>
        <div class="structure-tools">
          <span class="structure-label">Estrutura:</span>
          <button class="mini structure-button split-track" type="button">Dividir no ponto atual</button>
          <button class="mini structure-button merge-next" type="button">Unir com a próxima</button>
        </div>
      </div>
      <div class="form-grid">
        <div class="field wide">
          <label>Música</label>
          <select class="song-select">${songOptions(item.titulo)}</select>
          <div class="custom-row ${customVisible ? "" : "hidden"}">
            <input class="custom-title" type="text" value="${customVisible ? escapeHtml(item.titulo) : ""}" placeholder="Digite o nome da música">
            <label class="custom-add"><input class="add-list" type="checkbox"> adicionar à lista</label>
          </div>
          ${recognitionMarkup(item)}
        </div>
        <div class="quality">
          <div class="quality-label">Qualidade da execução</div>
          <div class="quality-options">${qualityOptions(item)}</div>
        </div>
        <div class="reference-box">
          <label><input class="reference" type="checkbox" ${item.usar_como_referencia ? "checked" : ""}> Usar no banco de referências</label>
        </div>
        <div class="cut-row">
          <div class="field">
            <label>Ajuste do início (s)</label>
            <input class="delta-start" type="number" step="0.5" value="${Number(item.ajuste_inicio || 0)}">
            <span class="cut-help">+ corta; − acrescenta</span>
          </div>
          <div class="field">
            <label>Ajuste do fim (s)</label>
            <input class="delta-end" type="number" step="0.5" value="${Number(item.ajuste_fim || 0)}">
            <span class="cut-help">+ corta; − acrescenta</span>
          </div>
        </div>
        <div class="field full">
          <label>Observação opcional</label>
          <textarea class="observation" placeholder="Ex.: erro no refrão; versão particularmente boa">${escapeHtml(item.observacao || "")}</textarea>
        </div>
      </div>
      <div class="live-result"></div>
    </div>
  </article>`;
}
function getCardData(card) {
  const order = Number(card.dataset.order);
  const original = state.items.find(item => item.ordem === order);
  const select = card.querySelector(".song-select");
  const custom = card.querySelector(".custom-title");
  const title = select.value === "__OUTRA__" ? custom.value.trim() : select.value.trim();
  const qualityInput = card.querySelector(`input[name="quality-${order}"]:checked`);
  const deltaStart = Number(card.querySelector(".delta-start").value || 0);
  const deltaEnd = Number(card.querySelector(".delta-end").value || 0);
  const start = Number(original.inicio_corte_original) + deltaStart;
  const end = Number(original.fim_corte_original) - deltaEnd;
  return {
    ordem: order,
    incluir: card.querySelector(".include").checked,
    titulo: title,
    qualidade: qualityInput ? qualityInput.value : "",
    usar_como_referencia: card.querySelector(".reference").checked,
    ajuste_inicio: deltaStart,
    ajuste_fim: deltaEnd,
    observacao: card.querySelector(".observation").value.trim(),
    adicionar_lista: select.value === "__OUTRA__" && card.querySelector(".add-list").checked,
    effective_start: start,
    effective_end: end,
    duration: end - start,
    original,
  };
}
function updateCard(card) {
  const data = getCardData(card);
  const title = data.titulo || "Faixa sem identificação";
  const quality = data.qualidade ? `, ${data.qualidade}` : "";
  const invalid = data.duration <= 0 || data.effective_start < 0 || data.effective_end > state.data.duracao_master + .25;
  card.classList.toggle("excluded", !data.incluir);
  card.querySelector(".summary-title").textContent = title;
  card.querySelector(".reference").disabled = !data.incluir;
  const result = card.querySelector(".live-result");
  result.innerHTML = invalid
    ? `<strong>Corte inválido.</strong> Revise os ajustes.`
    : `<strong>${escapeHtml(title + quality)} (${formatDuration(data.duration)})</strong><br>Corte final: ${formatClock(data.effective_start)}–${formatClock(data.effective_end)} · duração ${formatDuration(data.duration)}`;
  result.style.color = invalid ? "#b3261e" : "";
  if (typeof card.refreshPlayer === "function") card.refreshPlayer();
  updateSummary();
}
function updateSummary() {
  const items = [...document.querySelectorAll(".track-card")].map(getCardData);
  const included = items.filter(item => item.incluir);
  const references = included.filter(item => item.usar_como_referencia);
  const total = included.reduce((sum, item) => sum + Math.max(0, item.duration), 0);
  summaryEl.textContent = `${included.length} faixas · ${formatDuration(total)} · ${references.length} referências`;
}

function setInterfaceBusy(busy) {
  saveButton.disabled = busy;
  finalizeButton.disabled = busy;
  closeButton.disabled = busy;
  closeTopButton.disabled = busy;
  startAnalysisButton.disabled = busy || Number(state.overview?.quantidade_brutos || 0) === 0;
  identifyButton.disabled = busy;
  const cards = [...document.querySelectorAll(".track-card")];
  cards.forEach((card, index) => {
    const splitButton = card.querySelector(".split-track");
    const mergeButton = card.querySelector(".merge-next");
    if (splitButton) splitButton.disabled = busy;
    if (mergeButton) mergeButton.disabled = busy || index === cards.length - 1;
  });
}
function renderData(data, focusOrder = null, preserveMoveRaw = true) {
  const previousMoveRaw = moveRaw.checked;
  state.data = data;
  state.items = data.segmentos;
  reviewWorkspace.classList.remove("hidden");
  actionsFooter.classList.remove("hidden");
  identifyButton.classList.remove("hidden");
  document.getElementById("subtitle").textContent = `Ensaio de ${data.data_exibicao} · versão ${data.app_version}`;
  moveRaw.checked = preserveMoveRaw ? previousMoveRaw : data.mover_brutos_padrao;
  tracksEl.innerHTML = data.segmentos.map(renderTrack).join("");
  document.querySelectorAll(".track-card").forEach(bindCard);
  const cards = [...document.querySelectorAll(".track-card")];
  cards.forEach((current, index) => {
    const mergeButton = current.querySelector(".merge-next");
    if (mergeButton) mergeButton.disabled = index === cards.length - 1;
  });
  updateSummary();
  if (focusOrder != null) {
    const target = document.querySelector(`.track-card[data-order="${focusOrder}"]`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}
async function applyStructure(path, payload, successMessage, focusOrder) {
  clearMessages();
  setInterfaceBusy(true);
  showSuccess("Salvando alterações e regenerando as prévias de áudio…");
  try {
    const result = await api(path, payload);
    renderData(result.dados, result.foco_ordem ?? focusOrder, true);
    showSuccess(result.mensagem || successMessage);
  } catch (error) {
    showError(error.message);
  } finally {
    setInterfaceBusy(false);
  }
}
async function splitTrack(card) {
  const data = getCardData(card);
  const audio = card.querySelector("audio");
  const duration = adjustedDuration(data);
  const timeline = clamp(physicalToTimeline(data, audio.currentTime || 0), 0, duration);
  if (timeline < 1 || duration - timeline < 1) {
    showError("Posicione a timeline pelo menos 1 segundo após o início e 1 segundo antes do fim.");
    return;
  }
  if (!window.confirm(`Dividir a faixa ${String(data.ordem).padStart(2, "0")} em ${formatClock(timeline)}? A primeira parte manterá os dados atuais; a segunda será criada para nova identificação.`)) return;
  let base;
  try { base = collectPayload(false); } catch (error) { showError(error.message); return; }
  base.ordem = data.ordem;
  base.ponto_master = data.effective_start + timeline;
  await applyStructure("/api/dividir", base, "Faixa dividida.", data.ordem);
}
async function mergeWithNext(card) {
  const cards = [...document.querySelectorAll(".track-card")];
  const index = cards.indexOf(card);
  if (index < 0 || index >= cards.length - 1) {
    showError("Esta é a última faixa e não há uma próxima faixa para unir.");
    return;
  }
  const current = getCardData(card);
  const next = getCardData(cards[index + 1]);
  const gap = next.effective_start - current.effective_end;
  const gapText = gap > 0.05 ? ` O intervalo de ${formatDuration(gap)} entre elas será mantido.` : "";
  if (!window.confirm(`Unir as faixas ${String(current.ordem).padStart(2, "0")} e ${String(next.ordem).padStart(2, "0")}?${gapText}`)) return;
  let base;
  try { base = collectPayload(false); } catch (error) { showError(error.message); return; }
  base.ordem = current.ordem;
  await applyStructure("/api/unir", base, "Faixas unidas.", current.ordem);
}

function bindCard(card) {
  const select = card.querySelector(".song-select");
  const customRow = card.querySelector(".custom-row");
  bindPlayer(card);
  select.addEventListener("change", () => {
    customRow.classList.toggle("hidden", select.value !== "__OUTRA__");
    if (select.value === "__OUTRA__") card.querySelector(".custom-title").focus();
    updateCard(card);
  });
  card.querySelectorAll("input:not(.seek-bar), textarea").forEach(el => el.addEventListener("input", () => updateCard(card)));
  card.querySelectorAll("input[type=checkbox], input[type=radio]").forEach(el => el.addEventListener("change", () => updateCard(card)));
  card.querySelector(".jump-start").addEventListener("click", () => {
    const data = getCardData(card);
    const audio = card.querySelector("audio");
    playTimelineRange(audio, data, 0);
  });
  card.querySelector(".jump-end").addEventListener("click", () => {
    const data = getCardData(card);
    const audio = card.querySelector("audio");
    const duration = adjustedDuration(data);
    const startAt = Math.max(0, duration - 10);
    playTimelineRange(audio, data, startAt, duration);
  });
  card.querySelector(".split-track").addEventListener("click", () => splitTrack(card));
  card.querySelector(".merge-next").addEventListener("click", () => mergeWithNext(card));
  updateCard(card);
}
function collectPayload(requireComplete = true) {
  const segments = [...document.querySelectorAll(".track-card")].map(getCardData);
  for (const item of segments) {
    if (item.duration < 1 || item.effective_start < 0 || item.effective_end > state.data.duracao_master + .25) {
      throw new Error(`Corte inválido na faixa ${item.ordem}.`);
    }
    if (requireComplete && item.incluir && !item.titulo) throw new Error(`Informe o nome da faixa ${item.ordem}.`);
    if (requireComplete && item.incluir && !item.qualidade) throw new Error(`Avalie a qualidade da faixa ${item.ordem}.`);
  }
  const selected = segments.filter(item => item.incluir).sort((a,b) => a.ordem-b.ordem);
  if (!selected.length) throw new Error("Mantenha pelo menos uma faixa no ensaio.");
  for (let i = 1; i < selected.length; i++) {
    if (selected[i].effective_start < selected[i-1].effective_end - .01) {
      throw new Error(`As faixas ${selected[i-1].ordem} e ${selected[i].ordem} ficaram sobrepostas.`);
    }
  }
  return {
    segmentos: segments.map(({effective_start, effective_end, duration, original, ...rest}) => rest),
    mover_brutos: moveRaw.checked,
  };
}
async function api(path, payload = null) {
  const options = payload ? {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload)} : {};
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.erro || `Erro HTTP ${response.status}`);
  return data;
}
async function save() {
  clearMessages();
  saveButton.disabled = finalizeButton.disabled = true;
  try {
    const payload = collectPayload();
    const result = await api("/api/salvar", payload);
    state.data.musicas = result.musicas || state.data.musicas;
    showSuccess(result.mensagem || "Alterações salvas.");
  } catch (error) {
    showError(error.message);
  } finally {
    saveButton.disabled = finalizeButton.disabled = false;
  }
}
async function finalize() {
  clearMessages();
  let payload;
  try { payload = collectPayload(); } catch (error) { showError(error.message); return; }
  const action = payload.mover_brutos ? "gerar o vídeo e mover os brutos após a validação" : "gerar o vídeo mantendo os brutos";
  if (!window.confirm(`Confirma ${action}?`)) return;
  saveButton.disabled = finalizeButton.disabled = true;
  try {
    await api("/api/finalizar", payload);
    state.processType = "finalizacao";
    progressPanel.classList.remove("hidden");
    progressTitle.textContent = "Finalizando…";
    progressText.textContent = "Gerando áudio, vídeo, capítulos, descrição e referências.";
    spinner.classList.remove("hidden");
    progressPanel.scrollIntoView({behavior: "smooth", block: "start"});
    pollStatus();
  } catch (error) {
    showError(error.message);
    saveButton.disabled = finalizeButton.disabled = false;
  }
}
async function refreshOverview() {
  const overview = await api("/api/estado");
  state.overview = overview;
  const files = overview.brutos || [];
  rawStatus.textContent = files.length
    ? `${files.length} arquivo(s) de gravação em brutas: ${files.join(", ")}`
    : "Nenhum arquivo WAV encontrado na pasta brutas.";
  referenceStatus.textContent = `${overview.referencias_ativas || 0} referências ativas · ${overview.musicas || 0} músicas na lista.`;
  startAnalysisButton.disabled = files.length === 0;
  if (overview.revisao_disponivel) {
    const current = overview.revisao_atual;
    if (current) {
      referenceStatus.textContent += ` Análise atual: ${current.data_exibicao}, ${current.segmentos} faixa(s).`;
    }
    identifyButton.classList.remove("hidden");
  }
  return overview;
}

async function startAnalysis() {
  clearMessages();
  if (state.overview?.revisao_disponivel) {
    if (!window.confirm("Iniciar uma nova análise? A revisão atual será preservada no histórico e substituída pela nova análise.")) return;
  }
  setInterfaceBusy(true);
  try {
    await api("/api/analisar", {});
    state.processType = "analise";
    progressPanel.classList.remove("hidden");
    progressTitle.textContent = "Analisando gravações…";
    progressText.textContent = "Detectando faixas, gerando prévias e comparando com o banco de referências.";
    spinner.classList.remove("hidden");
    progressPanel.scrollIntoView({behavior: "smooth", block: "start"});
    pollStatus();
  } catch (error) {
    showError(error.message);
    setInterfaceBusy(false);
  }
}

async function reidentify() {
  clearMessages();
  setInterfaceBusy(true);
  identifyButton.textContent = "Identificando…";
  try {
    let payload = {};
    if (state.data) payload = collectPayload(false);
    const result = await api("/api/identificar", payload);
    renderData(result.dados, null, true);
    showSuccess(result.mensagem || "Identificação concluída.");
  } catch (error) {
    showError(error.message);
  } finally {
    identifyButton.textContent = "Identificar músicas novamente";
    setInterfaceBusy(false);
  }
}

async function pollStatus() {
  clearTimeout(state.polling);
  try {
    const status = await api("/api/status");
    const type = status.tipo || state.processType || "finalizacao";
    logBox.textContent = status.log || "Aguardando saída do processo…";
    logBox.scrollTop = logBox.scrollHeight;
    if (status.estado === "executando") {
      state.polling = setTimeout(pollStatus, 1500);
      return;
    }
    spinner.classList.add("hidden");
    if (status.estado === "concluido") {
      if (type === "analise") {
        progressTitle.textContent = "Análise concluída";
        progressText.textContent = "A revisão foi preparada. Confira os nomes sugeridos, cortes e avaliações.";
        const data = await api("/api/dados");
        moveRaw.checked = data.mover_brutos_padrao;
        renderData(data, null, false);
        await refreshOverview();
        showSuccess("Análise concluída. A página de revisão está pronta.");
        reviewWorkspace.scrollIntoView({behavior: "smooth", block: "start"});
      } else {
        progressTitle.textContent = "Processo concluído";
        progressText.textContent = "Vídeo, áudio, capítulos, descrição e referências foram gerados com sucesso.";
        showSuccess("Finalização concluída com sucesso.");
        await refreshOverview();
      }
    } else if (status.estado === "erro") {
      progressTitle.textContent = type === "analise" ? "A análise encontrou um erro" : "A finalização encontrou um erro";
      progressText.textContent = "Consulte o log abaixo.";
      showError(`${type === "analise" ? "A análise" : "A finalização"} terminou com erro ${status.codigo}.`);
    }
  } catch (error) {
    showError(error.message);
  }
  setInterfaceBusy(false);
}

async function load() {
  try {
    const overview = await refreshOverview();
    document.getElementById("subtitle").textContent = `Versão ${overview.app_version} · pronto para iniciar ou continuar um ensaio`;
    if (overview.revisao_disponivel) {
      const data = await api("/api/dados");
      moveRaw.checked = data.mover_brutos_padrao;
      renderData(data, null, false);
    } else {
      reviewWorkspace.classList.add("hidden");
      actionsFooter.classList.add("hidden");
    }
  } catch (error) {
    showError(error.message);
  }
}

startAnalysisButton.addEventListener("click", startAnalysis);
identifyButton.addEventListener("click", reidentify);
async function closeInterface() {
  if (!window.confirm("Encerrar a interface local? Alterações não salvas serão perdidas.")) return;
  try {
    await api("/api/encerrar", {});
    document.body.innerHTML = '<main style="max-width:720px;margin:80px auto;font-family:Segoe UI,Arial;padding:24px"><h1>Interface encerrada</h1><p>Você já pode fechar esta aba.</p></main>';
  } catch (error) { showError(error.message); }
}
closeButton.addEventListener("click", closeInterface);
closeTopButton.addEventListener("click", closeInterface);
saveButton.addEventListener("click", save);
finalizeButton.addEventListener("click", finalize);
load();