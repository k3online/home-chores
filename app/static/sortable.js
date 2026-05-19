(function () {
  function cellValue(row, index) {
    var cell = row.cells[index];
    if (!cell) {
      return "";
    }
    return (cell.getAttribute("data-sort") || cell.textContent || "").trim();
  }

  function parseValue(value) {
    var normalized = value.replace(/[$,\s]/g, "");
    if (/^-?\d+(\.\d+)?$/.test(normalized)) {
      return Number(normalized);
    }
    var time = Date.parse(value);
    if (!Number.isNaN(time)) {
      return time;
    }
    return value.toLowerCase();
  }

  function compareValues(left, right, direction) {
    var a = parseValue(left);
    var b = parseValue(right);
    if (a < b) {
      return direction === "asc" ? -1 : 1;
    }
    if (a > b) {
      return direction === "asc" ? 1 : -1;
    }
    return 0;
  }

  function clearSortState(table) {
    Array.prototype.forEach.call(table.querySelectorAll("th[data-sortable]"), function (th) {
      th.removeAttribute("aria-sort");
    });
  }

  function sortTable(table, index, direction) {
    var tbody = table.tBodies[0];
    var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
    rows.sort(function (left, right) {
      return compareValues(cellValue(left, index), cellValue(right, index), direction);
    });
    rows.forEach(function (row) {
      tbody.appendChild(row);
    });
  }

  function setupTable(table) {
    Array.prototype.forEach.call(table.querySelectorAll("th[data-sortable]"), function (th, index) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "sort-button";
      button.textContent = th.textContent.trim();
      th.textContent = "";
      th.appendChild(button);

      button.addEventListener("click", function () {
        var current = th.getAttribute("aria-sort");
        var direction = current === "ascending" ? "desc" : "asc";
        clearSortState(table);
        th.setAttribute("aria-sort", direction === "asc" ? "ascending" : "descending");
        sortTable(table, index, direction);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll("table[data-sortable-table]"), setupTable);
  });
})();
