function initializeTwinChat(details) {
  var frame = details.querySelector("[data-twin-frame]");

  details.addEventListener("toggle", function () {
    if (!details.open || frame.hasAttribute("src")) return;

    frame.src = frame.dataset.src;
    frame.hidden = false;
  });
}

document.querySelectorAll("[data-twin-chat]").forEach(initializeTwinChat);
