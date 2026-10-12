const HOURS = Array.from({ length: 10 }, (_, index) => index + 10);
const SAMPLE = {
  capacity: 20,
  fuelBudget: 17,
  maxDark: 2,
  outageHours: [12, 13, 14, 15, 17, 18, 19],
  fuelTiers: [
    { load: 7, rate: 1.2 },
    { load: 14, rate: 2 },
const SAMPLE = {
  capacity: 20,
  fuelBudget: 17,
  maxDark: 2,
  outageHours: [12, 13, 14, 15, 17, 18, 19],
  fuelTiers: [
    { load: 7, rate: 1.2 },
    { load: 14, rate: 2 },
    { load: 20, rate: 2.8 }
  ],
  shops: [
    { id: "pharmacy", kw: 3, type: "mandatory", values: [6,6,6,6,6,6,6,6,6,6] },
    { id: "atm_booth", kw: 2, type: "mandatory", values: [4,4,4,4,4,4,4,4,4,4] },
    { id: "tailor_jamal", kw: 4, type: "normal", values: [2,2,3,3,4,4,4,4,5,5] },
    { id: "mobile_shop", kw: 3, type: "normal", values: [1,1,2,2,2,3,4,6,8,8] },
    { id: "photocopy", kw: 2, type: "normal", values: [3,3,5,5,4,3,2,2,1,1] },
    { id: "tea_stall", kw: 1, type: "normal", values: [2,2,3,3,3,2,2,3,3,3] },
    { id: "beauty_salon", kw: 4, type: "normal", values: [1,1,2,3,4,5,5,4,3,2] },
    { id: "grocery_fridge", kw: 3, type: "normal", values: [3,3,3,3,3,3,4,5,5,4] },
    { id: "electronics", kw: 5, type: "normal", values: [1,1,2,2,3,3,5,6,7,6] },
    { id: "restaurant", kw: 6, type: "normal", values: [2,3,6,7,5,3,3,5,7,8] },
    { id: "jewellery", kw: 3, type: "normal", values: [1,2,3,3,3,3,4,5,5,3] },
    { id: "clothing", kw: 2, type: "normal", values: [2,2,3,3,3,4,5,5,4,3] }
  ]
};

const form = document.getElementById("scenario-form");
const shopList = document.getElementById("shop-list");
const fuelTiers = document.getElementById("fuel-tiers");
const hourSlots = document.getElementById("hour-slots");
const inputArea = document.getElementById("input-json");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const summaryEl = document.getElementById("summary");
const rosterTable = document.getElementById("roster-table");
const darkSummaryEl = document.getElementById("shop-dark-summary");
const hourSummaryEl = document.getElementById("hour-summary");
let latestResult = null;
let hasCalculated = false;
let recalculationTimer = null;
let requestSequence = 0;
let activeRequest = null;

function scheduleRecalculation(delay = 450) {
  if (!hasCalculated) return;
  window.clearTimeout(recalculationTimer);
  requestSequence += 1;
  if (activeRequest) activeRequest.abort();
  activeRequest = null;
  const button = document.getElementById("generate");
  button.disabled = false;
  button.classList.remove("is-loading");
  latestResult = null;
  resultsEl.classList.add("hidden");
  setStatus("Inputs changed. Recalculating the roster…", "working");
  recalculationTimer = window.setTimeout(() => {
    if (!form.checkValidity()) {
      setStatus("Complete all required fields to update the roster.", "error");
      return;
    }
    form.requestSubmit();
  }, delay);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

function setStatus(message, kind = "success") {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`;
}

function renderHourSlots(outageHours = []) {
  hourSlots.innerHTML = HOURS.map((hour) => {
    const isOutage = outageHours.includes(hour);
    return `<button class="hour-slot ${isOutage ? "is-outage" : "is-grid"}" type="button" data-hour="${hour}" aria-pressed="${isOutage}" title="${hour}:00 — ${isOutage ? "Outage" : "Grid available"}">
      <span>${hour}:00</span>
      <small>${isOutage ? "Outage" : "Grid available"}</small>
    </button>`;
  }).join("");
}

function addShop(shop = {}) {
  const entry = document.createElement("div");
  entry.className = "shop-entry";
  const row = document.createElement("div");
  row.className = "shop-row";
  row.innerHTML = `
    <label class="shop-name-field">
      <span class="mobile-field-label">Shop name</span>
      <input class="shop-name" type="text" maxlength="80" placeholder="e.g. pharmacy" value="${escapeHtml(shop.id || "")}" required />
    </label>
    <label>
      <span class="mobile-field-label">Power</span>
      <span class="input-with-unit compact"><input class="shop-kw" type="number" min="1" step="1" placeholder="3" value="${shop.kw ?? ""}" required /><span>kW</span></span>
    </label>
    <label>
      <span class="mobile-field-label">Type</span>
      <select class="shop-type" aria-label="Shop type">
        <option value="normal" ${shop.type !== "mandatory" ? "selected" : ""}>Normal</option>
        <option value="mandatory" ${shop.type === "mandatory" ? "selected" : ""}>Mandatory</option>
      </select>
    </label>
    <label>
      <span class="mobile-field-label">Hourly values</span>
      <button class="values-toggle" type="button" aria-expanded="false">10 hourly values <span>⌄</span></button>
    </label>
    <button class="remove-shop" type="button" aria-label="Remove shop" title="Remove shop">×</button>
  `;
  const values = shop.values || Array(10).fill("");
  const valuesPanel = document.createElement("div");
  valuesPanel.className = "shop-values hidden";
  valuesPanel.innerHTML = HOURS.map((hour, index) => `
    <label><span>${hour}:00</span><input class="shop-value" type="number" min="0" step="1" value="${escapeHtml(values[index] ?? "")}" required /></label>
  `).join("");
  entry.append(row, valuesPanel);
  shopList.append(entry);
}

function renderFuelTiers(tiers) {
  fuelTiers.innerHTML = tiers.map((tier, index) => `
    <div class="fuel-tier">
      <span class="tier-caption">${escapeHtml(["Low load", "Medium load", "Full load"][index] || `Load tier ${index + 1}`)}</span>
      <span class="input-with-unit compact"><input class="tier-load" type="number" min="1" step="1" aria-label="Load limit, kilowatts" value="${tier.load}" required /><span>up to kW</span></span>
      <span class="fuel-equals">→</span>
      <span class="input-with-unit compact"><input class="tier-rate" type="number" min="0" step="0.01" aria-label="Diesel per hour, litres" value="${tier.rate}" required /><span>L/hour</span></span>
      <button class="remove-fuel-tier" type="button" aria-label="Remove fuel tier">×</button>
    </div>
  `).join("");
}

function setFormValues(data) {
  document.getElementById("capacity").value = data.capacity;
  document.getElementById("fuel-budget").value = data.fuelBudget;
  document.getElementById("max-dark").value = data.maxDark;
  shopList.replaceChildren();
  data.shops.forEach(addShop);
  renderFuelTiers(data.fuelTiers);
  renderHourSlots(data.outageHours);
}

function samplePayload() {
  return {
    grid_available: HOURS.map((hour) => !SAMPLE.outageHours.includes(hour)),
    generator_capacity_kw: SAMPLE.capacity,
    fuel_budget_litres: SAMPLE.fuelBudget,
    fuel_table: SAMPLE.fuelTiers.map(({ load, rate }) => ({ load_kw: load, litres_per_hour: rate })),
    max_consecutive_dark: SAMPLE.maxDark,
    shops: SAMPLE.shops.map((shop) => ({
      id: shop.id,
      kw: shop.kw,
      type: shop.type,
      value_per_slot: [...shop.values]
    }))
  };
}

function loadSample() {
  setFormValues(SAMPLE);
  inputArea.value = JSON.stringify(samplePayload(), null, 2);
  hasCalculated = true;
  scheduleRecalculation(0);
  setStatus("Sample loaded. Finding the best roster…", "working");
}

function clearScenario() {
  document.getElementById("capacity").value = "";
  document.getElementById("fuel-budget").value = "";
  document.getElementById("max-dark").value = "";
  shopList.replaceChildren();
  renderFuelTiers([
    { load: 5, rate: "" },
    { load: 10, rate: "" },
    { load: 15, rate: "" }
  ]);
  renderHourSlots();
  latestResult = null;
  hasCalculated = false;
  resultsEl.classList.add("hidden");
  setStatus("Inputs cleared. Enter a new scenario to continue.", "neutral");
}

function collectPayload() {
  const entries = [...shopList.querySelectorAll(".shop-entry")];
  if (entries.length > 12) {
    throw new Error("You can add up to 12 shops.");
  }
  const shops = entries.map((entry) => {
    const row = entry.querySelector(".shop-row");
    const id = row.querySelector(".shop-name").value.trim();
    const kw = Number(row.querySelector(".shop-kw").value);
    const type = row.querySelector(".shop-type").value;
    const values = [...entry.querySelectorAll(".shop-value")].map((input) => Number(input.value));
    return {
      id,
      kw,
      type,
      value_per_slot: values
    };
  });

  const seenNames = new Set();
  for (const shop of shops) {
    const normalizedName = shop.id.toLocaleLowerCase();
    if (seenNames.has(normalizedName)) {
      throw new Error(`Duplicate shop name: ${shop.id}`);
    }
    seenNames.add(normalizedName);
  }
  if (shops.length === 0) {
    throw new Error("Add at least one shop to calculate a roster.");
  }

  const tiers = [...fuelTiers.querySelectorAll(".fuel-tier")].map((tier) => ({
    load_kw: Number(tier.querySelector(".tier-load").value),
    litres_per_hour: Number(tier.querySelector(".tier-rate").value)
  }));
  const capacity = Number(document.getElementById("capacity").value);
  if (tiers.length === 0) {
    throw new Error("Add at least one fuel consumption tier.");
  }
  for (let index = 0; index < tiers.length; index += 1) {
    if (index > 0 && tiers[index].load_kw <= tiers[index - 1].load_kw) {
      throw new Error("Fuel load tiers must be in strictly increasing order.");
    }
  }
  if (tiers[tiers.length - 1].load_kw !== capacity) {
    throw new Error("The final fuel tier must match the generator's maximum capacity.");
  }

  const outageHours = new Set(
    [...hourSlots.querySelectorAll(".hour-slot.is-outage")].map((slot) => Number(slot.dataset.hour))
  );

  return {
    grid_available: HOURS.map((hour) => !outageHours.has(hour)),
    generator_capacity_kw: capacity,
    fuel_budget_litres: Number(document.getElementById("fuel-budget").value),
    fuel_table: tiers,
    max_consecutive_dark: Number(document.getElementById("max-dark").value),
    shops
  };
}

function renderSummary(data, payload) {
  const outageCount = payload.grid_available.filter((available) => !available).length;
  const totalHours = data.hours.length;
  summaryEl.innerHTML = `
    <article class="metric-card"><span class="metric-icon">ϟ</span><span class="metric-label">Total value</span><strong>${escapeHtml(data.value_total)}</strong><small>points</small></article>
    <article class="metric-card"><span class="metric-icon">◉</span><span class="metric-label">Fuel used</span><strong>${escapeHtml(data.fuel_total_litres)}</strong><small>litres / ${escapeHtml(payload.fuel_budget_litres)} litres</small></article>
    <article class="metric-card"><span class="metric-icon">▦</span><span class="metric-label">Outage hours</span><strong>${outageCount}</strong><small>out of ${totalHours} hours</small></article>
    <article class="metric-card"><span class="metric-icon">⌂</span><span class="metric-label">Shops</span><strong>${payload.shops.length}</strong><small>in this plan</small></article>
  `;
}

function renderDarkSummary(data) {
  const entries = Object.entries(data.per_shop_dark_hours || {})
    .filter(([, hours]) => hours.length > 0)
    .sort((a, b) => a[0].localeCompare(b[0]));
  if (!entries.length) {
    darkSummaryEl.innerHTML = '<p class="empty-result">Fuel and capacity are sufficient to keep every shop powered.</p>';
    return;
  }
  darkSummaryEl.innerHTML = `<ul class="dark-list">${entries.map(([shop, hours]) =>
    `<li><span class="shop-avatar">${escapeHtml(shop.slice(0, 1).toUpperCase())}</span><strong>${escapeHtml(shop)}</strong><span class="dark-count">${hours.length} hours</span><span class="dark-reasons">${hours.map((slot) => {
      const rosterHour = data.hours.find((hour) => hour.hour === `${slot + 10}:00`);
      const darkEntry = rosterHour?.dark.find((entry) => entry.id === shop);
      const reason = darkEntry?.reason || "Limited generator capacity or fuel.";
      return `<span title="${escapeHtml(reason)}">${slot + 10}:00 · ${escapeHtml(reason)}</span>`;
    }).join("")}</span></li>`
  ).join("")}</ul>`;
}

function renderHourSummary(data) {
  const outagePlans = data.hours.filter((hour) => !hour.grid);
  if (!outagePlans.length) {
    hourSummaryEl.innerHTML = '<p class="empty-result">There are no grid outages in this schedule.</p>';
    return;
  }
  let runningFuel = 0;
  hourSummaryEl.innerHTML = outagePlans.map((hour) => {
    runningFuel += Number(hour.fuel_used_litres);
    return `
      <div class="hour-plan">
        <strong>${escapeHtml(hour.hour)}</strong>
        <span class="load-meter" role="img" aria-label="${escapeHtml(hour.load_kw)} kW of ${escapeHtml(hour.capacity_kw)} kW"><i style="width:${Math.min(100, (hour.load_kw / hour.capacity_kw) * 100)}%"></i></span>
        <span>${escapeHtml(hour.load_kw)} / ${escapeHtml(hour.capacity_kw)} kW</span>
        <span class="fuel-value">${escapeHtml(hour.fuel_used_litres)} L</span>
        <small>Total ${runningFuel.toFixed(2)} / ${escapeHtml(document.getElementById("fuel-budget").value)} L</small>
      </div>
    `;
  }).join("");
}

function renderRoster(data, payload) {
  const hours = data.hours;
  const allShops = [...new Set(hours.flatMap((hour) =>
    hour.powered.concat(hour.dark.map((entry) => entry.id))
  ))].sort();
  const shopsById = new Map(payload.shops.map((shop) => [shop.id, shop]));
  const header = `<thead><tr><th>Shop</th>${hours.map((hour) =>
    `<th class="${hour.grid ? "grid-heading" : "outage-heading"}">${escapeHtml(hour.hour)}<small>${hour.grid ? "Grid" : "Generator"}</small></th>`
  ).join("")}</tr></thead>`;
  const rows = allShops.map((shopId) => {
    const cells = hours.map((hour) => {
      if (hour.powered.includes(shopId)) {
        return `<td>${hour.grid
          ? '<span class="roster-state state-grid">Grid</span>'
          : '<span class="roster-state state-on" aria-label="Powered">✓</span>'}</td>`;
      }
      if (hour.dark.some((entry) => entry.id === shopId)) {
        const darkEntry = hour.dark.find((entry) => entry.id === shopId);
        const reason = darkEntry.reason || "Generator constraint.";
        return `<td><span class="roster-state state-off" title="${escapeHtml(reason)}" aria-label="Dark: ${escapeHtml(reason)}">✗</span></td>`;
      }
      return '<td><span class="roster-state state-idle">—</span></td>';
    }).join("");
    const mandatory = shopsById.get(shopId)?.type === "mandatory";
    return `<tr><th scope="row">${escapeHtml(shopId)}${mandatory ? '<span class="mandatory-tag">Mandatory</span>' : ""}</th>${cells}</tr>`;
  }).join("");
  rosterTable.innerHTML = `<table><caption>Shops powered by the grid or generator during each hour</caption>${header}<tbody>${rows}</tbody></table>`;
}

async function generateRoster(event) {
  event.preventDefault();
  window.clearTimeout(recalculationTimer);
  requestSequence += 1;
  const currentRequest = requestSequence;
  if (activeRequest) activeRequest.abort();
  activeRequest = null;
  if (!form.reportValidity()) return;
  latestResult = null;
  resultsEl.classList.add("hidden");

  let payload;
  try {
    payload = collectPayload();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }

  const button = document.getElementById("generate");
  const controller = new AbortController();
  activeRequest = controller;
  button.disabled = true;
  button.classList.add("is-loading");
  setStatus("Finding the best roster…", "working");
  let response;
  try {
    response = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
  } catch {
    if (controller.signal.aborted || currentRequest !== requestSequence) return;
    activeRequest = null;
    button.disabled = false;
    button.classList.remove("is-loading");
    setStatus("Could not connect to the server. Check that the app is running.", "error");
    return;
  }

  let result;
  try {
    result = await response.json();
  } catch {
    if (currentRequest !== requestSequence) return;
    setStatus("The server returned an unreadable JSON response.", "error");
    return;
  } finally {
    if (currentRequest === requestSequence) {
      activeRequest = null;
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  if (currentRequest !== requestSequence) return;
  hasCalculated = true;
  if (!response.ok || result.status === "invalid_input") {
    setStatus(result.detail || "The input could not be validated.", "error");
    return;
  }
  if (result.status === "infeasible") {
    const conflictDetails = Array.isArray(result.conflicts)
      ? result.conflicts.map((conflict) => conflict.rule).join(", ")
      : "";
    setStatus(
      `${result.detail || "A valid roster could not be created from these inputs."}${conflictDetails ? ` (${conflictDetails})` : ""}`,
      "error"
    );
    return;
  }
  latestResult = result;
  renderSummary(result, payload);
  renderDarkSummary(result);
  renderHourSummary(result);
  renderRoster(result, payload);
  resultsEl.classList.remove("hidden");
  setStatus("Your power roster is ready.", "success");
  resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyJsonText(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    setStatus("Could not parse the JSON. Check commas, quotes, and brackets.", "error");
    return false;
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    setStatus("The top-level JSON value must be an object.", "error");
    return false;
  }
  if (!Array.isArray(payload.grid_available) || payload.grid_available.length !== 10 ||
      !Array.isArray(payload.fuel_table) || payload.fuel_table.length === 0 ||
      !Array.isArray(payload.shops) || payload.shops.length > 12 ||
      !Number.isFinite(payload.generator_capacity_kw) ||
      !Number.isFinite(payload.fuel_budget_litres) ||
      !Number.isInteger(payload.max_consecutive_dark)) {
    setStatus("Check that grid_available, generator_capacity_kw, fuel_budget_litres, fuel_table, max_consecutive_dark, and shops are valid.", "error");
    return false;
  }
  if (payload.shops.some((shop) =>
    !shop || typeof shop.id !== "string" || !Number.isFinite(shop.kw) ||
    !["mandatory", "normal"].includes(shop.type) ||
    !Array.isArray(shop.value_per_slot) || shop.value_per_slot.length !== 10
  )) {
    setStatus("Each shop must have an id, kw, type, and exactly 10 value_per_slot entries.", "error");
    return false;
  }
  if (payload.fuel_table.some((tier) =>
    !tier || !Number.isFinite(tier.load_kw) || !Number.isFinite(tier.litres_per_hour)
  )) {
    setStatus("Each fuel_table tier must have numeric load_kw and litres_per_hour values.", "error");
    return false;
  }

  setFormValues({
    capacity: payload.generator_capacity_kw,
    fuelBudget: payload.fuel_budget_litres,
    maxDark: payload.max_consecutive_dark,
    outageHours: HOURS.filter((_, index) => payload.grid_available[index] === false),
    fuelTiers: payload.fuel_table.map((tier) => ({ load: tier.load_kw, rate: tier.litres_per_hour })),
    shops: payload.shops.map((shop) => ({
      id: shop.id,
      kw: shop.kw,
      type: shop.type,
      values: shop.value_per_slot
    }))
  });
  inputArea.value = JSON.stringify(payload, null, 2);
  setStatus("JSON applied to the form. Review the inputs and calculate the roster.");
  scheduleRecalculation();
  return true;
}

function downloadOutput() {
  if (!latestResult) {
    setStatus("Calculate a roster before downloading the output.", "error");
    return;
  }
  const blob = new Blob([`${JSON.stringify(latestResult, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "roster-output.json";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

hourSlots.addEventListener("click", (event) => {
  const button = event.target.closest(".hour-slot");
  if (!button) return;
  const outage = button.classList.contains("is-outage");
  button.classList.toggle("is-outage", !outage);
  button.classList.toggle("is-grid", outage);
  button.setAttribute("aria-pressed", String(!outage));
  button.querySelector("small").textContent = outage ? "Grid available" : "Outage";
  button.title = `${button.dataset.hour}:00 — ${outage ? "Grid available" : "Outage"}`;
  scheduleRecalculation();
});

shopList.addEventListener("click", (event) => {
  const toggleButton = event.target.closest(".values-toggle");
  if (toggleButton) {
    const valuesPanel = toggleButton.closest(".shop-entry").querySelector(".shop-values");
    const expanded = toggleButton.getAttribute("aria-expanded") === "true";
    valuesPanel.classList.toggle("hidden", expanded);
    toggleButton.setAttribute("aria-expanded", String(!expanded));
  }
  const removeButton = event.target.closest(".remove-shop");
  if (removeButton) {
    removeButton.closest(".shop-entry").remove();
    scheduleRecalculation();
  }
});

document.getElementById("add-shop").addEventListener("click", () => {
  if (shopList.querySelectorAll(".shop-entry").length >= 12) {
    setStatus("You can add up to 12 shops.", "error");
    return;
  }
  addShop();
  shopList.lastElementChild.querySelector(".shop-name").focus();
  scheduleRecalculation();
});

fuelTiers.addEventListener("click", (event) => {
  const removeButton = event.target.closest(".remove-fuel-tier");
  if (!removeButton) return;
  if (fuelTiers.querySelectorAll(".fuel-tier").length === 1) {
    setStatus("At least one fuel consumption tier is required.", "error");
    return;
  }
  removeButton.closest(".fuel-tier").remove();
  scheduleRecalculation();
});

document.getElementById("add-fuel-tier").addEventListener("click", () => {
  const capacity = Number(document.getElementById("capacity").value);
  const tiers = [...fuelTiers.querySelectorAll(".tier-load")];
  const previousLoad = Number(tiers[tiers.length - 1]?.value || 0);
  if (previousLoad >= capacity) {
    setStatus("Lower the highest load tier before adding another tier.", "error");
    return;
  }
  const nextLoad = Math.min(capacity, previousLoad + Math.max(1, Math.round(capacity / 3)));
  const tier = document.createElement("div");
  tier.className = "fuel-tier";
  tier.innerHTML = `<span class="tier-caption">Load tier ${tiers.length + 1}</span>
    <span class="input-with-unit compact"><input class="tier-load" type="number" min="1" step="1" aria-label="Load limit, kilowatts" value="${nextLoad}" required /><span>up to kW</span></span>
    <span class="fuel-equals">→</span>
    <span class="input-with-unit compact"><input class="tier-rate" type="number" min="0" step="0.01" aria-label="Diesel per hour, litres" placeholder="0.00" required /><span>L/hour</span></span>
    <button class="remove-fuel-tier" type="button" aria-label="Remove fuel tier">×</button>`;
  fuelTiers.append(tier);
  tier.querySelector(".tier-rate").focus();
  scheduleRecalculation();
});

document.getElementById("toggle-outages").addEventListener("click", () => {
  renderHourSlots();
  scheduleRecalculation();
});
document.getElementById("load-sample").addEventListener("click", loadSample);
document.getElementById("clear-input").addEventListener("click", clearScenario);
document.getElementById("apply-json").addEventListener("click", () => applyJsonText(inputArea.value));
document.getElementById("input-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    applyJsonText(await file.text());
  } catch {
    setStatus("Could not read the file. Choose a valid JSON file.", "error");
  }
});
document.getElementById("download-output").addEventListener("click", downloadOutput);
document.getElementById("print-output").addEventListener("click", () => window.print());
form.addEventListener("submit", generateRoster);
form.addEventListener("input", scheduleRecalculation);

setFormValues(SAMPLE);
inputArea.value = JSON.stringify(samplePayload(), null, 2);
setStatus("Review the inputs and calculate a roster.");
