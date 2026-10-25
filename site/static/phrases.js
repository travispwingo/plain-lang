// Filter the phrase reference as you type.
const filter = document.getElementById("filter");
filter.addEventListener("input", () => {
  const words = filter.value.toLowerCase().split(/\s+/).filter(Boolean);
  for (const phrase of document.querySelectorAll(".phrase, .other-ways li")) {
    const text = phrase.textContent.toLowerCase();
    phrase.hidden = !words.every((w) => text.includes(w));
  }
});
