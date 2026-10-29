const KELAS = [
  { value: "1", roman: "I", fase: "A" },
  { value: "2", roman: "II", fase: "A" },
  { value: "3", roman: "III", fase: "B" },
  { value: "4", roman: "IV", fase: "B" },
  { value: "5", roman: "V", fase: "C" },
  { value: "6", roman: "VI", fase: "C" },
];

const FASE_RANGE = {
  A: "Kelas I–II",
  B: "Kelas III–IV",
  C: "Kelas V–VI",
};

const state = {
  kelas: "",
  mapel: "pai",
  q: "",
};

let DATA = [];

const kelasSelect = document.querySelector("#kelas");
const mapelSelect = document.querySelector("#mapel");
const cariInput = document.querySelector("#cari");
const statusEl = document.querySelector("#status");
const hasilEl = document.querySelector("#hasil");
const form = document.querySelector("#controls");
const loadingScreen = document.querySelector("#loading-screen");
const loadingStartedAt = performance.now();

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function hideLoadingScreen() {
  const remainingTime = Math.max(0, 1200 - (performance.now() - loadingStartedAt));
  window.setTimeout(() => {
    loadingScreen.setAttribute("aria-hidden", "true");
    loadingScreen.classList.add("is-hidden");
  }, remainingTime);
}

function normalize(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[\u2019\u2018\u0027\u0060]/g, "")
    .replace(/[\u2013\u2014]/g, "-")
    .toLowerCase();
}

function matchesElement(element, query) {
  return normalize([element.number, element.title, element.text].join(" ")).includes(query);
}

function faseForKelas(value) {
  return KELAS.find((item) => item.value === value).fase;
}

function romanForKelas(value) {
  return KELAS.find((item) => item.value === value).roman;
}

function populate() {
  const placeholder = el("option", "", "Pilih kelas");
  placeholder.value = "";
  kelasSelect.append(placeholder);

  for (const item of KELAS) {
    const option = el("option", "", `Kelas ${item.roman} — Fase ${item.fase}`);
    option.value = item.value;
    kelasSelect.append(option);
  }

  const semua = el("option", "", "Semua mata pelajaran");
  semua.value = "all";
  mapelSelect.append(semua);

  for (const subject of DATA) {
    const option = el("option", "", subject.name);
    option.value = subject.id;
    mapelSelect.append(option);
  }

  if (!DATA.some((subject) => subject.id === state.mapel)) {
    state.mapel = "all";
  }

  kelasSelect.value = state.kelas;
  mapelSelect.value = state.mapel;
}

function renderElement(element) {
  const depth = (element.number.match(/\./g) || []).length;
  const isSub = depth >= 3;
  const section = el("section", isSub ? "element element-sub" : "element");
  const heading = el(isSub ? "h4" : "h3");

  heading.append(el("span", "num", element.number));
  heading.append(document.createTextNode(element.title || ""));
  section.append(heading);

  if (element.text) {
    section.append(el("p", "", element.text));
  } else if (isSub || !/^Elemen\b/.test(element.title)) {
    section.append(el("p", "empty", "Tidak ada teks CP pada dokumen sumber."));
  }

  return section;
}

function renderSubject(subject, fase, elementsToRender) {
  const data = subject.fases[fase];
  const article = el("article", "subject");
  const head = el("header", "subject-head");

  head.append(el("h2", "", subject.name));
  head.append(el("p", "subject-meta", `Fase ${fase} · ${FASE_RANGE[fase]}`));
  article.append(head);

  if (data.intro) {
    article.append(el("p", "intro", data.intro));
  }

  const elements = el("div", "elements");
  for (const element of elementsToRender) {
    elements.append(renderElement(element));
  }
  article.append(elements);

  return article;
}

function unavailableMessage(subject, fase) {
  if (subject.id === "bing" && fase === "A") {
    return "CP Bahasa Inggris pada dokumen sumber dimulai pada Fase B (kelas III–IV), sehingga tidak ada CP untuk Fase A.";
  }
  if (subject.id === "ipas" && fase === "A") {
    return "CP IPAS pada dokumen sumber dimulai pada Fase B (kelas III–IV), sehingga tidak ada CP untuk Fase A.";
  }
  if (subject.id === "koding" && fase !== "C") {
    return "CP Koding dan Kecerdasan Artifisial pada dokumen sumber hanya tersedia untuk Fase C (kelas V–VI).";
  }
  return `Dokumen sumber tidak memuat CP ${subject.name} untuk Fase ${fase}.`;
}

function renderUnavailable(subject, fase) {
  const box = el("div", "notice");
  box.append(el("h2", "", `${subject.name} — Fase ${fase}`));
  box.append(el("p", "", unavailableMessage(subject, fase)));

  const available = Object.keys(subject.fases).sort();
  if (available.length) {
    box.append(el("p", "notice-note", `Fase yang tersedia untuk mata pelajaran ini: ${available.join(", ")}.`));
  }

  hasilEl.replaceChildren(box);
}

function renderNoResults(fase, query) {
  const box = el("div", "notice");
  box.append(el("h2", "", "Tidak ada CP yang cocok"));
  box.append(el("p", "", `Tidak ditemukan teks CP untuk “${query}” pada Fase ${fase}.`));
  if (state.mapel !== "all") {
    box.append(el("p", "notice-note", "Coba pilih “Semua mata pelajaran” atau gunakan kata kunci lain."));
  } else {
    box.append(el("p", "notice-note", "Coba gunakan kata kunci lain."));
  }
  hasilEl.replaceChildren(box);
}

function syncUrl() {
  try {
    const params = new URLSearchParams();
    if (state.kelas) params.set("kelas", state.kelas);
    if (state.mapel !== "pai") params.set("mapel", state.mapel);
    if (state.q.trim()) params.set("q", state.q.trim());
    const query = params.toString();
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}`);
  } catch (error) {
    return;
  }
}

function render() {
  syncUrl();
  if (!state.kelas) {
    statusEl.textContent = "";
    hasilEl.replaceChildren();
    return;
  }

  const fase = faseForKelas(state.kelas);
  const roman = romanForKelas(state.kelas);
  const query = normalize(state.q.trim());
  const selected = state.mapel === "all" ? DATA : DATA.filter((subject) => subject.id === state.mapel);

  if (state.mapel !== "all" && selected.length && !selected[0].fases[fase]) {
    renderUnavailable(selected[0], fase);
    statusEl.textContent = `Kelas ${roman} · Fase ${fase} (${FASE_RANGE[fase]}) · ${selected[0].name} · tidak tersedia`;
    return;
  }

  const results = [];
  let totalElements = 0;

  for (const subject of selected) {
    const data = subject.fases[fase];
    if (!data) continue;

    const subjectMatch = query && normalize(subject.name).includes(query);
    const introMatch = query && normalize(data.intro).includes(query);
    const wholeSubject = !query || subjectMatch || introMatch;
    const elements = wholeSubject
      ? data.elements
      : data.elements.filter((element) => matchesElement(element, query));

    if (!elements.length && !wholeSubject) continue;

    results.push({ subject, elements });
    totalElements += elements.length;
  }

  if (!results.length) {
    renderNoResults(fase, state.q.trim());
    statusEl.textContent = `Kelas ${roman} · Fase ${fase} (${FASE_RANGE[fase]}) · 0 elemen`;
    return;
  }

  hasilEl.replaceChildren();
  for (const result of results) {
    hasilEl.append(renderSubject(result.subject, fase, result.elements));
  }

  if (state.mapel === "all") {
    const missing = DATA.filter((subject) => !subject.fases[fase]).map((subject) => subject.name);
    if (missing.length) {
      hasilEl.append(
        el("p", "availability", `Tidak tersedia pada Fase ${fase}: ${missing.join("; ")}.`)
      );
    }
  }

  const parts = [`Kelas ${roman}`, `Fase ${fase} (${FASE_RANGE[fase]})`];
  if (state.mapel === "all") {
    parts.push(`${results.length} mata pelajaran`);
  } else {
    parts.push(results[0].subject.name);
  }
  parts.push(query ? `${totalElements} elemen cocok` : `${totalElements} elemen`);
  statusEl.textContent = parts.join(" · ");
}

function bind() {
  kelasSelect.addEventListener("change", () => {
    state.kelas = kelasSelect.value;
    render();
  });

  mapelSelect.addEventListener("change", () => {
    state.mapel = mapelSelect.value;
    render();
  });

  let timer;
  cariInput.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      state.q = cariInput.value;
      render();
    }, 120);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    state.q = cariInput.value;
    render();
  });
}

async function init() {
  const params = new URLSearchParams(location.search);
  if (params.has("q")) {
    state.q = params.get("q");
    cariInput.value = state.q;
  }

  try {
    const response = await fetch("data/cp.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    DATA = await response.json();
  } catch (error) {
    statusEl.textContent = "Gagal memuat data CP.";
    const box = el("div", "notice");
    box.append(el("h2", "", "Data tidak dapat dimuat"));
    box.append(el("p", "", "Berkas data/cp.json tidak dapat dibaca. Jalankan aplikasi melalui server lokal, misalnya Laragon, lalu muat ulang halaman."));
    hasilEl.replaceChildren(box);
    hideLoadingScreen();
    return;
  }

  const mapelParam = params.get("mapel");
  if (
    mapelParam &&
    (mapelParam === "all" || DATA.some((subject) => subject.id === mapelParam))
  ) {
    state.mapel = mapelParam;
  }

  populate();
  bind();
  render();
  hideLoadingScreen();
}

init();
