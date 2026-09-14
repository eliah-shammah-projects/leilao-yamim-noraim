/* Countdown and bid modal.
   Nothing here decides whether a bid is valid. That happens on the server. */

(function () {
  "use strict";

  /* ---------- Countdown ---------- */

  // The page shows whole days only and does not carry the closing hour at all.
  // The server says how many seconds until the day count next changes, which
  // is midnight in Israel, and the page reloads then so the figure moves. It
  // does not reload at the closing hour, since it does not know it: a bid sent
  // after the close is refused by the server, and the next load shows the
  // closed state.
  function startCountdown() {
    var box = document.querySelector(".countdown");
    if (!box) {
      return;
    }

    var seconds = parseInt(box.dataset.refreshIn, 10);
    if (isNaN(seconds) || seconds <= 0) {
      return;
    }

    function refresh() {
      // Never throw away a bid somebody is in the middle of typing.
      if (document.querySelector(".modal:not([hidden])")) {
        window.setTimeout(refresh, 60000);
        return;
      }
      window.location.reload();
    }

    window.setTimeout(refresh, seconds * 1000);
  }

  /* ---------- Bid modal ---------- */

  // Set by startModal. The enlarged card carries a clone of the bid button,
  // made after load, so it cannot rely on the listeners bound below.
  var openBid = null;

  function startModal() {
    var modal = document.getElementById("bid-modal");
    if (!modal) {
      return;
    }

    var form = document.getElementById("bid-form");
    var titleEl = document.getElementById("modal-title");
    var amountEl = form.querySelector('[name="amount"]');
    var lastTrigger = null;

    function open(button) {
      lastTrigger = button;
      titleEl.textContent = button.dataset.aliyahName;
      form.action = button.dataset.action;

      modal.hidden = false;
      document.body.style.overflow = "hidden";

      // Contact fields are usually already filled from a previous bid, so the
      // amount is the one thing left to type.
      window.setTimeout(function () {
        amountEl.focus();
      }, 60);
    }

    function close() {
      modal.hidden = true;
      document.body.style.overflow = "";
      if (lastTrigger) {
        lastTrigger.focus();
        lastTrigger = null;
      }
    }

    openBid = open;

    document.querySelectorAll(".btn-bid").forEach(function (button) {
      button.addEventListener("click", function () {
        open(button);
      });
    });

    modal.querySelectorAll("[data-close]").forEach(function (el) {
      el.addEventListener("click", close);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !modal.hidden) {
        close();
      }
    });

    // A rejected bid comes back as a normal page load. Reopen the aliyah the
    // visitor was on so the error and the form stay together.
    var marker = document.getElementById("reopen-marker");
    if (marker) {
      var button = document.querySelector(
        '.btn-bid[data-aliyah-id="' + marker.dataset.aliyahId + '"]'
      );
      if (button) {
        open(button);
      }
    }
  }

  /* ---------- The enlarged card ---------- */

  /* Tapping a card brings the same card up big in the middle of the page, with
     its photograph, its name, its amount and its bid button. It is the card
     itself, cloned, not a second design to keep in step with the first. The
     small button on the card still opens the form directly. */

  function startCardZoom() {
    var modal = document.getElementById("card-modal");
    if (!modal) {
      return;
    }

    var slot = modal.querySelector(".card-modal-slot");
    var lastTrigger = null;

    function close() {
      modal.hidden = true;
      document.body.style.overflow = "";
      slot.innerHTML = "";
      if (lastTrigger) {
        lastTrigger.focus();
        lastTrigger = null;
      }
    }

    function open(card, trigger) {
      lastTrigger = trigger;

      var clone = card.cloneNode(true);
      clone.removeAttribute("id");
      clone.classList.add("card-big");

      // No zooming a card that is already open.
      var cover = clone.querySelector(".card-zoom");
      if (cover) {
        cover.parentNode.removeChild(cover);
      }

      // The clone's photograph must not wait to be scrolled into view.
      clone.querySelectorAll("img[loading]").forEach(function (img) {
        img.removeAttribute("loading");
      });

      // The form is opened from the card's own button, not from the clone.
      // The clone is thrown away when this panel closes, and focus has to have
      // somewhere real to return to afterwards.
      var origin = card.querySelector(".btn-bid");
      var bid = clone.querySelector(".btn-bid");
      if (bid && origin) {
        bid.addEventListener("click", function () {
          close();
          if (openBid) {
            openBid(origin);
          }
        });
      }

      slot.innerHTML = "";
      slot.appendChild(clone);

      modal.hidden = false;
      document.body.style.overflow = "hidden";
    }

    document.querySelectorAll(".card-zoom").forEach(function (cover) {
      cover.addEventListener("click", function () {
        open(cover.closest(".card"), cover);
      });
    });

    modal.querySelectorAll("[data-close]").forEach(function (el) {
      el.addEventListener("click", close);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !modal.hidden) {
        close();
      }
    });
  }

  /* ---------- Banners ---------- */

  function startFlashes() {
    var flashes = document.querySelectorAll(".flash");
    if (!flashes.length) {
      return;
    }

    function dismiss(flash) {
      flash.classList.add("is-going");
      window.setTimeout(function () {
        flash.remove();
      }, 520);
    }

    flashes.forEach(function (flash) {
      var button = flash.querySelector(".flash-close");
      if (button) {
        button.addEventListener("click", function () {
          dismiss(flash);
        });
      }
      // A confirmation should not sit on the page forever. It goes on its own
      // after a while, and the close button is there for anyone impatient.
      window.setTimeout(function () {
        dismiss(flash);
      }, 8000);
    });
  }

  /* ---------- Keeping your place when the occasion changes ---------- */

  /* Switching tab is a normal link, so the browser loads a fresh page and
     lands at the top. Someone half way down the aliyot who taps the other
     occasion and comes back should not have to scroll all the way down again.
     The position is remembered across the one navigation and restored. */

  var TAB_SCROLL_KEY = "aliyot:tab-scroll";

  function startTabs() {
    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        try {
          sessionStorage.setItem(TAB_SCROLL_KEY, String(window.scrollY));
        } catch (error) {
          // Private browsing can refuse storage. Losing the scroll position is
          // not a reason to break the link.
        }
      });
    });

    var saved = null;
    try {
      saved = sessionStorage.getItem(TAB_SCROLL_KEY);
      sessionStorage.removeItem(TAB_SCROLL_KEY);
    } catch (error) {
      return;
    }

    // A bid comes back with an anchor to its own card. That wins.
    if (saved === null || window.location.hash) {
      return;
    }

    var wanted = parseInt(saved, 10);
    if (isNaN(wanted)) {
      return;
    }

    // The other occasion can be a far shorter page: Yom Kipur is one panel.
    var root = document.documentElement;
    var limit = Math.max(0, root.scrollHeight - window.innerHeight);
    var target = Math.max(0, Math.min(wanted, limit));

    // The page scrolls smoothly by default, which would animate this jump.
    var previous = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    window.scrollTo(0, target);
    root.style.scrollBehavior = previous;
  }

  startCountdown();
  startModal();
  startCardZoom();
  startFlashes();
  startTabs();
})();
