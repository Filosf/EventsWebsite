(function () {
  "use strict";

  function setupLanguageEditor() {
    const panels = Array.from(document.querySelectorAll(".language-panel"));
    if (!panels.length) return;

    const labels = document.documentElement.lang === "en"
      ? { ru: "Russian", en: "English", he: "Hebrew" }
      : { ru: "Русский", en: "English", he: "עברית" };
    const tabs = document.createElement("div");
    tabs.className = "language-editor-tabs";
    tabs.setAttribute("role", "tablist");
    panels[0].before(tabs);

    const buttons = new Map();
    for (const language of Object.keys(labels)) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = labels[language];
      button.dataset.language = language;
      button.setAttribute("role", "tab");
      button.addEventListener("click", function () {
        activate(language);
      });
      buttons.set(language, button);
      tabs.appendChild(button);
    }

    function enabledLanguages() {
      return Array.from(document.querySelectorAll('input[name="enabled_languages"]:checked')).map(function (input) {
        return input.value;
      });
    }

    function activate(language) {
      for (const panel of panels) {
        const active = panel.classList.contains("language-" + language);
        panel.classList.toggle("is-active", active);
      }
      for (const [code, button] of buttons) {
        const active = code === language;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      }
      const previewButton = document.querySelector('[data-preview-language="' + language + '"]');
      if (previewButton) previewButton.click();
    }

    function syncTabs(preferredLanguage) {
      const enabled = enabledLanguages();
      for (const [language, button] of buttons) {
        button.hidden = !enabled.includes(language);
      }
      document.querySelectorAll("[data-preview-language]").forEach(function (button) {
        button.hidden = !enabled.includes(button.dataset.previewLanguage);
      });
      const current = tabs.querySelector("button.is-active:not([hidden])");
      const next = enabled.includes(preferredLanguage) ? preferredLanguage : enabled[0];
      if (!current && next) activate(next);
      if (!next) panels.forEach(function (panel) { panel.classList.remove("is-active"); });
    }

    document.querySelectorAll('input[name="enabled_languages"]').forEach(function (input) {
      input.addEventListener("change", function () {
        syncTabs(input.checked ? input.value : null);
      });
    });

    const defaultLanguage = document.querySelector("#id_default_language");
    syncTabs(defaultLanguage ? defaultLanguage.value : null);
  }

  function setupCopyLinks() {
    const buttons = Array.from(document.querySelectorAll(".copy-link-button[data-copy-url]"));

    async function copyText(value) {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const input = document.createElement("textarea");
      input.value = value;
      input.setAttribute("readonly", "");
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", async function () {
        const url = new URL(button.dataset.copyUrl, window.location.origin).href;
        try {
          await copyText(url);
          button.classList.add("is-copied");
          button.title = button.dataset.copiedLabel;
          button.setAttribute("aria-label", button.dataset.copiedLabel);
          window.setTimeout(function () {
            button.classList.remove("is-copied");
            button.title = button.dataset.copyLabel;
            button.setAttribute("aria-label", button.dataset.copyLabel);
          }, 1600);
        } catch (error) {
          button.title = url;
        }
      });
    });
  }

  function setupPreview() {
    const frame = document.querySelector("#event-preview-frame");
    const viewport = document.querySelector("#event-preview-viewport");
    const openLink = document.querySelector("#event-preview-open");
    const buttons = Array.from(document.querySelectorAll("[data-preview-url]"));
    if (!frame || !viewport || !buttons.length) return;

    const desktopWidth = 1200;

    function resizePreview() {
      const scale = Math.min(1, viewport.clientWidth / desktopWidth);
      frame.style.width = desktopWidth + "px";
      frame.style.height = Math.ceil(viewport.clientHeight / scale) + "px";
      frame.style.transform = "scale(" + scale + ")";
    }

    resizePreview();
    if (window.ResizeObserver) {
      new ResizeObserver(resizePreview).observe(viewport);
    } else {
      window.addEventListener("resize", resizePreview);
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        frame.src = button.dataset.previewUrl;
        if (openLink) openLink.href = button.dataset.previewUrl;
        buttons.forEach(function (item) {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", active ? "true" : "false");
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupCopyLinks();
    setupPreview();
    setupLanguageEditor();
  });
})();
