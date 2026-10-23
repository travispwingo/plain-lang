// Search: filters titles, headings and phrase wordings as you type.
const results = document.getElementById("results");
if (results) {
  const query = new URLSearchParams(location.search).get("q") || "";
  document.getElementById("q").value = query;
  const index = await (await fetch("/search.json")).json();
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const found = [];
  for (const page of index) {
    const hits = [page.title, ...page.headings].filter((text) =>
      words.every((w) => text.toLowerCase().includes(w)));
    if (hits.length) found.push([page, hits]);
  }
  if (!found.length) {
    results.innerHTML = "<li>Nothing matches. Try fewer or different words.</li>";
  }
  for (const [page, hits] of found) {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = page.url;
    link.textContent = page.title;
    li.append(link);
    const more = hits.filter((h) => h !== page.title).slice(0, 4);
    if (more.length) li.append(": " + more.join("; "));
    results.append(li);
  }
}
