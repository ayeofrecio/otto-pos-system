/* Close Transaction (Z-read) modal helpers.
   Uses CSRF_TOKEN, defined in the inline config block of cashier.html. */

async function printXReading() {
    const btn = document.getElementById("print-x-reading-btn");
    btn.disabled = true;
    try {
        const r = await fetch(btn.dataset.url, {
            method: "GET",
            headers: { "X-CSRFToken": CSRF_TOKEN },
        });
        const d = await r.json();
        alert(d.message || d.error);
    } catch (e) {
        alert("Could not print the X-Reading. Please try again.");
    } finally {
        btn.disabled = false;
    }
}

function showZReadConfirm() {
    document.getElementById("close-trans-footer-default").style.display = "none";
    document.getElementById("close-trans-confirm-strip").style.display = "block";
}

function hideZReadConfirm() {
    document.getElementById("close-trans-confirm-strip").style.display = "none";
    document.getElementById("close-trans-footer-default").style.display = "flex";
}