requireLogin();

const MAX_BYTES = 5 * 1024 * 1024;
const form = document.getElementById("bill-form");
const imageInput = document.getElementById("image");
const dropzone = document.getElementById("dropzone");
const statusBox = document.getElementById("status");
const preview = document.getElementById("preview");
const previewImg = document.getElementById("preview-img");
const alertBox = document.getElementById("alert");
const customerSelect = document.getElementById("customer");
const matchInfo = document.getElementById("match-info");
const itemsBody = document.getElementById("items");
const totalInput = document.getElementById("total_amount");
const sumText = document.getElementById("sum-text");
const sumBadge = document.getElementById("sum-badge");
const ocrText = document.getElementById("ocr-text");
const saveButton = document.getElementById("save");

let selectedFile = null;
let fullText = "";
let previewUrl = null;

function setStatus(message, busy = false, kind = "") {
  statusBox.classList.remove("hidden");
  statusBox.replaceChildren(...[
    busy ? el("span", { class: "spinner" }) : null,
    kind ? el("span", { class: `badge badge-${kind}`, text: message }) : el("span", { text: message }),
  ].filter(Boolean)
  );
}

function mark(input, value) {
  input.classList.remove("filled", "missing");
  input.classList.add(value === null || value === undefined || value === "" ? "missing" : "filled");
}

function clearMarks() {
  form.querySelectorAll(".filled, .missing").forEach(node => node.classList.remove("filled", "missing"));
}

function addItemRow(item = { name: "", qty: 1, amount: "" }, highlight = false) {
  const name = el("input", { value: item.name || "", placeholder: "Product name", maxlength: 100 });
  const qty = el("input", { type: "number", min: 1, step: 1, value: item.qty || 1, class: "col-qty" });
  const amount = el("input", { type: "number", min: 0, step: "0.01", value: item.amount || "", class: "num" });
  if (highlight) [name, qty, amount].forEach(input => input.classList.add("filled"));
  const row = el("tr", {},
    el("td", {}, name),
    el("td", { class: "col-qty" }, qty),
    el("td", { class: "col-amount" }, amount),
    el("td", { class: "col-del" }, el("button", {
      class: "btn btn-ghost", type: "button", title: "Remove product", "aria-label": "Remove product", text: "✕",
      onclick: () => { row.remove(); if (!itemsBody.children.length) addItemRow(); updateSum(); },
    })),
  );
  row.addEventListener("input", (event) => { event.target.classList.remove("filled", "missing"); updateSum(); });
  itemsBody.append(row);
  updateSum();
}

function readItems() {
  return [...itemsBody.querySelectorAll("tr")].map(row => {
    const [name, qty, amount] = row.querySelectorAll("input");
    return { name: name.value.trim(), qty: qty.value, amount: amount.value };
  }).filter(item => item.name || item.amount);
}

function updateSum() {
  const sum = readItems().reduce((total, item) => total + (Number(item.amount) || 0), 0);
  sumText.textContent = `Items add up to ${money(sum)}`;
  const total = totalInput.value === "" ? null : Number(totalInput.value);
  if (total === null || !readItems().length) {
    sumBadge.replaceChildren();
  } else if (Math.abs(total - sum) < 0.005) {
    sumBadge.replaceChildren(el("span", { class: "badge badge-ok", text: "Matches total" }));
  } else {
    sumBadge.replaceChildren(el("span", { class: "badge badge-warn", text: "Does not match total" }));
  }
}

async function loadCustomers() {
  try {
    const data = await apiJson("/account/api/registrations/?page_size=100&ordering=name");
    customerSelect.replaceChildren(
      el("option", { value: "", text: "Select a customer…" }),
      ...data.results.map(c => el("option", { value: c.id, text: `${c.name} · ${c.mobile}` })),
    );
  } catch (error) {
    showAlert(alertBox, `Could not load customers: ${error.message}`);
  }
}

function showMatch(result) {
  const read = [result.customer_name, result.mobile].filter(Boolean).join(" · ") || "nothing";
  const match = result.matched_customer;
  const parts = [el("span", { text: `Read from image: ${read}. ` })];
  if (match) {
    customerSelect.value = String(match.id);
    const labels = { name_and_mobile: ["ok", "Matched by name and mobile"], mobile: ["warn", "Matched by mobile only, check the name"], name: ["warn", "Matched by name only, check the mobile"] };
    const [kind, text] = labels[match.matched_by] || ["warn", "Matched"];
    parts.push(el("span", { class: `badge badge-${kind}`, text }));
    mark(customerSelect, match.id);
  } else {
    customerSelect.value = "";
    parts.push(el("span", { class: "badge badge-bad", text: "No matching customer" }));
    parts.push(el("span", { text: " Choose one, or register the customer on the " }), el("a", { href: "/account/customers/", target: "_blank", text: "Customers page" }), ".");
    mark(customerSelect, null);
  }
  matchInfo.replaceChildren(...parts);
}

function fillForm(result) {
  form.bill_id.value = result.bill_id || "";
  mark(form.bill_id, result.bill_id);
  form.printed_at.value = result.printed_at || "";
  mark(form.printed_at, result.printed_at);
  totalInput.value = result.total_amount || "";
  mark(totalInput, result.total_amount);
  itemsBody.replaceChildren();
  if (result.products && result.products.length) {
    result.products.forEach(item => addItemRow(item, true));
  } else {
    addItemRow();
    itemsBody.querySelectorAll("input").forEach(input => input.classList.add("missing"));
  }
  showMatch(result);
  fullText = result.full_text || "";
  ocrText.textContent = fullText || "No text was found in the image.";
  updateSum();
}

async function runOcr(file) {
  hideAlert(alertBox);
  if (!["image/png", "image/jpeg"].includes(file.type)) { showAlert(alertBox, "Choose a PNG or JPEG image."); return; }
  if (file.size > MAX_BYTES) { showAlert(alertBox, "Image must be 5 MB or smaller."); return; }
  selectedFile = file;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  previewImg.src = previewUrl;
  preview.classList.remove("hidden");
  saveButton.disabled = true;
  setStatus("Reading text from the image…", true);
  const body = new FormData();
  body.append("image", file);
  try {
    const result = await apiJson("/account/api/ocr/", { method: "POST", body });
    await customersReady;
    fillForm(result);
    const found = ["bill_id", "customer_name", "mobile", "total_amount", "printed_at"].filter(key => result[key]).length + (result.products.length ? 1 : 0);
    setStatus(found === 6 ? "All 6 details found. Please check them." : `${found} of 6 details found. Fill the red fields.`, false, found === 6 ? "ok" : "warn");
  } catch (error) {
    setStatus("Could not read the image.", false, "bad");
    showAlert(alertBox, error.message);
  } finally {
    saveButton.disabled = !selectedFile;
  }
}

function resetForm() {
  form.reset();
  clearMarks();
  itemsBody.replaceChildren();
  addItemRow();
  selectedFile = null;
  fullText = "";
  imageInput.value = "";
  ocrText.textContent = "Upload an image to see the text.";
  matchInfo.textContent = "Name and mobile read from the image are used to pick the customer.";
  preview.classList.add("hidden");
  statusBox.classList.add("hidden");
  saveButton.disabled = true;
  if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
  updateSum();
}

function validate() {
  const problems = [];
  const billId = form.bill_id.value.trim().toUpperCase();
  if (!/^B-\d{4,10}$/.test(billId)) problems.push("Bill ID must look like B-1001.");
  if (!customerSelect.value) problems.push("Choose a customer.");
  if (!form.printed_at.value) problems.push("Enter the printed date and time.");
  const items = readItems();
  if (!items.length) problems.push("Add at least one product.");
  if (items.some(item => !item.name || !(Number(item.qty) >= 1) || item.amount === "" || Number(item.amount) < 0)) problems.push("Every product needs a name, a quantity of 1 or more, and an amount.");
  if (totalInput.value === "" || Number(totalInput.value) < 0) problems.push("Enter the total amount.");
  return problems;
}

imageInput.addEventListener("change", () => { if (imageInput.files[0]) runOcr(imageInput.files[0]); });

["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", (event) => { const file = event.dataTransfer.files[0]; if (file) runOcr(file); });

form.addEventListener("input", (event) => {
  if (event.target.closest("#items")) return;
  event.target.classList.remove("filled", "missing");
  if (event.target === totalInput) updateSum();
});
customerSelect.addEventListener("change", () => customerSelect.classList.remove("filled", "missing"));
document.getElementById("add-item").addEventListener("click", () => addItemRow());
document.getElementById("clear").addEventListener("click", () => { hideAlert(alertBox); resetForm(); });

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAlert(alertBox);
  if (!selectedFile) { showAlert(alertBox, "Upload the bill image first."); return; }
  const problems = validate();
  if (problems.length) { showAlert(alertBox, problems.join(" ")); return; }
  const billId = form.bill_id.value.trim().toUpperCase();
  const body = new FormData();
  body.append("bill_id", billId);
  body.append("customer", customerSelect.value);
  body.append("printed_at", form.printed_at.value);
  body.append("total_amount", totalInput.value);
  body.append("products", JSON.stringify(readItems().map(item => ({ name: item.name, qty: Number(item.qty), amount: item.amount }))));
  body.append("ocr_text", fullText);
  body.append("bill_image", selectedFile);
  saveButton.disabled = true;
  saveButton.textContent = "Saving…";
  try {
    const bill = await apiJson("/account/api/bills/", { method: "POST", body });
    resetForm();
    alertBox.className = "alert alert-ok";
    alertBox.replaceChildren(el("span", { text: `Bill ${bill.bill_id} saved. ` }), el("a", { href: `/account/bills/${encodeURIComponent(bill.bill_id)}/`, text: "View bill →" }));
    toast(`Bill ${bill.bill_id} saved.`);
  } catch (error) {
    showAlert(alertBox, error.message);
    saveButton.disabled = false;
  } finally {
    saveButton.textContent = "Save bill";
  }
});

totalInput.addEventListener("input", updateSum);
addItemRow();
const customersReady = loadCustomers();
