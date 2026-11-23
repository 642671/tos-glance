(function () {
  "use strict";

  var HEALTH_URL = "/v2/proxy/glance/?v=0.8.10";
  var frame = document.getElementById("appFrame");
  var loading = document.getElementById("loading");
  var errorPanel = document.getElementById("error");
  var errorDetail = document.getElementById("errorDetail");
  var settled = false;

  function markReady() {
    if (settled) {
      return;
    }
    settled = true;
    loading.hidden = true;
  }

  function showError(detail) {
    if (settled) {
      return;
    }
    settled = true;
    loading.hidden = true;
    errorPanel.hidden = false;
    if (detail) {
      errorDetail.textContent = detail;
    }
  }

  async function waitForHealth() {
    for (var attempt = 0; attempt < 20; attempt += 1) {
      try {
        var response = await fetch(HEALTH_URL, {
          cache: "no-store",
          credentials: "include"
        });
        if (response.ok) {
          markReady();
          return;
        }
      } catch (error) {
        // The platform proxy or local service may still be starting.
      }
      await new Promise(function (resolve) {
        window.setTimeout(resolve, 500);
      });
    }
    showError(
      "The Glance service did not answer its health check. " +
      "Confirm that the application service is running and inspect its diagnostic log."
    );
  }

  frame.addEventListener("load", function () {
    window.setTimeout(markReady, 300);
  }, { once: true });

  window.setTimeout(waitForHealth, 500);
}());
