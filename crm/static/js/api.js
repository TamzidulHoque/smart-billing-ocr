const Auth = {
  get access() { return sessionStorage.getItem("access"); },
  get refresh() { return sessionStorage.getItem("refresh"); },
  save(tokens) {
    sessionStorage.setItem("access", tokens.access);
    if (tokens.refresh) sessionStorage.setItem("refresh", tokens.refresh);
  },
  clear() {
    sessionStorage.removeItem("access");
    sessionStorage.removeItem("refresh");
  },
};

function goToLogin() {
  Auth.clear();
  const next = encodeURIComponent(location.pathname + location.search);
  location.href = `/account/login/?next=${next}`;
}

function requireLogin() {
  if (!Auth.access) goToLogin();
}

async function refreshAccess() {
  if (!Auth.refresh) return false;
  const response = await fetch("/account/api/token/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: Auth.refresh }),
  });
  if (!response.ok) return false;
  Auth.save(await response.json());
  return true;
}

async function apiFetch(path, options = {}, retried = false) {
  const headers = new Headers(options.headers || {});
  if (Auth.access) headers.set("Authorization", `Bearer ${Auth.access}`);
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    options = { ...options, body: JSON.stringify(options.json) };
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && !retried) {
    if (await refreshAccess()) return apiFetch(path, options, true);
    goToLogin();
    throw new Error("Session expired. Please log in again.");
  }
  return response;
}

async function apiJson(path, options = {}) {
  const response = await apiFetch(path, options);
  let data = null;
  try { data = await response.json(); } catch (e) { data = null; }
  if (!response.ok) {
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function errorMessage(data, status) {
  if (!data) return `Request failed (${status}).`;
  if (typeof data.detail === "string") return data.detail;
  const parts = [];
  for (const [key, value] of Object.entries(data)) {
    const text = Array.isArray(value) ? value.map(v => (typeof v === "string" ? v : JSON.stringify(v))).join(" ") : (typeof value === "string" ? value : JSON.stringify(value));
    parts.push(key === "non_field_errors" ? text : `${key.replaceAll("_", " ")}: ${text}`);
  }
  return parts.join(" • ") || `Request failed (${status}).`;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function money(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `Tk ${number.toFixed(2)}` : "-";
}

function printedText(value) {
  return value ? String(value).slice(0, 16).replace("T", " ") : "-";
}

function showAlert(box, message, kind = "bad") {
  box.className = `alert alert-${kind}`;
  box.textContent = message;
}

function hideAlert(box) {
  box.className = "alert hidden";
  box.textContent = "";
}

function toast(message) {
  let node = document.getElementById("toast");
  if (!node) {
    node = el("div", { id: "toast", class: "toast" });
    document.body.append(node);
  }
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.remove("show"), 2800);
}

function renderPager(container, data, page, onPage) {
  container.replaceChildren();
  const pageSize = data.pageSize;
  const totalPages = Math.max(1, Math.ceil(data.count / pageSize));
  container.append(
    el("span", { text: `${data.count} result${data.count === 1 ? "" : "s"} · Page ${page} of ${totalPages}` }),
    el("div", { class: "btns" },
      el("button", { class: "btn btn-light", type: "button", disabled: !data.previous, onclick: () => onPage(page - 1), text: "← Previous" }),
      el("button", { class: "btn btn-light", type: "button", disabled: !data.next, onclick: () => onPage(page + 1), text: "Next →" }),
    ),
  );
}

document.addEventListener("DOMContentLoaded", () => {
  const logout = document.getElementById("logout");
  if (logout) logout.addEventListener("click", () => { Auth.clear(); location.href = "/account/login/"; });
});
