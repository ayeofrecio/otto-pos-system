(() => {
    const KEY = "pos-theme";
    const root = document.documentElement;
    const btn = document.getElementById("themeToggle");
    if (!btn) return;

    const sync = () => {
        const dark = root.dataset.theme === "dark";
        const state = btn.querySelector("[data-theme-state]");
        
        if (!btn.children.length) btn.textContent = dark ? "☾" : "☀";
        if (state) state.textContent = dark ? "On" : "Off";

        const attr = btn.getAttribute("role") === "menuitemcheckbox"
            ? "aria-checked" : "aria-pressed";
        btn.setAttribute(attr, dark);
    };

    const apply = (theme) => {
        if (theme === "dark") root.dataset.theme = "dark";
        else delete root.dataset.theme;
        sync();
    };

    btn.addEventListener("click", () => {
        const next = root.dataset.theme === "dark" ? "light" : "dark";
        try { localStorage.setItem(KEY, next); } catch (e) { }
        apply(next);
    });

    // keep other open tabs (e.g. login vs cashier) in sync
    window.addEventListener("storage", (e) => {
        if (e.key === KEY) apply(e.newValue);
    });

    sync();
})();