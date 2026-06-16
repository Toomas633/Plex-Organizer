/**
 * Plex Organizer docs — client-side interactions
 * Single-page tabbed layout; navigation is driven by the URL hash.
 */

function toggleMenu() {
  document.getElementById("header").classList.toggle("nav-open");
}

document.addEventListener("click", function (e) {
  const header = document.getElementById("header");
  const nav = document.getElementById("nav-main");
  const btn = document.getElementById("menu-btn");
  if (
    header &&
    header.classList.contains("nav-open") &&
    nav &&
    !nav.contains(e.target) &&
    btn &&
    e.target !== btn &&
    !btn.contains(e.target)
  ) {
    header.classList.remove("nav-open");
  }
});

function toggleTheme() {
  const root = document.documentElement;
  root.classList.add("theme-transitioning");
  const next = root.dataset.theme === "light" ? "dark" : "light";
  root.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch (e) {
    console.warn("Could not persist theme preference:", e);
  }
  setTimeout(function () {
    root.classList.remove("theme-transitioning");
  }, 260);
}

globalThis.addEventListener("resize", function () {
  if (globalThis.innerWidth > 800) {
    const header = document.getElementById("header");
    if (header) header.classList.remove("nav-open");
  }
});

function showTab(name) {
  const panels = document.querySelectorAll(".tab-panel");
  let found = false;
  panels.forEach(function (p) {
    const on = p.id === name;
    p.classList.toggle("active", on);
    if (on) found = true;
  });
  if (!found) {
    const home = document.getElementById("home");
    if (home) home.classList.add("active");
    name = "home";
  }
  document.querySelectorAll(".nav-main a[data-tab]").forEach(function (a) {
    const active = a.dataset.tab === name;
    a.classList.toggle("active", active);
    a.setAttribute("aria-selected", active ? "true" : "false");
  });
  return name;
}

function routeTab() {
  const hash = (location.hash || "").replace(/^#/, "");
  const header = document.getElementById("header");
  if (header) header.classList.remove("nav-open");

  if (!hash) {
    showTab("home");
    globalThis.scrollTo(0, 0);
    return;
  }

  const el = document.getElementById(hash);
  if (el?.classList.contains("tab-panel")) {
    showTab(hash);
    globalThis.scrollTo(0, 0);
  } else if (el) {
    const panel = el.closest(".tab-panel");
    showTab(panel ? panel.id : "home");
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    showTab("home");
    globalThis.scrollTo(0, 0);
  }
}

globalThis.addEventListener("hashchange", routeTab);
document.addEventListener("DOMContentLoaded", routeTab);
