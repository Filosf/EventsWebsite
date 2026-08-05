"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const table = document.querySelector("#result_list");
  if (!table) {
    return;
  }

  const labels = Array.from(table.querySelectorAll("thead th"), (header) => {
    const text = header.querySelector(".text");
    return text ? text.textContent.trim().replace(/\s+/g, " ") : "";
  });

  table.querySelectorAll("tbody tr").forEach((row) => {
    Array.from(row.children).forEach((cell, index) => {
      if (labels[index]) {
        cell.dataset.label = labels[index];
      }
    });
  });
});
