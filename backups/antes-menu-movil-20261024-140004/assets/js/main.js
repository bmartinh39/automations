/* Edita aquí tus datos de contacto */
var CONTACT = {
  phone: "34600000000",
  email: "tu@correo.com",
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

// All sector panels remain readable until the tab interface is initialized.
tabs.forEach(function (tab) {
  var panel = document.getElementById(tab.getAttribute("aria-controls"));

  panel.setAttribute("role", "tabpanel");
  panel.setAttribute("aria-labelledby", tab.id);
  panel.tabIndex = 0;
});

function show(i) {
  tabs.forEach(function (t, k) {
    var on = k === i;

    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;

    var p = document.getElementById(t.getAttribute("aria-controls"));

    p.hidden = !on;
  });
}

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
