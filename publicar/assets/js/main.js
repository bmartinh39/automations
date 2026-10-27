/* Edita aquí tus datos de contacto */
var CONTACT = {
  phone: "34600000000",
  email: "borja@borjamartin.com",
  msg: "Hola, me gustaría hablar de cómo simplificar las tareas de mi negocio.",
};

document.querySelectorAll("[data-wa]").forEach(function (a) {
  a.href =
    "https://wa.me/" + CONTACT.phone + "?text=" + encodeURIComponent(CONTACT.msg);
  a.target = "_blank";
  a.rel = "noopener";
});

document.querySelectorAll("[data-mail]").forEach(function (a) {
  a.href =
    "mailto:" +
    CONTACT.email +
    "?subject=" +
    encodeURIComponent("Conversación sobre mi negocio");
});

var tabs = [].slice.call(document.querySelectorAll(".tab"));
var tabList = document.querySelector(".tabs");
var activeSectorIndex = null;
var requestedSectorIndex = null;
var sectorAnimation = null;
var sectorReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// All sector panels remain readable until the tab interface is initialized.
tabs.forEach(function (tab) {
  var panel = document.getElementById(tab.getAttribute("aria-controls"));

  panel.setAttribute("role", "tabpanel");
  panel.setAttribute("aria-labelledby", tab.id);
  panel.tabIndex = 0;
});

function stopSectorAnimation() {
  if (sectorAnimation) {
    sectorAnimation.onfinish = null;
    sectorAnimation.cancel();
    sectorAnimation = null;
  }
}

function displaySector(i) {
  tabs.forEach(function (t, k) {
    var on = k === i;

    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;

    var p = document.getElementById(t.getAttribute("aria-controls"));

    p.hidden = !on;
  });

  activeSectorIndex = i;
}

function show(i, immediate) {
  if (requestedSectorIndex === i && !immediate) return;

  requestedSectorIndex = i;

  var previousPanel = activeSectorIndex === null
    ? null
    : document.getElementById(tabs[activeSectorIndex].getAttribute("aria-controls"));
  var panel = document.getElementById(tabs[i].getAttribute("aria-controls"));
  var previousOpacity = previousPanel
    ? window.getComputedStyle(previousPanel).opacity
    : "1";

  stopSectorAnimation();

  if (
    !previousPanel ||
    immediate ||
    sectorReducedMotion.matches ||
    typeof panel.animate !== "function"
  ) {
    displaySector(i);
    return;
  }

  function fadeIn() {
    displaySector(i);
    sectorAnimation = panel.animate(
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: 800, easing: "ease-out", fill: "both" }
    );
    sectorAnimation.onfinish = stopSectorAnimation;
  }

  // Mantiene el panel actual durante el desvanecido y cambia al llegar a cero.
  sectorAnimation = previousPanel.animate(
    [{ opacity: previousOpacity }, { opacity: 0 }],
    { duration: 140, easing: "ease-in", fill: "both" }
  );
  sectorAnimation.onfinish = function () {
    // Oculta el panel saliente antes de retirar el efecto para evitar parpadeos.
    previousPanel.hidden = true;
    stopSectorAnimation();
    fadeIn();
  };
}

sectorReducedMotion.addEventListener("change", function () {
  if (requestedSectorIndex !== null) {
    show(requestedSectorIndex, true);
  }
});

tabs.forEach(function (t, i) {
  t.addEventListener("click", function () {
    show(i);
  });

  t.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      show((i + 1) % tabs.length);
      tabs[(i + 1) % tabs.length].focus();
    }

    if (e.key === "ArrowLeft") {
      e.preventDefault();
      var j = (i + tabs.length - 1) % tabs.length;

      show(j);
      tabs[j].focus();
    }

    if (e.key === "Home" || e.key === "End") {
      e.preventDefault();

      var index = e.key === "Home" ? 0 : tabs.length - 1;

      show(index);
      tabs[index].focus();
    }
  });
});

if (tabList && tabs.length > 0) {
  show(0);
  tabList.hidden = false;
}

// El menú mantiene los enlaces visibles si JavaScript no está disponible.
var header = document.querySelector(".nav");
var menuToggle = document.querySelector(".menu-toggle");
var navigation = document.getElementById("primary-navigation");
var mobileNavigation = window.matchMedia("(max-width: 900px)");

if (header && menuToggle && navigation) {
  var menuAnimation = null;
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function setMenuOpen(open, animate) {
    if (menuAnimation) {
      menuAnimation.cancel();
      menuAnimation = null;
    }

    var closed = mobileNavigation.matches && !open;
    var wasHidden = navigation.hidden;

    menuToggle.setAttribute("aria-expanded", String(open));
    menuToggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
    // Al cerrar, los enlaces dejan de recibir foco durante la transición.
    navigation.inert = closed;
    navigation.setAttribute("aria-hidden", String(closed));

    if (
      animate === false ||
      !mobileNavigation.matches ||
      reducedMotion.matches ||
      typeof navigation.animate !== "function" ||
      (closed && wasHidden)
    ) {
      navigation.hidden = closed;
      return;
    }

    navigation.hidden = false;

    var frames = [
      { opacity: 0, transform: "translateY(-6px)" },
      { opacity: 1, transform: "translateY(0)" },
    ];

    if (closed) frames.reverse();

    menuAnimation = navigation.animate(frames, {
      duration: 180,
      easing: "ease-out",
    });

    menuAnimation.onfinish = function () {
      navigation.hidden = closed;
      menuAnimation = null;
    };
  }

  function resetNavigation() {
    var focusInNavigation = navigation.contains(document.activeElement);
    var focusOnToggle = document.activeElement === menuToggle;

    setMenuOpen(false, false);

    if (mobileNavigation.matches && focusInNavigation) {
      menuToggle.focus();
    } else if (!mobileNavigation.matches && focusOnToggle) {
      navigation.querySelector("a").focus();
    }
  }

  menuToggle.addEventListener("click", function () {
    setMenuOpen(menuToggle.getAttribute("aria-expanded") !== "true");
  });

  navigation.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      if (!mobileNavigation.matches) return;

      setMenuOpen(false);

      var target = document.querySelector(link.getAttribute("href"));

      if (target) {
        target.tabIndex = -1;
        target.focus({ preventScroll: true });
      }
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && menuToggle.getAttribute("aria-expanded") === "true") {
      setMenuOpen(false);
      menuToggle.focus();
    }
  });

  document.addEventListener("click", function (event) {
    if (menuToggle.getAttribute("aria-expanded") === "true" && !header.contains(event.target)) {
      var focusInNavigation = navigation.contains(document.activeElement);

      setMenuOpen(false);

      if (focusInNavigation) menuToggle.focus();
    }
  });

  // También se cierra al usar la marca o el contacto de la cabecera.
  header.querySelectorAll(".brand, .btn").forEach(function (link) {
    link.addEventListener("click", function () {
      setMenuOpen(false);
    });
  });

  mobileNavigation.addEventListener("change", resetNavigation);
  reducedMotion.addEventListener("change", resetNavigation);
  header.classList.add("menu-ready");
  menuToggle.hidden = false;
  resetNavigation();
}
