(function () {
  "use strict";

  var statusEl = document.getElementById("status");
  var appUrl = "/glance/?v=0.8.11";

  fetch(appUrl, { cache: "no-store", credentials: "include" })
    .then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      statusEl.textContent = "The Glance service is responding.";
    })
    .catch(function (error) {
      statusEl.textContent =
        "The Glance service did not answer (" + error.message + "). " +
        "Check glance-system.service and its logs.";
    });
}());
