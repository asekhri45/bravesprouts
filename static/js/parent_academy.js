document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("academySearchInput");
    const resultsBox = document.getElementById("academySearchResults");
    const resultsInner = document.getElementById("academySearchResultsInner");

    const items = Array.from(document.querySelectorAll(".academy-searchable"));

    function normalize(text) {
      return (text || "").toLowerCase().trim();
    }

    function closeResults() {
      resultsBox.classList.remove("is-open");
      resultsInner.innerHTML = "";
    }

    function renderResults(query) {
      const cleanQuery = normalize(query);

      if (!cleanQuery) {
        closeResults();
        return;
      }

      const words = cleanQuery.split(/\s+/).filter(Boolean);

      const matches = items
        .map(item => {
          const title = item.dataset.title || "";
          const category = item.dataset.category || "";
          const summary = item.dataset.summary || "";
          const searchableText = normalize(`${title} ${category} ${summary}`);

          let score = 0;

          words.forEach(word => {
            if (normalize(title).includes(word)) score += 5;
            if (normalize(category).includes(word)) score += 2;
            if (normalize(summary).includes(word)) score += 3;
            if (searchableText.includes(word)) score += 1;
          });

          return { item, title, category, summary, score };
        })
        .filter(result => result.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 8);

      resultsBox.classList.add("is-open");

      if (matches.length === 0) {
        resultsInner.innerHTML = `
          <div class="search-empty-state">
            <h3>No results found</h3>
            <p>Try searching for words like school, speaking pressure, whispering, anxiety, or relatives.</p>
          </div>
        `;
        return;
      }

      resultsInner.innerHTML = `
        <div class="search-result-count">
          ${matches.length} result${matches.length === 1 ? "" : "s"} found
        </div>
        ${matches.map(result => `
          <a href="${result.item.href}" class="search-result-item">
            <span class="search-result-category">${result.category}</span>
            <span class="search-result-title">${result.title}</span>
            <span class="search-result-summary">${result.summary}</span>
          </a>
        `).join("")}
      `;
    }

    input.addEventListener("input", function () {
      renderResults(input.value);
    });

    input.addEventListener("focus", function () {
      if (input.value.trim()) {
        renderResults(input.value);
      }
    });

    document.addEventListener("click", function (event) {
      const clickedInsideSearch =
        event.target.closest(".academy-search-area");

      if (!clickedInsideSearch) {
        closeResults();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeResults();
        input.blur();
      }
    });
  });