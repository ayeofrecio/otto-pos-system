(function () {
    const btn = document.getElementById("cloudBtn");
    if (!btn) return;
    const status = btn.querySelector(".menu-item__status");
    const STATES = ["is-loading", "is-success", "is-error"];

    function setState(state, text) {
        btn.classList.remove(...STATES);
        if (state) btn.classList.add("is-" + state);
        if (status) status.textContent = text || "";
    }

    btn.addEventListener("click", () => {
        if (btn.getAttribute("aria-disabled") === "true") return;
        btn.setAttribute("aria-disabled", "true");
        setState("loading", "Syncing…");

        setTimeout(() => {
            const ok = Math.random() > 0.5;
            setState(ok ? "success" : "error", ok ? "Up to date" : "Failed");

            setTimeout(() => {
                setState(null, "");
                btn.removeAttribute("aria-disabled");
            }, 2500);
        }, 2000);
    });
})();