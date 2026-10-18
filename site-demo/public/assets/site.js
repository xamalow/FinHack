// Purchase buttons are not wired to a checkout in this demo.
(function () {
  var toast = document.querySelector(".toast");
  var timer;
  document.addEventListener("click", function (event) {
    var button = event.target.closest(".js-buy");
    if (!button || !toast) return;
    toast.textContent = "Online checkout is not available in this demo. Contact research@velstrand.example to buy a licence.";
    toast.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(function () { toast.hidden = true; }, 3500);
  });
})();
