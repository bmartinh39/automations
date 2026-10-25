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

function show(i) {
  tabs.forEach(function (t, k) {
    var on = k === i;

    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;

    var p = document.getElementById(t.getAttribute("aria-controls"));

    p.classList.toggle("on", on);
    p.hidden = !on;
  });
}

tabs.forEach(function (t, i) {
  t.addEventListener("click", function () {
    show(i);
  });

  t.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") {
      show((i + 1) % tabs.length);
      tabs[(i + 1) % tabs.length].focus();
    }

    if (e.key === "ArrowLeft") {
      var j = (i + tabs.length - 1) % tabs.length;

      show(j);
      tabs[j].focus();
    }
  });
});
