(function () {
  var cookieLifetimeSeconds = 365 * 24 * 60 * 60;

  function saveLanguagePreference(event) {
    if (event.defaultPrevented) return;

    var language = event.currentTarget.getAttribute("hreflang");
    if (language !== "es" && language !== "en") return;

    try {
      document.cookie = "site_lang=" + language +
        "; Path=/; Max-Age=" + cookieLifetimeSeconds +
        "; SameSite=Lax; Secure";
    } catch (error) {
      // Keep ordinary navigation working when cookie access is blocked.
    }
  }

  document.querySelectorAll(".language-switch a[hreflang]").forEach(function (link) {
    link.addEventListener("click", saveLanguagePreference);
  });
})();
