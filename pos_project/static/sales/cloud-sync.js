/* Header cloud button: "Update Current Inventory".
   PLACEHOLDER: the result is random. Replace the setTimeout block with a real
   request to the inventory sync endpoint and set success/error from the response. */
(function () {
    const btn = document.getElementById("cloudBtn");
    if (!btn) return;

    btn.addEventListener("click", () => {
        if (btn.disabled) return;

        btn.disabled = true;
        btn.className = "icon-btn loading";

        setTimeout(() => {
            btn.className = Math.random() > 0.5 ? "icon-btn success" : "icon-btn error";

            setTimeout(() => {
                btn.className = "icon-btn";
                btn.disabled = false;
            }, 2000);
        }, 2000);
    });
})();