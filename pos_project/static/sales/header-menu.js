(function () {
    const root = document.getElementById("header-menu");
    if (!root) return;
    const trigger = document.getElementById("header-menu-trigger");
    const panel = document.getElementById("header-menu-panel");
    const items = () => Array.from(panel.querySelectorAll('[role="menuitem"]'));
    const isOpen = () => panel.classList.contains("is-open");

    function open(focusFirst) {
        panel.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
        if (focusFirst && items()[0]) items()[0].focus();
    }

    function close(returnFocus) {
        panel.classList.remove("is-open");
        trigger.setAttribute("aria-expanded", "false");
        // POS option: use document.getElementById("barcode-input").focus() here instead.
        if (returnFocus) trigger.focus();
    }

    trigger.addEventListener("click", () => (isOpen() ? close(false) : open(false)));
    trigger.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); open(true); }
    });

    panel.addEventListener("click", (e) => {
        const item = e.target.closest('[role="menuitem"]');
        if (item && !item.hasAttribute("data-keep-open")) close(false);
    });

    panel.addEventListener("keydown", (e) => {
        const list = items();
        const i = list.indexOf(document.activeElement);
        if (e.key === "ArrowDown") { e.preventDefault(); list[(i + 1) % list.length].focus(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); list[(i - 1 + list.length) % list.length].focus(); }
        else if (e.key === "Home") { e.preventDefault(); list[0].focus(); }
        else if (e.key === "End") { e.preventDefault(); list[list.length - 1].focus(); }
        else if (e.key === "Tab") { close(false); }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && isOpen()) { e.stopPropagation(); close(true); }
    }, true);

    document.addEventListener("click", (e) => {
        if (isOpen() && !root.contains(e.target)) close(false);
    });
})();