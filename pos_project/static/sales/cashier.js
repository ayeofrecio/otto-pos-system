/**
 * POS Cashier - barcode handling, live time, toast dismiss, item search
 */
// document.addEventListener('keydown', function (evt) {
//   console.log('key:', evt.key, '| code:', evt.code);


(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Best-effort browser maximize for POS usage
  // ---------------------------------------------------------------------------
  function maximizeBrowserWindow() {
    try {
      window.moveTo(0, 0);
      if (window.screen && window.screen.availWidth && window.screen.availHeight) {
        window.resizeTo(window.screen.availWidth, window.screen.availHeight);
      }
    } catch (_) {
      // Some browsers block script-driven window resize/move.
    }
  }
  maximizeBrowserWindow();

  // Tracks whether a fullscreen exit was explicitly requested via F9, so the
  // fullscreenchange listener below can tell that apart from the browser's
  // own automatic exit-on-Escape behavior (which we want to undo).
  let exitingFullscreenViaF9 = false;

  async function toggleFullscreenMode() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        exitingFullscreenViaF9 = true;
        await document.exitFullscreen();
      }
    } catch (_) {
      // Fullscreen may be blocked by browser policy.
      exitingFullscreenViaF9 = false;
    }
  }

  // The Fullscreen API auto-exits fullscreen whenever Escape is pressed,
  // regardless of app-level keydown handling — this can't be prevented with
  // evt.preventDefault(). That means closing a modal (e.g. Search) with
  // Escape while in kiosk fullscreen mode unintentionally un-maximizes the
  // window. Restore fullscreen unless the exit was the deliberate F9 toggle.
  document.addEventListener('fullscreenchange', function () {
    if (!document.fullscreenElement && !exitingFullscreenViaF9) {
      document.documentElement.requestFullscreen().catch(() => {});
    }
    exitingFullscreenViaF9 = false;
  });

  // ---------------------------------------------------------------------------
  // Live time tick
  // ---------------------------------------------------------------------------
  function updateTime() {
    const now = new Date();
    const timeEl = document.getElementById('live-time');
    const dateEl = document.getElementById('live-date');
    if (timeEl) {
      timeEl.textContent = now.toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
      });
    }
    if (dateEl) {
      dateEl.textContent = now.toLocaleDateString('en-US', {
        weekday: 'long', month: 'short', day: 'numeric', year: 'numeric'
      });
    }
  }

  if (document.getElementById('live-time')) {
    setInterval(updateTime, 1000);
  }

  // cashier.js — wire up the cloud button
  const cloudBtn = document.getElementById("cloudBtn");

  if (cloudBtn) {
    cloudBtn.addEventListener("click", async () => {
      setCloudState("loading");

      try {
          const res = await fetch("/pos/update-from-csv/", {
              method: "POST",
              headers: { "X-CSRFToken": getCookie("csrftoken") },
          });

          const text = await res.text();   // 👈 read raw first
          console.log("RAW RESPONSE:", text);

          let data;
          try {
              data = JSON.parse(text);     // 👈 manually parse
          } catch (e) {
              throw new Error("Invalid JSON response");
          }

          if (!res.ok) {
              throw new Error(data.message || "Request failed");
          }

          if (data.status === "ok") {
              setCloudState("success");
              console.log(data);
          } else {
              setCloudState("error");
              console.error(data.message);
          }

      } catch (err) {
          setCloudState("error");
          console.error("Error:", err);
      }
    });
  }

  function setCloudState(state) {
      if (!cloudBtn) {
        return;
      }
      // Matches your icon-download / icon-success / icon-error / icon-loading CSS classes
      const states = ["idle", "loading", "success", "error"];
      const iconMap = {
          idle:    "icon-download",
          loading: "icon-loading",
          success: "icon-success",
          error:   "icon-error",
      };
      cloudBtn.dataset.state = state;
      // Your CSS should show/hide .icon-* based on [data-state] on the button
  }

  function getCookie(name) {
      return document.cookie.split("; ")
          .find(r => r.startsWith(name + "="))
          ?.split("=")[1];
  }
  // ---------------------------------------------------------------------------
  // Dynamic max-height for Items Entered based on bottom bar position
  // ---------------------------------------------------------------------------
  function updateScannedItemsMaxHeight() {
    const inner = document.querySelector('.scanned-items-inner');
    const actionsBar = document.querySelector('.actions');
    if (!inner || !actionsBar) { return; }
    const innerRect = inner.getBoundingClientRect();
    const barRect = actionsBar.getBoundingClientRect();
    const gap = 8;
    const maxH = Math.max(100, barRect.top - innerRect.top - gap);
    inner.style.maxHeight = maxH + 'px';
  }
  function onResizeOrLoad() {
    updateScannedItemsMaxHeight();
  }
  if (document.querySelector('.scanned-items-inner')) {
    onResizeOrLoad();
    window.addEventListener('resize', onResizeOrLoad);
  }
  // Re-run when HTMX updates the page (cart updates swap scanned-items-panel oob)
  var lastRequestWasCartAdd = false;
  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath || '';
    lastRequestWasCartAdd = path.indexOf('/cart/add') !== -1;
  });
  document.body.addEventListener('htmx:afterSettle', function () {
    updateScannedItemsMaxHeight();
    syncSelectedRowAfterRender();
    if (lastRequestWasCartAdd) {
      lastRequestWasCartAdd = false;
      var scannedRows = document.querySelectorAll('.scanned-item[data-rec-ctr]');
      if (scannedRows && scannedRows.length) {
        setSelectedScannedRow(scannedRows[scannedRows.length - 1].getAttribute('data-rec-ctr'));
      }
      const scannedInner = document.querySelector('.scanned-items-inner');
      if (scannedInner) { scannedInner.scrollTop = scannedInner.scrollHeight; }
      const cartList = document.querySelector('.cart-list');
      if (cartList) { cartList.scrollTop = cartList.scrollHeight; }
    }
  });


  // Capture barcode value just before htmx submits (needed for search prefill on not-found)
  var lastScannedBarcode = '';
  var selectedLineRecCtr = '';

  function normalizeRecCtr(value) {
    var n = Number(value);
    if (!Number.isFinite(n) || n <= 0) {
      return '';
    }
    return String(Math.trunc(n));
  }

  function setSelectedScannedRow(recCtr) {
    var normalized = normalizeRecCtr(recCtr);
    selectedLineRecCtr = normalized;

    var rows = document.querySelectorAll('.scanned-item[data-rec-ctr]');
    rows.forEach(function (row) {
      var rowRecCtr = normalizeRecCtr(row.getAttribute('data-rec-ctr'));
      row.classList.toggle('scanned-item-selected', !!normalized && rowRecCtr === normalized);
    });

    var recInput = document.getElementById('line-disc-rec-ctr');
    if (recInput && normalized) {
      recInput.value = normalized;
    }
  }

  function syncSelectedRowAfterRender() {
    var rows = document.querySelectorAll('.scanned-item[data-rec-ctr]');
    if (!rows.length) {
      selectedLineRecCtr = '';
      return;
    }

    if (selectedLineRecCtr) {
      setSelectedScannedRow(selectedLineRecCtr);
      if (document.querySelector('.scanned-item.scanned-item-selected')) {
        return;
      }
    }

    setSelectedScannedRow(rows[rows.length - 1].getAttribute('data-rec-ctr'));
  }

  // ---------------------------------------------------------------------------
  // Move selection up/down through scanned items (Arrow keys from barcode input)
  // ---------------------------------------------------------------------------
  function moveItemSelection(delta) {
    var rows = document.querySelectorAll('.scanned-item[data-rec-ctr]');
    if (!rows.length) { return; }

    var currentIndex = -1;
    if (selectedLineRecCtr) {
      for (var i = 0; i < rows.length; i++) {
        if (normalizeRecCtr(rows[i].getAttribute('data-rec-ctr')) === selectedLineRecCtr) {
          currentIndex = i;
          break;
        }
      }
    }

    var nextIndex;
    if (currentIndex < 0) {
      nextIndex = delta > 0 ? 0 : rows.length - 1;
    } else {
      nextIndex = (currentIndex + delta + rows.length) % rows.length;
    }

    var nextRecCtr = normalizeRecCtr(rows[nextIndex].getAttribute('data-rec-ctr'));
    setSelectedScannedRow(nextRecCtr);
    rows[nextIndex].scrollIntoView({ block: 'nearest' });
  }

  const barcodeFormEl = document.getElementById('barcode-form');
  if (barcodeFormEl) {
    barcodeFormEl.addEventListener('submit', function () {
      const inp = document.getElementById('barcode-input');
      lastScannedBarcode = inp ? inp.value.trim() : '';
    });
  }

  // ---------------------------------------------------------------------------
  // Denomination Modal
  // ---------------------------------------------------------------------------

  window.openDenominationModal = function () {
    const modal = document.getElementById("denom-modal");
    if (modal) modal.classList.add("open");
  };

  window.closeDenominationModal = function () {
    const modal = document.getElementById("denom-modal");
    if (modal) modal.classList.remove("open");
  };

  window.closeDenominationModalOutside = function (e) {
    if (e.target === document.getElementById("denom-modal")) {
      window.closeDenominationModal();
    }
  };

  window.applyDenominationTotal = function () {

    const total = document.getElementById("denom-total-display").dataset.total || 0;

    const cashInput = document.getElementById("closing-cash-input");

    if (cashInput) {
      cashInput.value = parseFloat(total).toFixed(2);
      cashInput.dispatchEvent(new Event("input", { bubbles: true }));
      cashInput.focus();
    }

    window.closeDenominationModal();
  };

  // ---------------------------------------------------------------------------
  // Toast auto-dismiss + open search on item-not-found
  // ---------------------------------------------------------------------------
  document.body.addEventListener('htmx:afterSwap', function (evt) {
    if (evt.detail.target.id !== 'toast-container') { return; }
    const container = evt.detail.target;
    if (!container.innerHTML) { return; }
    // Auto-dismiss toast after 2 s
    setTimeout(function () { container.innerHTML = ''; }, 2000);
    // If item not found, open search modal prefilled with what was scanned
    if (container.querySelector('[data-open-search]')) {
      setTimeout(function () {
        window.openSearchModal(lastScannedBarcode || '');
      }, 120);
    }
  });

  // After cart_add: clear barcode, reset qty to 1, reset item discount, refocus
  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath;
    if (!path) { return; }
    const barcodeInput = document.getElementById('barcode-input');
    const qtyInput = document.getElementById('qty-input');
    if (barcodeInput && path.includes('/cart/add')) {
      // Keep entered qty when barcode is not found and search modal is requested.
      const responseText = (evt.detail.xhr && evt.detail.xhr.responseText) || '';
      const isNotFoundFlow = responseText.indexOf('data-open-search') !== -1;
      barcodeInput.value = '';
      if (qtyInput && !isNotFoundFlow) { qtyInput.value = '1'; }
      // Item discount is one-shot — reset after each scan
      window.clearDiscount();
      barcodeInput.focus();
    } else if (barcodeInput && path.includes('/cart/')) {
      barcodeInput.focus();
    }
  });

  // F2 → focus qty input; F3 → open discount modal
  // * in empty barcode field → focus qty input
  document.addEventListener('keydown', function (evt) {
    const barcodeInput = document.getElementById('barcode-input');
    const qtyInput = document.getElementById('qty-input');
    const suspendHotkey = (typeof POS_FKEYS !== 'undefined' && POS_FKEYS.iSusRt) ? POS_FKEYS.iSusRt : 'F3';
    const searchHotkey = (typeof POS_FKEYS !== 'undefined' && POS_FKEYS.iView) ? POS_FKEYS.iView : 'F1';
    const qtyHotkey = (typeof POS_FKEYS !== 'undefined' && POS_FKEYS.iQty) ? POS_FKEYS.iQty : 'F2';

    // Block browser defaults for ALL keys that are mapped to POS functions
    if (typeof POS_FKEYS !== 'undefined') {
      const mappedKeys = Object.values(POS_FKEYS);
      if (mappedKeys.includes(evt.key)) {
        evt.preventDefault();
      }
    }

    // F9 toggles browser fullscreen for kiosk-like POS mode.
    if (evt.key === 'F9') {
      evt.preventDefault();
      toggleFullscreenMode();
      return;
    }

    // Block browser defaults for ALL keys that are mapped to POS functions
    if (typeof POS_FKEYS !== 'undefined') {
      const mappedKeys = Object.values(POS_FKEYS);
      if (mappedKeys.includes(evt.key)) {
        evt.preventDefault();
      }
    }

    // F9 toggles browser fullscreen for kiosk-like POS mode.
    if (evt.key === 'F9') {
      evt.preventDefault();
      toggleFullscreenMode();
      return;
    }

    if (evt.key === searchHotkey) {
      evt.preventDefault();
      window.openSearchModal();
      return;
    }

    if (evt.key === qtyHotkey) {
      evt.preventDefault();
      if (qtyInput) { qtyInput.focus(); qtyInput.select(); }
      return;
    }

    if (evt.key === POS_FKEYS.iDisc) {
      evt.preventDefault();
      var selectedForDisc = getSelectedRecCtr();
      if (selectedForDisc) {
        window.openLineDiscModal(selectedForDisc);
      } else {
        window.openDiscountModal();
      }
      return;
    }

    if (evt.key === POS_FKEYS.stDisc) {
      evt.preventDefault();
      window.openTransDiscModal();
      return;
    }

    if (evt.key === POS_FKEYS.prOver) {
      evt.preventDefault();
      window.triggerPriceOverride();
      return;
    }

    if (evt.key === POS_FKEYS.iRet) {
      evt.preventDefault();
      window.triggerItemReturn();
      return;
    }
    if (evt.key === suspendHotkey) {
      evt.preventDefault();
      window.openSuspendModal();
      return;
    }

    if (evt.key === POS_FKEYS.paymnt) {
      evt.preventDefault();
      window.openPayModal();
      return;
    }

    if (POS_FKEYS.menu && POS_FKEYS.menu !== suspendHotkey && evt.key === POS_FKEYS.menu) {
//     if (evt.key === POS_FKEYS.menu) {
      evt.preventDefault();
      window.openFkeyHelpModal();
      return;
    }

    if (evt.key === POS_FKEYS.iVoid) {
      evt.preventDefault();
      window.triggerVoidItem();
      return;
    }

    if (evt.key === POS_FKEYS.iVoidA) {
      evt.preventDefault();
      window.triggerVoidTransaction();
      return;
    }

    if (evt.key === POS_FKEYS.voidTr) {
      evt.preventDefault();
      window.triggerVoidPrevious();
      return;
    }

    if (POS_FKEYS.cWithD && evt.key === POS_FKEYS.cWithD) {
      evt.preventDefault();
      window.openCashInOutModal('OUT');
      return;
    }

    if (evt.key === '*' && qtyInput && document.activeElement === barcodeInput && !barcodeInput.value) {
      evt.preventDefault();
      qtyInput.focus();
      qtyInput.select();
      return;
    }

    if (evt.key === 'Escape') {
      const payModal = document.getElementById('pay-modal');
      const discModal = document.getElementById('discount-modal');
      const tdModal = document.getElementById('trans-disc-modal');
      const poModal = document.getElementById('price-override-modal');
      const fkeyModal = document.getElementById('fkey-help-modal');
      const itemReturnModal = document.getElementById('item-return-modal');
      const suspendModal = document.getElementById('suspend-modal');
      const cashInOutModal = document.getElementById('cash-inout-modal');
      if (payModal && payModal.classList.contains('open')) { window.closePayModal(); }
      else if (discModal && discModal.classList.contains('open')) { window.closeDiscountModal(); }
      else if (tdModal && tdModal.classList.contains('open')) { window.closeTransDiscModal(); }
      else if (poModal && poModal.classList.contains('open')) { window.closePriceOverrideModal(); }
      else if (itemReturnModal && itemReturnModal.classList.contains('open')) { window.closeItemReturnModal(); }
      else if (suspendModal && suspendModal.classList.contains('open')) { window.closeSuspendModal(); }
      else if (cashInOutModal && cashInOutModal.classList.contains('open')) { window.closeCashInOutModal(); }
      else if (fkeyModal && fkeyModal.classList.contains('open')) { window.closeFkeyHelpModal(); }
      else if (closeTransModal && closeTransModal.classList.contains('open')) { window.closeCloseTransModal(); }
    }
  });

  // After editing qty, pressing Enter moves focus to barcode input
  const qtyInputEl = document.getElementById('qty-input');
  if (qtyInputEl) {
    qtyInputEl.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        const barcodeInput = document.getElementById('barcode-input');
        if (barcodeInput) { barcodeInput.focus(); }
      }
    });
  }

  // Pressing Enter in the barcode field runs the enterKey() logic.
  // (Required because adding the qty number input means the browser no longer
  // auto-submits a multi-input form on Enter.)
  const barcodeInputEl = document.getElementById('barcode-input');
  if (barcodeInputEl) {
    barcodeInputEl.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        enterKey();
      } else if (evt.key === 'ArrowUp') {
        evt.preventDefault();
        moveItemSelection(-1);
      } else if (evt.key === 'ArrowDown') {
        evt.preventDefault();
        moveItemSelection(1);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // enterKey — intercepts Enter on the barcode field
  // Logic ported from Clarion:
  //   len <= 11 + is_alias  → open color/size picker
  //   len == 12             → backend parses embedded color/size, submit normally
  //   otherwise             → submit normally
  // ---------------------------------------------------------------------------
  function enterKey() {
    var barcodeInput = document.getElementById('barcode-input');
    if (!barcodeInput) { return; }
    var barcode = barcodeInput.value.trim();
    if (!barcode) { return; }

    if (barcode.length <= 11) {
      // Ask the server whether this icode is an alias item with variants
      fetch('/sales/cart/variants/?barcode=' + encodeURIComponent(barcode))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok && data.is_alias && data.variants && data.variants.length > 0) {
            openColorSizeModal(barcode, data.item_desc, data.variants);
          } else {
            submitBarcodeForm();
          }
        })
        .catch(function () {
          submitBarcodeForm();
        });
    } else {
      // 12-char (or longer) barcode — let the backend handle it
      submitBarcodeForm();
    }
  }

  function submitBarcodeForm() {
    var form = document.getElementById('barcode-form');
    if (form) {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    }
  }

  // ---------------------------------------------------------------------------
  // Color / Size Picker Modal (shown for alias items)
  // ---------------------------------------------------------------------------
  window.openColorSizeModal = function (icode, itemDesc, variants) {
    var modal = document.getElementById('color-size-modal');
    var titleEl = document.getElementById('color-size-modal-title');
    var grid = document.getElementById('color-size-variant-grid');
    if (!modal || !grid) { return; }
    if (titleEl) { titleEl.textContent = itemDesc || icode; }
    grid.innerHTML = '';
    variants.forEach(function (v) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'variant-btn';
      btn.innerHTML =
        '<span class="variant-color">' + (v.color_desc || v.color_code || '\u2014') + '</span>' +
        '<span class="variant-size">' + (v.size_desc  || v.size_code  || '\u2014') + '</span>' +
        '<span class="variant-price">\u20B1' + parseFloat(v.price).toFixed(2) + '</span>';
      btn.addEventListener('click', function () { selectVariant(v.barcode); });
      grid.appendChild(btn);
    });
    modal.classList.add('open');
  };

  window.closeColorSizeModal = function () {
    var modal = document.getElementById('color-size-modal');
    if (modal) { modal.classList.remove('open'); }
    var barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeColorSizeModalOutside = function (evt) {
    if (evt.target === document.getElementById('color-size-modal')) {
      window.closeColorSizeModal();
    }
  };

  function selectVariant(variantBarcode) {
    var barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.value = variantBarcode; }
    window.closeColorSizeModal();
    submitBarcodeForm();
  }


  var pendingDisc = { pct: 0, type: '', label: '' };

  window.openDiscountModal = function () {
    const modal = document.getElementById('discount-modal');
    const input = document.getElementById('disc-pct-modal-input');
    if (!modal) { return; }
    modal.classList.add('open');
    // Pre-fill with current pending discount
    if (input) {
      input.value = pendingDisc.pct || 0;
      pendingDisc.pct = normalizeDiscountPctInput(input);
    }
    refreshDiscTypeBtns(pendingDisc.type);
    setTimeout(function () {
      if (pendingDisc.type === 'REG' || !pendingDisc.type) {
        if (input) { input.focus(); input.select(); }
      }
    }, 80);
  };

  window.closeDiscountModal = function () {
    const modal = document.getElementById('discount-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeDiscountModalOutside = function (evt) {
    if (evt.target === document.getElementById('discount-modal')) {
      window.closeDiscountModal();
    }
  };

  window.selectDiscType = function (btn, code, label, defaultPct) {
    pendingDisc.type = code;
    pendingDisc.label = label;
    refreshDiscTypeBtns(code);
    const input = document.getElementById('disc-pct-modal-input');
    if (input) {
      if (defaultPct > 0) { input.value = defaultPct; }
      pendingDisc.pct = normalizeDiscountPctInput(input);
      input.focus();
      input.select();
    }
  };

  function refreshDiscTypeBtns(selectedCode) {
    document.querySelectorAll('.disc-type-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-disc-code') === selectedCode);
    });
  }

  window.applyDiscount = function () {
    const input = document.getElementById('disc-pct-modal-input');
    const pct = normalizeDiscountPctInput(input);
    if (pct <= 0) {
      window.removeDiscountAndClose();
      return;
    }
    pendingDisc.pct = pct;
    if (!pendingDisc.type) {
      pendingDisc.type = 'REG';
      pendingDisc.label = 'Regular';
    }
    syncDiscFields();
    window.closeDiscountModal();
  };

  window.removeDiscountAndClose = function () {
    window.clearDiscount();
    window.closeDiscountModal();
  };

  window.clearDiscount = function () {
    pendingDisc = { pct: 0, type: '', label: '' };
    syncDiscFields();
  };

  function syncDiscFields() {
    const badge = document.getElementById('disc-badge');
    const badgeText = document.getElementById('disc-badge-text');
    const pctField = document.getElementById('disc-pct-field');
    const typeField = document.getElementById('disc-type-field');
    if (pctField) { pctField.value = pendingDisc.pct; }
    if (typeField) { typeField.value = pendingDisc.type; }
    if (badge) {
      if (pendingDisc.pct > 0) {
        badge.classList.add('visible');
        if (badgeText) {
          badgeText.textContent = pendingDisc.pct + '% — ' + (pendingDisc.label || pendingDisc.type);
        }
      } else {
        badge.classList.remove('visible');
      }
    }
  }

  // Allow Enter in the discount % field to immediately apply
  const discPctInput = document.getElementById('disc-pct-modal-input');
  if (discPctInput) {
    ['input', 'change', 'blur'].forEach(function (evtName) {
      discPctInput.addEventListener(evtName, function () {
        pendingDisc.pct = normalizeDiscountPctInput(discPctInput);
      });
    });
    discPctInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') { evt.preventDefault(); window.applyDiscount(); }
    });
  }

  // ---------------------------------------------------------------------------
  // Line Discount Modal (click row in Items Entered)
  // ---------------------------------------------------------------------------
  function normalizeDiscountPctInput(inputEl) {
    if (!inputEl) { return 0; }
    const raw = parseFloat(inputEl.value);
    if (!Number.isFinite(raw)) {
      inputEl.value = '0';
      return 0;
    }
    const clamped = Math.max(0, Math.min(100, raw));
    const normalized = Math.trunc(clamped);
    inputEl.value = String(normalized);
    return normalized;
  }

  var lineDiscRecCtr = null;
  var lineDiscType = '';

  window.openLineDiscModal = function (recCtr) {
    lineDiscRecCtr = normalizeRecCtr(recCtr) || recCtr;
    lineDiscType = 'REG';
    const modal = document.getElementById('line-disc-modal');
    const recInput = document.getElementById('line-disc-rec-ctr');
    const pctInput = document.getElementById('line-disc-pct-input');
    const typeInput = document.getElementById('line-disc-type');
    if (!modal || !recInput) { return; }
    recInput.value = lineDiscRecCtr;
    typeInput.value = 'REG';
    pctInput.value = 0;
    normalizeDiscountPctInput(pctInput);
    setSelectedScannedRow(lineDiscRecCtr);
    refreshLineDiscTypeBtns('REG');
    modal.classList.add('open');
    setTimeout(function () { if (pctInput) { pctInput.focus(); pctInput.select(); } }, 80);
  };

  window.closeLineDiscModal = function () {
    const modal = document.getElementById('line-disc-modal');
    if (modal) { modal.classList.remove('open'); }
    lineDiscRecCtr = null;
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeLineDiscModalOutside = function (evt) {
    if (evt.target === document.getElementById('line-disc-modal')) {
      window.closeLineDiscModal();
    }
  };

  window.voidSelectedLineItem = function () {
    const recInput = document.getElementById('line-disc-rec-ctr');
    const recCtr = lineDiscRecCtr || (recInput && recInput.value);
    if (!recCtr) {
      alert('No item selected to void.');
      return;
    }
    if (!confirm('Void this item?')) {
      return;
    }

    postFormEncoded(CART_VOID_ITEM_URL, { rec_ctr: recCtr })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          alert(res.data.error || 'Failed to void item.');
          return;
        }
        window.closeLineDiscModal();
        window.location.reload();
      })
      .catch(function () {
        alert('Failed to void item.');
      });
  };

  window.selectLineDiscType = function (btn, code, label, defaultPct) {
    lineDiscType = code;
    refreshLineDiscTypeBtns(code);
    const typeInput = document.getElementById('line-disc-type');
    const pctInput = document.getElementById('line-disc-pct-input');
    if (typeInput) { typeInput.value = code; }
    if (pctInput) {
      if (defaultPct > 0) { pctInput.value = defaultPct; }
      pctInput.focus();
      pctInput.select();
    }
  };

  function refreshLineDiscTypeBtns(selectedCode) {
    document.querySelectorAll('.line-disc-type-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-code') === selectedCode);
    });
  }

  window.applyLineDisc = function () {
    const pctInput = document.getElementById('line-disc-pct-input');
    const pct = normalizeDiscountPctInput(pctInput);
    if (pct <= 0) {
      window.removeLineDiscAndClose();
      return;
    }
    const form = document.getElementById('line-disc-form');
    if (form) {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    }
    window.closeLineDiscModal();
  };

  window.removeLineDiscAndClose = function () {
    const pctInput = document.getElementById('line-disc-pct-input');
    const typeInput = document.getElementById('line-disc-type');
    if (pctInput) { pctInput.value = 0; }
    if (typeInput) { typeInput.value = ''; }
    const form = document.getElementById('line-disc-form');
    if (form) {
      const recInput = document.getElementById('line-disc-rec-ctr');
      if (recInput && recInput.value) {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }
    }
    window.closeLineDiscModal();
  };

  const lineDiscPctInput = document.getElementById('line-disc-pct-input');
  if (lineDiscPctInput) {
    ['input', 'change', 'blur'].forEach(function (evtName) {
      lineDiscPctInput.addEventListener(evtName, function () {
        normalizeDiscountPctInput(lineDiscPctInput);
      });
    });
    lineDiscPctInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') { evt.preventDefault(); window.applyLineDisc(); }
    });
  }

  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath || '';
    if (path.indexOf('/cart/line-disc') !== -1) {
      const barcodeInput = document.getElementById('barcode-input');
      if (barcodeInput) { barcodeInput.focus(); }
    }
  });

  window.openPriceOverrideFromLineDisc = function () {
    const recInput = document.getElementById('line-disc-rec-ctr');
    const recCtr = recInput ? String(recInput.value || '').trim() : '';
    if (!recCtr) {
      alert('No item selected for price override.');
      return;
    }
    window.closeLineDiscModal();
    window.openPriceOverrideModal(recCtr);
  };

  window.triggerPriceOverride = function () {
    const recCtr = getSelectedRecCtr();
    if (!recCtr) {
      return;
    }
    window.openPriceOverrideModal(recCtr);
  };

  window.openPriceOverrideModal = function (recCtr) {
    const modal = document.getElementById('price-override-modal');
    const recInput = document.getElementById('line-price-rec-ctr');
    const priceInput = document.getElementById('price-override-input');
    const currentEl = document.getElementById('price-override-current');
    if (!modal || !recInput || !priceInput) { return; }

    const recValue = String(recCtr || '').trim();
    if (!recValue) { return; }

    const recNumber = Number(recValue);
    const recKey = Number.isFinite(recNumber) ? Math.trunc(recNumber) : null;

    setSelectedScannedRow(recKey !== null ? String(recKey) : recValue);

    let currentPrice = 0;
    let row = null;

    if (recKey !== null) {
      document.querySelectorAll('.scanned-item[data-rec-ctr]').forEach(function (candidate) {
        if (row) { return; }
        const raw = candidate.getAttribute('data-rec-ctr');
        const n = Number(raw);
        if (Number.isFinite(n) && Math.trunc(n) === recKey) {
          row = candidate;
        }
      });
    } else {
      row = document.querySelector('.scanned-item[data-rec-ctr="' + recValue + '"]');
    }

    if (row) {
      const rowPrice = parseFloat(row.getAttribute('data-unit-price') || '0');
      if (Number.isFinite(rowPrice)) {
        currentPrice = rowPrice;
      }
    }

    recInput.value = recKey !== null ? String(recKey) : recValue;
    priceInput.value = currentPrice.toFixed(2);
    if (currentEl) {
      currentEl.textContent = '₱' + currentPrice.toFixed(2);
    }

    modal.classList.add('open');
    setTimeout(function () {
      priceInput.focus();
      priceInput.select();
    }, 80);
  };

  window.closePriceOverrideModal = function () {
    const modal = document.getElementById('price-override-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closePriceOverrideModalOutside = function (evt) {
    if (evt.target === document.getElementById('price-override-modal')) {
      window.closePriceOverrideModal();
    }
  };

  window.applyPriceOverride = function () {
    const recInput = document.getElementById('line-price-rec-ctr');
    const priceInput = document.getElementById('price-override-input');
    if (!recInput || !priceInput) { return; }

    const newPrice = parseFloat(priceInput.value || '0');
    if (!Number.isFinite(newPrice) || newPrice < 0) {
      alert('Enter a valid unit price.');
      return;
    }

    const recCtr = String(recInput.value || '').trim();
    if (!recCtr) {
      alert('No item selected for price override.');
      return;
    }

    postFormEncoded(CART_LINE_PRICE_OVERRIDE_URL, {
      rec_ctr: recCtr,
      new_price: newPrice.toFixed(4),
    })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          var msg = (res.data && res.data.error) ? res.data.error : ('Failed to apply price override (HTTP ' + res.status + ').');
          alert(msg);
          return;
        }
        window.closePriceOverrideModal();
        window.location.reload();
      })
      .catch(function () {
        alert('Failed to apply price override.');
      });
  };

  const priceOverrideInput = document.getElementById('price-override-input');
  if (priceOverrideInput) {
    priceOverrideInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        window.applyPriceOverride();
      }
    });
  }

  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const path = evt.detail.pathInfo && evt.detail.pathInfo.requestPath || '';
    if (path.indexOf('/cart/line-price-override') !== -1) {
      const barcodeInput = document.getElementById('barcode-input');
      if (barcodeInput) { barcodeInput.focus(); }
    }
  });

  // ---------------------------------------------------------------------------
  // Transaction Subtotal Discount Modal (F4)
  // ---------------------------------------------------------------------------
  // Initialise from server-rendered state so it survives page reload
  var pendingTransDisc = (typeof INITIAL_TRANS_DISC !== 'undefined')
    ? { pct: INITIAL_TRANS_DISC.pct, type: INITIAL_TRANS_DISC.type, label: INITIAL_TRANS_DISC.label }
    : { pct: 0, type: '', label: '' };

  window.openTransDiscModal = function () {
    const modal = document.getElementById('trans-disc-modal');
    const input = document.getElementById('trans-disc-pct-input');
    if (!modal) { return; }
    modal.classList.add('open');
    if (input) {
      input.value = pendingTransDisc.pct || 0;
      pendingTransDisc.pct = normalizeDiscountPctInput(input);
    }
    refreshTransDiscBtns(pendingTransDisc.type);
    setTimeout(function () { if (input) { input.focus(); input.select(); } }, 80);
  };

  window.closeTransDiscModal = function () {
    const modal = document.getElementById('trans-disc-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeTransDiscModalOutside = function (evt) {
    if (evt.target === document.getElementById('trans-disc-modal')) {
      window.closeTransDiscModal();
    }
  };

  window.selectTransDiscType = function (btn, code, label, defaultPct) {
    pendingTransDisc.type = code;
    pendingTransDisc.label = label;
    refreshTransDiscBtns(code);
    const input = document.getElementById('trans-disc-pct-input');
    if (input) {
      if (defaultPct > 0) { input.value = defaultPct; }
      input.focus(); input.select();
    }
  };

  function refreshTransDiscBtns(selectedCode) {
    document.querySelectorAll('#trans-disc-modal .disc-type-btn').forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-tdcode') === selectedCode);
    });
  }

  window.applyTransDisc = function () {
    const input = document.getElementById('trans-disc-pct-input');
    const pct = normalizeDiscountPctInput(input);
    if (pct <= 0) { window.removeTransDiscAndClose(); return; }
    pendingTransDisc.pct = pct;
    if (!pendingTransDisc.type) { pendingTransDisc.type = 'REG'; pendingTransDisc.label = 'Regular'; }
    submitTransDisc();
    window.closeTransDiscModal();
  };

  window.removeTransDiscAndClose = function () {
    pendingTransDisc = { pct: 0, type: '', label: '' };
    submitTransDisc();
    window.closeTransDiscModal();
  };

  function submitTransDisc() {
    const form = document.getElementById('trans-disc-form');
    if (!form) { return; }
    document.getElementById('trans-disc-pct-hidden').value = pendingTransDisc.pct;
    document.getElementById('trans-disc-type-hidden').value = pendingTransDisc.type;
    document.getElementById('trans-disc-label-hidden').value = pendingTransDisc.label;
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  }

  // Enter in trans-disc % input applies immediately
  const tdPctInput = document.getElementById('trans-disc-pct-input');
  if (tdPctInput) {
    ['input', 'change', 'blur'].forEach(function (evtName) {
      tdPctInput.addEventListener(evtName, function () {
        pendingTransDisc.pct = normalizeDiscountPctInput(tdPctInput);
      });
    });
    tdPctInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') { evt.preventDefault(); window.applyTransDisc(); }
    });
  }

  // ---------------------------------------------------------------------------
  // Item Search Modal
  // ---------------------------------------------------------------------------
  let searchTimer = null;
  let searchResultsCache = [];
  let searchSelectedIndex = -1;

  window.openSearchModal = function (prefill) {
    const modal = document.getElementById('search-modal');
    const input = document.getElementById('modal-search-input');
    searchResultsCache = [];
    searchSelectedIndex = -1;
    modal.classList.add('open');
    setTimeout(function () {
      input.focus();
      if (prefill && prefill.length >= 1) {
        input.value = prefill;
        // Fire input event so the live-search debounce triggers
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }, 80);
  };

  window.closeSearchModal = function () {
    document.getElementById('search-modal').classList.remove('open');
    document.getElementById('modal-search-input').value = '';
    document.getElementById('modal-results').innerHTML =
      '<p class="search-hint">Type at least 2 characters to search</p>';
    searchResultsCache = [];
    searchSelectedIndex = -1;
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeSearchModalOutside = function (evt) {
    if (evt.target === document.getElementById('search-modal')) {
      window.closeSearchModal();
    }
  };

  // ---------------------------------------------------------------------------
  // Pay Modal (tender floating window)
  // ---------------------------------------------------------------------------
  window.closePayModal = function () {
    const modal = document.getElementById('pay-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closePayModalOutside = function (evt) {
    if (evt.target === document.getElementById('pay-modal')) {
      window.closePayModal();
    }
  };

  window.openPayModal = function () {
    const btn = document.getElementById('pay-trigger-btn');
    if (btn) { btn.click(); }
  };

  // ---------------------------------------------------------------------------
  // Function Key Help Modal
  // ---------------------------------------------------------------------------
  window.openFkeyHelpModal = function () {
    const modal = document.getElementById('fkey-help-modal');
    if (!modal) { return; }
    // Build grid rows from POS_FKEYS + POS_KEY_LABELS
    const grid = document.getElementById('fkey-grid-body');
    if (grid && typeof POS_FKEYS !== 'undefined' && typeof POS_KEY_LABELS !== 'undefined') {
      grid.innerHTML = '';
      // Static non-POS-KEYS entries first (F1, F2)
      const staticEntries = [
        { key: 'F1', desc: 'Item Search' },
        { key: 'F2', desc: 'Quantity Input' },
      ];
      staticEntries.forEach(function (e) {
        grid.insertAdjacentHTML('beforeend', buildFkeyRow(e.key, e.desc));
      });
      // Dynamic POS_FKEYS entries
      Object.keys(POS_KEY_LABELS).forEach(function (fn) {
        const physKey = POS_FKEYS[fn];
        const desc = POS_KEY_LABELS[fn];
        grid.insertAdjacentHTML('beforeend', buildFkeyRow(physKey || null, desc));
      });
    }
    modal.classList.add('open');
  };

  function buildFkeyRow(physKey, desc) {
    const badgeClass = physKey ? 'fkey-badge' : 'fkey-badge unassigned';
    const badgeLabel = physKey || '—';
    return '<div class="fkey-row">' +
      '<span class="' + badgeClass + '">' + badgeLabel + '</span>' +
      '<span class="fkey-desc">' + desc + '</span>' +
      '</div>';
  }

  window.closeFkeyHelpModal = function () {
    const modal = document.getElementById('fkey-help-modal');
    if (modal) { modal.classList.remove('open'); }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) { barcodeInput.focus(); }
  };

  window.closeFkeyHelpModalOutside = function (evt) {
    if (evt.target === document.getElementById('fkey-help-modal')) {
      window.closeFkeyHelpModal();
    }
  };

  // Close modal on Escape
  document.addEventListener('keydown', function (evt) {
    if (evt.key === 'Escape') {
      const modal = document.getElementById('search-modal');
      if (modal && modal.classList.contains('open')) {
        window.closeSearchModal();
      }
    }
  });

  // Live search as user types
  const modalInput = document.getElementById('modal-search-input');
  if (modalInput) {
    modalInput.addEventListener('input', function () {
      clearTimeout(searchTimer);
      const q = modalInput.value.trim();
      searchResultsCache = [];
      searchSelectedIndex = -1;
      if (q.length < 2) {
        document.getElementById('modal-results').innerHTML =
          '<p class="search-hint">Type at least 2 characters to search</p>';
        return;
      }
      searchTimer = setTimeout(function () { doSearch(q); }, 250);
    });

    modalInput.addEventListener('keydown', function (evt) {
      const modal = document.getElementById('search-modal');
      if (!modal || !modal.classList.contains('open')) { return; }

      if (evt.key === 'ArrowDown') {
        evt.preventDefault();
        moveSearchSelection(1);
      } else if (evt.key === 'ArrowUp') {
        evt.preventDefault();
        moveSearchSelection(-1);
      } else if (evt.key === 'Enter') {
        if (searchResultsCache.length > 0) {
          evt.preventDefault();
          selectActiveSearchResult();
        }
      }
    });
  }

  function doSearch(q) {
    const resultsEl = document.getElementById('modal-results');
    resultsEl.innerHTML = '<p class="search-hint">Searching…</p>';

    fetch(ITEM_SEARCH_URL + '?q=' + encodeURIComponent(q), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) { renderResults(data.results); })
      .catch(function () {
        resultsEl.innerHTML = '<p class="search-empty">Search failed. Please try again.</p>';
      });
  }

  function renderResults(results) {
    const resultsEl = document.getElementById('modal-results');
    searchResultsCache = results || [];
    searchSelectedIndex = -1;
    if (!results || results.length === 0) {
      resultsEl.innerHTML = '<p class="search-empty">No items found.</p>';
      return;
    }

    const rows = results.map(function (item) {
      const sizeLabel = item.size_display || item.size || '';
      const colorLabel = item.color_display || item.color_desc || '';
      // const variant = [sizeLabel, colorLabel].filter(Boolean).join('/');
      const variant = [colorLabel, sizeLabel].filter(Boolean).join('/');
      const variantHtml = variant ? '<span class="search-result-variant">(' + variant + ')</span>' : '';
      return '<div class="search-result" onclick="selectSearchResult(\'' +
        escHtml(item.barcode) + '\')" title="Click to add to cart">' +
        '<div class="search-result-info">' +
          '<span class="search-result-desc">' + escHtml(item.description) + '</span>' +
          (variantHtml ? variantHtml : '') +
        '</div>'
        + '<span class="search-result-code">' + escHtml(item.code) + '</span>' +
        '<span class="search-result-variant">' + escHtml(item.barcode) + '</span>' +
        '<span class="search-result-price">₱' + parseFloat(item.price).toLocaleString('en-PH', { minimumFractionDigits: 2 }) + '</span>' +
        '</div>';
    });
    resultsEl.innerHTML = rows.join('');
    setSearchSelection(0);
  }

  function moveSearchSelection(delta) {
    if (!searchResultsCache.length) { return; }
    if (searchSelectedIndex < 0) {
      setSearchSelection(delta > 0 ? 0 : searchResultsCache.length - 1);
      return;
    }
    const next = (searchSelectedIndex + delta + searchResultsCache.length) % searchResultsCache.length;
    setSearchSelection(next);
  }

  function setSearchSelection(index) {
    const rows = document.querySelectorAll('#modal-results .search-result');
    if (!rows.length) {
      searchSelectedIndex = -1;
      return;
    }
    const bounded = Math.max(0, Math.min(index, rows.length - 1));
    searchSelectedIndex = bounded;
    rows.forEach(function (row, idx) {
      row.classList.toggle('active', idx === bounded);
    });
    if (rows[bounded] && rows[bounded].scrollIntoView) {
      rows[bounded].scrollIntoView({ block: 'nearest' });
    }
  }

  function selectActiveSearchResult() {
    if (!searchResultsCache.length) { return; }
    const idx = searchSelectedIndex >= 0 ? searchSelectedIndex : 0;
    const item = searchResultsCache[idx];
    if (item && item.barcode) {
      window.selectSearchResult(item.barcode);
    }
  }

  window.selectSearchResult = function (barcode) {
    window.closeSearchModal();

    // Put barcode into input and submit via HTMX
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) {
      barcodeInput.value = barcode;
      document.getElementById('barcode-form').dispatchEvent(new Event('submit', { bubbles: true }));
    }
  };

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function postFormEncoded(url, payload) {
    const body = new URLSearchParams(payload || {});
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-CSRFToken': CSRF_TOKEN,
      },
      body: body.toString(),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data || {} };
      }).catch(function () {
        return { ok: r.ok, status: r.status, data: {} };
      });
    });
  }

  function getSelectedRecCtr() {
    function hasRecCtrRow(recCtr) {
      if (!recCtr) { return false; }
      var rows = document.querySelectorAll('.scanned-item[data-rec-ctr]');
      for (var i = 0; i < rows.length; i += 1) {
        if (normalizeRecCtr(rows[i].getAttribute('data-rec-ctr')) === recCtr) {
          return true;
        }
      }
      return false;
    }

    if (selectedLineRecCtr && hasRecCtrRow(selectedLineRecCtr)) {
      return selectedLineRecCtr;
    }

    var hidden = document.getElementById('line-disc-rec-ctr');
    if (hidden && hidden.value) {
      var hiddenRecCtr = normalizeRecCtr(hidden.value);
      if (hiddenRecCtr && hasRecCtrRow(hiddenRecCtr)) {
        setSelectedScannedRow(hiddenRecCtr);
        return hiddenRecCtr;
      }
    }

    var scanned = document.querySelectorAll('.scanned-item[data-rec-ctr]');
    if (scanned && scanned.length) {
      var lastRecCtr = normalizeRecCtr(scanned[scanned.length - 1].getAttribute('data-rec-ctr'));
      setSelectedScannedRow(lastRecCtr);
      return lastRecCtr;
    }

    selectedLineRecCtr = '';
    return '';
  }

  var loadedReturnReceiptNo = '';
  var loadedReturnItems = [];

  window.openSuspendModal = function () {
    var modal = document.getElementById('suspend-modal');
    var errorEl = document.getElementById('suspend-error');
    if (!modal) {
      return;
    }
    if (errorEl) {
      errorEl.textContent = '';
    }
    modal.classList.add('open');
    window.loadSuspendedTransactions();
    setTimeout(function () {
      var searchInput = document.getElementById('suspend-search-input');
      if (searchInput) { searchInput.focus(); }
    }, 80);
  };

  var suspendTriggerBtn = document.getElementById('suspend-trigger-btn');
  if (suspendTriggerBtn) {
    suspendTriggerBtn.addEventListener('click', function () {
      window.openSuspendModal();
    });
  }

  function setSuspendedBadgeCount(count) {
    var badge = document.getElementById('suspended-count-badge');
    if (!badge) {
      return;
    }
    var safe = Number(count || 0);
    if (!Number.isFinite(safe) || safe < 0) {
      safe = 0;
    }
    safe = Math.trunc(safe);
    badge.textContent = String(safe);
    badge.classList.toggle('is-zero', safe === 0);
  }

  setSuspendedBadgeCount(typeof INITIAL_SUSPENDED_COUNT === 'undefined' ? 0 : INITIAL_SUSPENDED_COUNT);

  window.closeSuspendModal = function () {
    var modal = document.getElementById('suspend-modal');
    if (modal) {
      modal.classList.remove('open');
    }
    var barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) {
      barcodeInput.focus();
    }
  };

  window.closeSuspendModalOutside = function (evt) {
    if (evt.target === document.getElementById('suspend-modal')) {
      window.closeSuspendModal();
    }
  };

  window.loadSuspendedTransactions = function () {
    var searchInput = document.getElementById('suspend-search-input');
    var resultsEl = document.getElementById('suspended-results');
    var errorEl = document.getElementById('suspend-error');
    var q = String((searchInput && searchInput.value) || '').trim();
    var url = CART_SUSPENDED_LIST_URL;
    if (q) {
      url += '?q=' + encodeURIComponent(q);
    }

    if (resultsEl) {
      resultsEl.innerHTML = '<div class="return-receipt-empty">Loading suspended transactions...</div>';
    }
    if (errorEl) {
      errorEl.textContent = '';
    }

    fetch(url, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data || {} };
        }).catch(function () {
          return { ok: r.ok, data: {} };
        });
      })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (resultsEl) {
            resultsEl.innerHTML = '<div class="return-receipt-empty">Unable to load suspended transactions.</div>';
          }
          if (errorEl) {
            errorEl.textContent = res.data.error || 'Unable to load suspended transactions.';
          }
          return;
        }

        setSuspendedBadgeCount(res.data.suspended_count || 0);
        renderSuspendedRows(Array.isArray(res.data.suspended) ? res.data.suspended : []);
      })
      .catch(function () {
        if (resultsEl) {
          resultsEl.innerHTML = '<div class="return-receipt-empty">Unable to load suspended transactions.</div>';
        }
        if (errorEl) {
          errorEl.textContent = 'Unable to load suspended transactions.';
        }
      });
  };

  function renderSuspendedRows(rows) {
    var resultsEl = document.getElementById('suspended-results');
    if (!resultsEl) {
      return;
    }
    if (!rows || !rows.length) {
      resultsEl.innerHTML = '<div class="return-receipt-empty">No suspended transactions found.</div>';
      return;
    }

    resultsEl.innerHTML = rows.map(function (row) {
      var transNo = escHtml(row.transaction_no || '');
      var itemCount = Number(row.item_count || 0);
      var total = Number(row.total || 0);
      return '<label class="return-item-row">' +
        '<div class="return-item-main">' +
        '<div class="return-item-desc">Transaction #' + transNo + '</div>' +
        '<div class="return-item-meta">Items: ' + escHtml(itemCount) + '</div>' +
        '</div>' +
        '<div class="return-item-meta" style="display:flex;gap:8px;align-items:center;">' +
        '<span>' + formatPeso(total) + '</span>' +
        '<button type="button" class="btn btn-secondary" onclick="retrieveSuspendedTransaction(\'' + transNo + '\')">Retrieve</button>' +
        '</div>' +
        '</label>';
    }).join('');
  }

  window.retrieveSuspendedTransaction = function (transactionNo) {
    var errorEl = document.getElementById('suspend-error');
    if (!transactionNo) {
      return;
    }
    if (!confirm('Retrieve suspended transaction #' + transactionNo + '?')) {
      return;
    }
    if (errorEl) {
      errorEl.textContent = '';
    }

    postFormEncoded(CART_SUSPENDED_RETRIEVE_URL, { transaction_no: transactionNo })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (errorEl) {
            errorEl.textContent = res.data.error || 'Failed to retrieve transaction.';
          }
          return;
        }
        setSuspendedBadgeCount(Math.max(0, Number((document.getElementById('suspended-count-badge') || {}).textContent || 0) - 1));
        window.location.reload();
      })
      .catch(function () {
        if (errorEl) {
          errorEl.textContent = 'Failed to retrieve transaction.';
        }
      });
  };

  window.suspendCurrentTransaction = function () {
    var errorEl = document.getElementById('suspend-error');
    if (!confirm('Suspend current unpaid transaction?')) {
      return;
    }
    if (errorEl) {
      errorEl.textContent = '';
    }

    postFormEncoded(CART_SUSPEND_URL, {})
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (errorEl) {
            errorEl.textContent = res.data.error || 'Failed to suspend transaction.';
          }
          return;
        }
        setSuspendedBadgeCount(Number((document.getElementById('suspended-count-badge') || {}).textContent || 0) + 1);
        window.location.reload();
      })
      .catch(function () {
        if (errorEl) {
          errorEl.textContent = 'Failed to suspend transaction.';
        }
      });
  };

  window.triggerItemReturn = function () {
    window.openItemReturnModal();
  };
  var suspendSearchInput = document.getElementById('suspend-search-input');
  if (suspendSearchInput) {
    suspendSearchInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        window.loadSuspendedTransactions();
      }
    });
  }

  window.openItemReturnModal = function () {
    const modal = document.getElementById('item-return-modal');
    const sourceInput = document.getElementById('item-return-source-trans');
    const pinInput = document.getElementById('item-return-admin-pin');
    const errorEl = document.getElementById('item-return-error');
    const lineLabel = document.getElementById('item-return-line-label');
    const sourceDateEl = document.getElementById('item-return-source-date');
    const selectAll = document.getElementById('item-return-select-all');
    const resultsEl = document.getElementById('item-return-results');

    if (!modal) {
      return;
    }

    loadedReturnReceiptNo = '';
    loadedReturnItems = [];
    if (sourceInput) {
      sourceInput.value = '';
    }
    if (pinInput) {
      pinInput.value = '';
    }
    if (errorEl) {
      errorEl.textContent = '';
    }
    if (lineLabel) {
      lineLabel.textContent = 'Enter receipt number, load items, then select item(s) to return.';
    }
    if (sourceDateEl) {
      sourceDateEl.style.display = 'none';
      sourceDateEl.textContent = '';
    }
    if (selectAll) {
      selectAll.checked = false;
    }
    if (resultsEl) {
      resultsEl.innerHTML = '<div class="return-receipt-empty">No receipt loaded yet.</div>';
    }

    modal.classList.add('open');
    setTimeout(function () {
      if (sourceInput) { sourceInput.focus(); sourceInput.select(); }
    }, 80);
  };

  window.closeItemReturnModal = function () {
    const modal = document.getElementById('item-return-modal');
    if (modal) {
      modal.classList.remove('open');
    }
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) {
      barcodeInput.focus();
    }
  };

  window.closeItemReturnModalOutside = function (evt) {
    if (evt.target === document.getElementById('item-return-modal')) {
      window.closeItemReturnModal();
    }
  };

  window.lookupPreviousReceiptForReturn = function () {
    const sourceInput = document.getElementById('item-return-source-trans');
    const errorEl = document.getElementById('item-return-error');
    const sourceDateEl = document.getElementById('item-return-source-date');
    const selectAll = document.getElementById('item-return-select-all');
    const receiptNo = String((sourceInput && sourceInput.value) || '').trim();

    if (!receiptNo) {
      if (errorEl) { errorEl.textContent = 'Original transaction number is required.'; }
      return;
    }
    if (errorEl) { errorEl.textContent = ''; }
    if (selectAll) { selectAll.checked = false; }

    fetch(CART_RETURN_LOOKUP_URL + '?receipt_no=' + encodeURIComponent(receiptNo), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data || {} };
        }).catch(function () {
          return { ok: r.ok, data: {} };
        });
      })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          loadedReturnReceiptNo = '';
          loadedReturnItems = [];
          renderReturnLookupItems([]);
          if (sourceDateEl) {
            sourceDateEl.style.display = 'none';
            sourceDateEl.textContent = '';
          }
          if (errorEl) { errorEl.textContent = res.data.error || 'Receipt lookup failed.'; }
          return;
        }

        loadedReturnReceiptNo = res.data.receipt_no || '';
        loadedReturnItems = Array.isArray(res.data.items) ? res.data.items : [];
        renderReturnLookupItems(loadedReturnItems);
        if (sourceDateEl) {
          sourceDateEl.style.display = 'block';
          sourceDateEl.textContent = 'Purchased date: ' + (res.data.transaction_date || 'N/A');
        }
      })
      .catch(function () {
        loadedReturnReceiptNo = '';
        loadedReturnItems = [];
        renderReturnLookupItems([]);
        if (sourceDateEl) {
          sourceDateEl.style.display = 'none';
          sourceDateEl.textContent = '';
        }
        if (errorEl) { errorEl.textContent = 'Receipt lookup failed.'; }
      });
  };

  function renderReturnLookupItems(items) {
    const resultsEl = document.getElementById('item-return-results');
    if (!resultsEl) {
      return;
    }
    if (!items || !items.length) {
      resultsEl.innerHTML = '<div class="return-receipt-empty">No items loaded.</div>';
      return;
    }

    resultsEl.innerHTML = items.map(function (item) {
      var variant = [item.size, item.color].filter(Boolean).join('/');
      var variantHtml = variant ? (' <span>(' + escHtml(variant) + ')</span>') : '';
      var maxQty = escHtml(item.max_qty || item.qty || '0');
      return '<label class="return-item-row">' +
        '<input type="checkbox" class="return-item-check" data-item-id="' + escHtml(item.line_id) + '" onchange="toggleReturnQtyInput(this)">' +
        '<div class="return-item-main">' +
        '<div class="return-item-desc">' + escHtml(item.description || item.item_code || '') + variantHtml + '</div>' +
        '<div class="return-item-meta">Code: ' + escHtml(item.item_code || '') + ' | Qty: ' + escHtml(item.qty || '0') + ' x P' + escHtml(item.price || '0') + '</div>' +
        '<div class="return-item-qty-wrap">Return Qty: <input type="number" class="return-item-qty" data-item-id="' + escHtml(item.line_id) + '" min="0.0001" step="0.0001" max="' + maxQty + '" value="' + maxQty + '" disabled></div>' +
        '</div>' +
        '<div class="return-item-meta">P' + escHtml(item.ext || '0') + '</div>' +
        '</label>';
    }).join('');
  }

  window.toggleReturnQtyInput = function (checkboxEl) {
    if (!checkboxEl) { return; }
    var itemId = checkboxEl.getAttribute('data-item-id');
    var qtyInput = document.querySelector('.return-item-qty[data-item-id="' + itemId + '"]');
    if (!qtyInput) { return; }
    qtyInput.disabled = !checkboxEl.checked;
    if (checkboxEl.checked) {
      qtyInput.focus();
      qtyInput.select();
    }
  };

  window.toggleAllReturnItems = function (checked) {
    document.querySelectorAll('.return-item-check').forEach(function (cb) {
      cb.checked = !!checked;
      window.toggleReturnQtyInput(cb);
    });
  };

  window.importSelectedReturnItems = function () {
    const errorEl = document.getElementById('item-return-error');
    const sourceInput = document.getElementById('item-return-source-trans');
    const pinInput = document.getElementById('item-return-admin-pin');
    const receiptNo = loadedReturnReceiptNo || String((sourceInput && sourceInput.value) || '').trim();
    const managerPin = String((pinInput && pinInput.value) || '').trim();
    const selectedQtyMap = {};
    const selectedIds = Array.from(document.querySelectorAll('.return-item-check:checked'))
      .map(function (cb) {
        var id = Number(cb.getAttribute('data-item-id'));
        var qtyInput = document.querySelector('.return-item-qty[data-item-id="' + id + '"]');
        var qty = qtyInput ? Number(qtyInput.value) : 0;
        var maxQty = qtyInput ? Number(qtyInput.getAttribute('max')) : 0;
        if (!Number.isFinite(id) || id <= 0) { return null; }
        if (!Number.isFinite(qty) || qty <= 0) { return null; }
        if (Number.isFinite(maxQty) && maxQty > 0 && qty > maxQty) {
          qty = maxQty;
          if (qtyInput) { qtyInput.value = String(maxQty); }
        }
        selectedQtyMap[String(id)] = String(qty);
        return id;
      })
      .filter(function (id) { return Number.isFinite(id) && id > 0; });

    if (!receiptNo) {
      if (errorEl) { errorEl.textContent = 'Load a receipt first.'; }
      return;
    }
    if (!selectedIds.length) {
      if (errorEl) { errorEl.textContent = 'Select at least one item to return.'; }
      return;
    }
    if (!managerPin) {
      if (errorEl) { errorEl.textContent = 'Admin / manager PIN is required.'; }
      return;
    }
    if (errorEl) { errorEl.textContent = ''; }

    postFormEncoded(CART_RETURN_IMPORT_URL, {
      receipt_no: receiptNo,
      manager_pin: managerPin,
      item_ids: JSON.stringify(selectedIds),
      item_qtys: JSON.stringify(selectedQtyMap),
    })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          if (errorEl) {
            errorEl.textContent = res.data.error || 'Failed to import return items.';
          }
          return;
        }
        window.closeItemReturnModal();
        window.location.reload();
      })
      .catch(function () {
        if (errorEl) {
          errorEl.textContent = 'Failed to import return items.';
        }
      });
  };

  var sourceTransInput = document.getElementById('item-return-source-trans');
  if (sourceTransInput) {
    sourceTransInput.addEventListener('keydown', function (evt) {
      if (evt.key === 'Enter') {
        evt.preventDefault();
        window.lookupPreviousReceiptForReturn();
      }
    });
  }

  window.triggerVoidItem = function () {
    var recCtr = getSelectedRecCtr();
    if (!recCtr) {
      alert('No item selected to void. Click an item first.');
      return;
    }
    if (!confirm('Void selected item?')) {
      return;
    }

    postFormEncoded(CART_VOID_ITEM_URL, { rec_ctr: recCtr })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          alert(res.data.error || 'Failed to void item.');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        alert('Failed to void item.');
      });
  };

  window.triggerVoidTransaction = function () {
    var managerPin = prompt('Manager PIN required for full transaction void:');
    if (managerPin === null) {
      return;
    }
    managerPin = String(managerPin || '').trim();
    if (!managerPin) {
      alert('Manager PIN is required.');
      return;
    }
    if (!confirm('Void entire active transaction?')) {
      return;
    }

    postFormEncoded(CART_VOID_TRANSACTION_URL, { manager_pin: managerPin })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          alert(res.data.error || 'Failed to void transaction.');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        alert('Failed to void transaction.');
      });
  };

  window.triggerVoidPrevious = function () {
    var receiptNo = prompt('Enter receipt number to void:');
    if (receiptNo === null) {
      return;
    }
    receiptNo = String(receiptNo || '').trim();
    if (!receiptNo) {
      alert('Receipt number is required.');
      return;
    }

    var managerPin = prompt('Manager PIN required for void previous transaction:');
    if (managerPin === null) {
      return;
    }
    managerPin = String(managerPin || '').trim();
    if (!managerPin) {
      alert('Manager PIN is required.');
      return;
    }

    if (!confirm('Void receipt #' + receiptNo + '?')) {
      return;
    }

    postFormEncoded(CART_VOID_PREVIOUS_URL, {
      receipt_no: receiptNo,
      manager_pin: managerPin,
    })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          alert(res.data.error || 'Failed to void previous transaction.');
          return;
        }
        alert('Previous transaction voided: ' + (res.data.receipt_no || receiptNo));
      })
      .catch(function () {
        alert('Failed to void previous transaction.');
      });
  };
  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function formatPeso(num) {
    return (
      "₱" +
      parseFloat(num || 0).toLocaleString("en-PH", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    );
  }

  function getModal() {
    return document.getElementById("close-trans-modal");
  }

// ---------------------------------------------------------------------------
// Close Transaction Modal
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
  function getModal() {
      return document.getElementById("close-trans-modal");
  }

  function formatPeso(val) {
      return "₱" + parseFloat(val || 0).toLocaleString("en-PH", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
      });
  }

  function setText(id, val) {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
  }

  // ---------------------------------------------------------------------------
  // Credit / Debit breakdown renderer
  // ---------------------------------------------------------------------------
  function renderCreditDebitBreakdown(list) {
      const container = document.getElementById("close-trans-credit-debit-list");
      if (!container) return;
      container.innerHTML = "";

      if (!list || list.length === 0) {
          const empty = document.createElement("div");
          empty.innerHTML = '<span class="close-trans-credit-empty">No credit/debit transactions</span>';
          container.appendChild(empty);
          return;
      }

      list.forEach(item => {
          const row   = document.createElement("div");
          const label = document.createElement("span");
          label.textContent = item.tender_desc;
          const value = document.createElement("span");
          value.textContent = formatPeso(item.total);
          row.appendChild(label);
          row.appendChild(value);
          container.appendChild(row);
      });
  }

  function renderCashMovementsHistory(list) {
      const container = document.getElementById("close-trans-movements-list");
      if (!container) return;
      container.innerHTML = "";

      if (!list || list.length === 0) {
          const empty = document.createElement("span");
          empty.className = "ct-movements-empty";
          empty.textContent = "No cash movements recorded.";
          container.appendChild(empty);
          return;
      }

      list.forEach(movement => {
          const row = document.createElement("div");
          row.className = "ct-movement-row " + (movement.type === "IN" ? "in" : "out");

          const typeSpan = document.createElement("span");
          typeSpan.className = "ct-movement-type " + (movement.type === "IN" ? "in" : "out");
          typeSpan.textContent = movement.type === "IN" ? "↓ IN" : "↑ OUT";

          const detailsDiv = document.createElement("div");
          detailsDiv.className = "ct-movement-details";
          const reasonSpan = document.createElement("div");
          reasonSpan.className = "ct-movement-reason";
          reasonSpan.textContent = movement.reason;
          const metaSpan = document.createElement("div");
          metaSpan.className = "ct-movement-meta";
          metaSpan.textContent = movement.approved_by
              ? `${movement.performed_by} @ ${movement.created_at} (Approved: ${movement.approved_by})`
              : `${movement.performed_by} @ ${movement.created_at}`;
          detailsDiv.appendChild(reasonSpan);
          detailsDiv.appendChild(metaSpan);

          const amountSpan = document.createElement("span");
          amountSpan.className = "ct-movement-amount";
          amountSpan.textContent = formatPeso(movement.amount);

          row.appendChild(typeSpan);
          row.appendChild(detailsDiv);
          row.appendChild(amountSpan);
          container.appendChild(row);
      });
  }

  // ---------------------------------------------------------------------------
  // Open modal — fetch fresh data each time
  // ---------------------------------------------------------------------------
  window.openCloseTransModal = function () {
      const modal     = document.getElementById("close-trans-modal");
      const cashInput  = document.getElementById("closing-cash-input");
      const notesInput = document.getElementById("close-trans-notes");
      const confirmBtn = document.getElementById("close-trans-confirm-btn");

      if (!modal) return;

      // Reset inputs
      if (cashInput)  cashInput.value  = "";
      if (notesInput) notesInput.value = "";
      if (confirmBtn) confirmBtn.disabled = false;

      // Reset all display values
      const resetEl = (id, val = "₱0.00") => {
          const el = document.getElementById(id);
          if (el) el.textContent = val;
      };

      resetEl("close-trans-opening-cash");
      resetEl("close-trans-paid-in-cash");
      resetEl("close-trans-mid-cash-in");
      resetEl("close-trans-mid-cash-out");
      resetEl("close-trans-net-worth");
      resetEl("close-trans-gross-sales");
      resetEl("close-trans-total-discounts");
      resetEl("close-trans-net-sales");
      resetEl("close-trans-credit-debit-cash");
      resetEl("close-trans-expected-cash");
      resetEl("close-trans-actual-cash");
      resetEl("close-trans-void-count",   "0");
      resetEl("close-trans-void-amount");
      resetEl("close-trans-return-count", "0");
      resetEl("close-trans-return-amount");

      const cashReturnedEl = document.getElementById("close-trans-cash-returned");
      if (cashReturnedEl) cashReturnedEl.textContent = "";

      const varianceEl = document.getElementById("close-trans-variance");
      if (varianceEl) {
          varianceEl.textContent = "—";
          varianceEl.className   = "close-trans-variance-val";
      }

      renderCreditDebitBreakdown([]);

      if (typeof resetDenomModal === "function") resetDenomModal();

      // Fetch session details
      fetch("/pos/to-close-session-details/", {
          method: "GET",
          headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF_TOKEN },
      })
      .then(r => r.json())
      .then(data => {
          const openingCash     = parseFloat(data.opening_cash)     || 0;
          const paidInCash      = parseFloat(data.paid_in_cash)     || 0;
          const midCashIn       = parseFloat(data.total_mid_cash_in) || 0;
          const midCashOut      = parseFloat(data.total_mid_cash_out) || 0;
          const cashReturned    = parseFloat(data.cash_returned)    || 0;
          const creditDebitCash = parseFloat(data.credit_debit_cash)|| 0;
          const expectedCash    = parseFloat(data.expected_cash)    || 0;
          const grossSales      = parseFloat(data.gross_sales)      || 0;
          const totalDiscounts  = parseFloat(data.total_discounts)  || 0;
          const netSales        = parseFloat(data.net_sales)        || 0;
          const netWorth        = parseFloat(data.net_worth)        || 0;
          const voidCount       = parseInt(data.void_count)         || 0;
          const voidAmount      = parseFloat(data.void_amount)      || 0;
          const returnCount     = parseInt(data.return_count)       || 0;
          const returnAmount    = parseFloat(data.return_amount)    || 0;

          // Store on modal for form submit and variance recalc
          modal._openingCash     = openingCash;
          modal._paidInCash      = paidInCash;
          modal._midCashIn       = midCashIn;
          modal._midCashOut      = midCashOut;
          modal._cashReturned    = cashReturned;
          modal._creditDebitCash = creditDebitCash;
          modal._expectedCash    = expectedCash;
          modal._netWorth        = netWorth;
          modal._grossSales      = grossSales;
          modal._totalDiscounts  = totalDiscounts;
          modal._netSales        = netSales;
          modal._voidCount       = voidCount;
          modal._voidAmount      = voidAmount;
          modal._returnCount     = returnCount;
          modal._returnAmount    = returnAmount;

          // Update display
          resetEl("close-trans-opening-cash",     formatPeso(openingCash));
          resetEl("close-trans-paid-in-cash",     formatPeso(paidInCash));
          resetEl("close-trans-mid-cash-in",      formatPeso(midCashIn));
          resetEl("close-trans-mid-cash-out",     formatPeso(midCashOut));
          resetEl("close-trans-expected-cash",    formatPeso(expectedCash));
          resetEl("close-trans-actual-cash",      formatPeso(expectedCash)); // until closing cash input re-enabled
          resetEl("close-trans-net-worth",        formatPeso(netWorth));
          resetEl("close-trans-gross-sales",      formatPeso(grossSales));
          resetEl("close-trans-total-discounts",  formatPeso(totalDiscounts));
          resetEl("close-trans-net-sales",        formatPeso(netSales));
          resetEl("close-trans-credit-debit-cash", formatPeso(creditDebitCash));
          resetEl("close-trans-void-count",       voidCount);
          resetEl("close-trans-void-amount",      formatPeso(voidAmount));
          resetEl("close-trans-return-count",     returnCount);
          resetEl("close-trans-return-amount",    formatPeso(returnAmount));

          // Cash returned sub-label
          if (cashReturnedEl && cashReturned > 0) {
              cashReturnedEl.textContent = `−${formatPeso(cashReturned)} returned`;
          }

          // Sync hidden inputs
          _syncHiddenFields(modal);

          renderCreditDebitBreakdown(data.credit_debit_cash_list || []);
          
          // Fetch and render cash movements history
          fetch("/sales/cash-movements-history/", {
              method: "GET",
              headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF_TOKEN },
          })
          .then(r => r.json())
          .then(movementsData => {
              if (movementsData.ok) {
                  renderCashMovementsHistory(movementsData.movements || []);
              }
          })
          .catch(err => console.warn("Could not load cash movements history:", err));
      })
      .catch(err => console.error("Failed to load session details:", err));

      modal.classList.add("open");
      setTimeout(() => cashInput && cashInput.focus(), 80);
  };

  // ---------------------------------------------------------------------------
  // Sync hidden form fields from modal state
  // ---------------------------------------------------------------------------
  function _syncHiddenFields(modal) {
      const setVal = (id, val) => {
          const el = document.getElementById(id);
          if (el) el.value = parseFloat(val || 0).toFixed(2);
      };
      const setInt = (id, val) => {
          const el = document.getElementById(id);
          if (el) el.value = parseInt(val || 0);
      };

      setVal("hidden-opening-cash",      modal._openingCash);
      setVal("hidden-paid-in-cash",      modal._paidInCash);
      setVal("hidden-mid-cash-in",       modal._midCashIn);
      setVal("hidden-mid-cash-out",      modal._midCashOut);
      setVal("hidden-credit-debit-cash", modal._creditDebitCash);
      setVal("hidden-expected-cash",     modal._expectedCash);
      setVal("hidden-net-worth",         modal._netWorth);
      setVal("hidden-gross-sales",       modal._grossSales);
      setVal("hidden-total-discounts",   modal._totalDiscounts);
      setVal("hidden-net-sales",         modal._netSales);
      setVal("hidden-void-amount",       modal._voidAmount);
      setVal("hidden-return-amount",     modal._returnAmount);
      setInt("hidden-void-count",        modal._voidCount);
      setInt("hidden-return-count",      modal._returnCount);
  }

  // ---------------------------------------------------------------------------
  // Close modal
  // ---------------------------------------------------------------------------
  window.closeCloseTransModal = function () {
      const modal = getModal();
      if (modal) modal.classList.remove("open");
      document.getElementById("barcode-input")?.focus();
  };

  window.closeCloseTransModalOutside = function (evt) {
      if (evt.target === getModal()) window.closeCloseTransModal();
  };

  // ---------------------------------------------------------------------------
  // Z-Read confirm strip toggle
  // ---------------------------------------------------------------------------
  window.showZReadConfirm = function () {
      const strip  = document.getElementById("close-trans-confirm-strip");
      const footer = document.getElementById("close-trans-footer-default");
      if (strip)  strip.style.display  = "block";
      if (footer) footer.style.display = "none";
  };

  window.hideZReadConfirm = function () {
      const strip  = document.getElementById("close-trans-confirm-strip");
      const footer = document.getElementById("close-trans-footer-default");
      if (strip)  strip.style.display  = "none";
      if (footer) footer.style.display = "flex";
  };

  // ---------------------------------------------------------------------------
  // Variance — recalculate whenever the closing cash input changes
  // ---------------------------------------------------------------------------
  function recalcVariance() {
      const modal      = getModal();
      const cashInput  = document.getElementById("closing-cash-input");
      const varianceEl = document.getElementById("close-trans-variance");
      const confirmBtn = document.getElementById("close-trans-confirm-btn");

      if (!cashInput || !varianceEl || !modal) return;

      const expected = (modal._expectedCash || 0);
      const raw      = cashInput.value;
      const actual   = parseFloat(raw) || 0;

      if (!raw) {
          varianceEl.textContent = "—";
          varianceEl.className   = "close-trans-variance-val";
          if (confirmBtn) confirmBtn.disabled = true;
          return;
      }

      const variance = actual - expected;

      if (variance > 0) {
          varianceEl.textContent = "+" + formatPeso(variance) + " over";
          varianceEl.className   = "close-trans-variance-val over";
      } else if (variance < 0) {
          varianceEl.textContent = formatPeso(Math.abs(variance)) + " short";
          varianceEl.className   = "close-trans-variance-val short";
      } else {
          varianceEl.textContent = "Exact";
          varianceEl.className   = "close-trans-variance-val exact";
      }

      if (confirmBtn) confirmBtn.disabled = actual < 0;
  }

  const closingCashInput = document.getElementById("closing-cash-input");
  if (closingCashInput) {
      closingCashInput.addEventListener("input", recalcVariance);
      closingCashInput.addEventListener("keydown", function (evt) {
          if (evt.key === "Enter") {
              evt.preventDefault();
              const confirmBtn = document.getElementById("close-trans-confirm-btn");
              if (confirmBtn && !confirmBtn.disabled) {
                  document.getElementById("close-trans-form").requestSubmit();
              }
          }
      });
  }

  // ---------------------------------------------------------------------------
  // Z-Reading Guard — triggered by middleware
  // ---------------------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
      if (typeof Z_READING_REQUIRED !== "undefined" && Z_READING_REQUIRED) {
          window.openCloseTransModal();
      }
  });

  document.addEventListener("openCloseTransModal", function () {
      const modal = getModal();
      if (modal && modal.classList.contains("open")) return;
      window.openCloseTransModal();
  });

  // ---------------------------------------------------------------------------
  // Form submit — sync hidden fields then POST
  // ---------------------------------------------------------------------------
  const closeTransForm = document.getElementById("close-trans-form");
  if (closeTransForm) {
      closeTransForm.addEventListener("submit", function (evt) {
          evt.preventDefault();

          const modal       = getModal();
          const cashInput   = document.getElementById("closing-cash-input");
          const closingCash = parseFloat(cashInput?.value) || 0;
          const expected    = (modal?._expectedCash)    || 0;
          const variance    = closingCash - expected;

          // Sync all hidden fields
          _syncHiddenFields(modal);

          // Variance is the only value that depends on closing cash input
          const varianceEl = document.getElementById("hidden-cash-variance");
          if (varianceEl) varianceEl.value = variance.toFixed(2);

          closeTransForm.submit();
      });
  }

  window.openCashInOutModal = function (defaultType) {
    const modal = document.getElementById("cash-inout-modal");
    const form = document.getElementById("cash-inout-form");
    const typeEl = document.getElementById("cash-movement-type");
    if (!modal) return;

    if (form) form.reset();
    if (typeEl && defaultType) {
      typeEl.value = defaultType;
    }

    modal.classList.add("open");
    setTimeout(() => {
      document.getElementById("cash-movement-amount")?.focus();
    }, 80);
  };

  window.closeCashInOutModal = function () {
    const modal = document.getElementById("cash-inout-modal");
    if (modal) modal.classList.remove("open");
    document.getElementById("barcode-input")?.focus();
  };

  window.closeCashInOutModalOutside = function (evt) {
    const modal = document.getElementById("cash-inout-modal");
    if (evt.target === modal) {
      window.closeCashInOutModal();
    }
  };

  window.submitCashInOut = function () {
    const form = document.getElementById("cash-inout-form");
    if (!form) return;

    const payload = new URLSearchParams(new FormData(form));

    fetch(CASH_INOUT_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-CSRFToken": CSRF_TOKEN,
      },
      body: payload.toString(),
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.ok) {
          alert(data.error || "Unable to save cash movement.");
          return;
        }

        const movementLabel = data.movement_type === "IN" ? "Cash In" : "Cash Out";
        alert(movementLabel + " saved: " + formatPeso(data.amount));
        window.closeCashInOutModal();
      })
      .catch(() => {
        alert("Network error while saving cash movement.");
      });
  };

  // ---------------------------------------------------------------------------
  // Denomination Modal
  // ---------------------------------------------------------------------------
  function resetDenomModal() {
    document.querySelectorAll(".denom-qty").forEach((inp) => (inp.value = ""));
    document.querySelectorAll(".denom-subtotal").forEach((el) => (el.textContent = "₱0.00"));
    const totalDisplay = document.getElementById("denom-total-display");
    if (totalDisplay) {
      totalDisplay.textContent = "₱0.00";
      totalDisplay.dataset.total = "0";
    }
  }

  window.openDenominationModal = function () {
    document.getElementById("denom-modal").style.display = "flex";
  };

  window.closeDenominationModal = function () {
    document.getElementById("denom-modal").style.display = "none";
  };

  window.closeDenominationModalOutside = function (evt) {
    if (evt.target.id === "denom-modal") window.closeDenominationModal();
  };

  window.applyDenominationTotal = function () {
    const totalDisplay = document.getElementById("denom-total-display");
    const total = parseFloat(totalDisplay?.dataset.total || 0);
    const cashInput = document.getElementById("closing-cash-input");

    if (cashInput) {
      cashInput.value = total.toFixed(2);
      // Trigger variance recalc
      cashInput.dispatchEvent(new Event("input", { bubbles: true }));
      cashInput.focus();
    }

    window.closeDenominationModal();
  };

  function updateDenomTotal() {
    let total = 0;
    document.querySelectorAll(".denom-row").forEach((row) => {
      const value = parseFloat(row.dataset.value) || 0;
      const qty = parseInt(row.querySelector(".denom-qty").value || 0, 10) || 0;
      total += value * qty;
    });

    const totalDisplay = document.getElementById("denom-total-display");
    if (totalDisplay) {
      totalDisplay.textContent = formatPeso(total);
      totalDisplay.dataset.total = total;
    }
  }

  // Wire up each denomination row — single implementation
  document.querySelectorAll(".denom-row").forEach((row) => {
    const value = parseFloat(row.dataset.value) || 0;
    const qtyInput = row.querySelector(".denom-qty");
    const subtotalEl = row.querySelector(".denom-subtotal");
    const plusBtn = row.querySelector(".plus");
    const minusBtn = row.querySelector(".minus");

    function updateRow() {
      const qty = parseInt(qtyInput.value || 0, 10) || 0;
      const subtotal = qty * value;
      if (subtotalEl) subtotalEl.textContent = formatPeso(subtotal);
      updateDenomTotal();
    }

    plusBtn?.addEventListener("click", () => { qtyInput.value = (parseInt(qtyInput.value || 0, 10) || 0) + 1; updateRow(); });
    minusBtn?.addEventListener("click", () => { qtyInput.value = Math.max(0, (parseInt(qtyInput.value || 0, 10) || 0) - 1); updateRow(); });
    qtyInput?.addEventListener("input", updateRow);
  });

  syncSelectedRowAfterRender();
})();