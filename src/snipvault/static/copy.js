// Copy button: plain JavaScript, no framework. Falls back to a selection copy.
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-copy-target]");
  if (!btn) return;
  var el = document.getElementById(btn.getAttribute("data-copy-target"));
  if (!el) return;
  var text = el.textContent;
  var done = function () {
    var old = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(function () { btn.textContent = old; }, 1500);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done);
  } else {
    var ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (e) {}
    document.body.removeChild(ta);
  }
});
