/*
 * Connection watchdog for the cashier screen.
 *
 * Pings /logs/health/ every few seconds. When the server/database stops
 * answering it shows a banner ("do not retry payment"); when it comes back it
 * tells the cashier to verify the cart and reports the outage to the audit log
 * (CONNECTION_LOST / CONNECTION_RESTORED). Reports made while offline are kept
 * in localStorage and sent after recovery.
 *
 * Passive by design: it never blocks, retries or modifies any POS request.
 */
(function () {
  var HEALTH_URL = '/logs/health/';
  var EVENT_URL = '/logs/client-event/';
  var STATUS_URL = '/logs/transaction-status/';
  var INTERVAL_MS = 5000;
  var FAILS_BEFORE_ALERT = 2;
  var QUEUE_KEY = 'pos_conn_events';

  var fails = 0;
  var lostAt = null;
  var banner = null;

  function cookie(name) {
    var m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[1]) : '';
  }

  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); } catch (e) { return []; }
  }

  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch (e) { /* storage unavailable */ }
  }

  function currentTransNo() {
    var el = document.querySelector('[data-trans-no]');
    return el ? el.getAttribute('data-trans-no') : '';
  }

  function flushQueue() {
    var queue = loadQueue();
    if (!queue.length) return;
    saveQueue([]);
    queue.forEach(function (evt) {
      fetch(EVENT_URL, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
        body: JSON.stringify(evt)
      }).then(function (r) {
        if (!r.ok) throw new Error('rejected');
      }).catch(function () {
        saveQueue(loadQueue().concat([evt]));   // try again next time
      });
    });
  }

  function queueEvent(evt) {
    saveQueue(loadQueue().concat([evt]));
  }

  function showBanner(html, color) {
    if (!banner) {
      banner = document.createElement('div');
      banner.setAttribute('role', 'alert');
      banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;padding:10px 16px;' +
        'font:600 14px system-ui,sans-serif;color:#fff;text-align:center';
      document.body.appendChild(banner);
    }
    banner.style.background = color;
    banner.innerHTML = html;
    banner.style.display = 'block';
  }

  function hideBanner() {
    if (banner) banner.style.display = 'none';
  }

  function onLost() {
    lostAt = new Date();
    showBanner('Connection to the server was lost. Do NOT retry the payment &mdash; wait for this message to clear.', '#b42318');
    queueEvent({ event: 'CONNECTION_LOST', lost_at: lostAt.toISOString(), trans_no: currentTransNo(), page: location.pathname });
  }

  function onRestored() {
    var now = new Date();
    var seconds = lostAt ? Math.round((now - lostAt) / 1000) : null;
    queueEvent({ event: 'CONNECTION_RESTORED', lost_at: lostAt && lostAt.toISOString(), restored_at: now.toISOString(),
      seconds: seconds, trans_no: currentTransNo(), page: location.pathname });
    lostAt = null;

    var transNo = currentTransNo();
    var msg = 'Connection restored. Please verify the cart before continuing. ' +
      '<a href="" style="color:#fff;text-decoration:underline" onclick="location.reload();return false;">Reload cart</a>';
    showBanner(msg, '#b54708');
    if (transNo) {
      fetch(STATUS_URL + encodeURIComponent(transNo) + '/', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.status === 'completed') {
            showBanner('Connection restored. Transaction ' + transNo + ' was already COMPLETED &mdash; do not charge again.', '#b42318');
          }
        }).catch(function () { /* banner above is enough */ });
    }
    setTimeout(hideBanner, 20000);
    flushQueue();
  }

  function ping() {
    var controller = window.AbortController ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, 4000) : null;
    fetch(HEALTH_URL, { cache: 'no-store', signal: controller ? controller.signal : undefined })
      .then(function (r) { if (!r.ok) throw new Error('unhealthy'); })
      .then(function () {
        fails = 0;
        if (lostAt) onRestored(); else flushQueue();
      })
      .catch(function () {
        fails += 1;
        if (fails === FAILS_BEFORE_ALERT && !lostAt) onLost();
      })
      .then(function () { if (timer) clearTimeout(timer); });
  }

  setInterval(ping, INTERVAL_MS);
})();
