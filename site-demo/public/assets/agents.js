// Shows a banner once the publisher has activated agent sales,
// that is once /.well-known/ai-data.json answers with a manifest.
(function () {
  var banner = document.getElementById("agent-banner");
  if (!banner) return;
  fetch("/.well-known/ai-data.json", { cache: "no-store" })
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (manifest) {
      if (!manifest || !manifest.payment) return;
      var payTo = String(manifest.payment.pay_to || "");
      var shortPayTo = payTo.length > 12 ? payTo.slice(0, 6) + "..." + payTo.slice(-4) : payTo;
      banner.textContent = "";
      var strong = document.createElement("strong");
      strong.textContent = "Now selling data to AI agents. ";
      banner.appendChild(strong);
      banner.appendChild(document.createTextNode(
        "Paid in " + (manifest.payment.asset || "USDC") + " with " + (manifest.payment.protocol || "x402") +
        (shortPayTo ? ", to " + shortPayTo : "") + ". Manifest: "
      ));
      var code = document.createElement("code");
      code.textContent = "/.well-known/ai-data.json";
      banner.appendChild(code);
      banner.hidden = false;
    })
    .catch(function () {});
})();
