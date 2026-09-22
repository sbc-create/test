/**
 * Shared comments widget.
 *
 * One file, four sites. A tenant template must never contain a copy of this
 * code — it references a pinned version of this artifact and supplies a small
 * configuration object, and that is the whole integration.
 *
 * Design rules that are load-bearing rather than stylistic:
 *
 * - **The page survives us.** Every entry point is wrapped so that a failure
 *   inside the widget cannot propagate into the host page's JavaScript. A
 *   comments outage degrades to a message in one box; it does not take down a
 *   film page.
 * - **No framework.** It attaches to a DOM node it owns and touches nothing
 *   above it, so React, Vue and plain HTML all host it the same way. It does
 *   not re-render nodes it did not create, which is what makes it safe inside
 *   a React tree: React's reconciler never sees our children change.
 * - **mount / update / destroy are idempotent.** Mounting twice returns the
 *   same instance; destroying twice is a no-op. Several instances on one page
 *   are independent, keyed by their root element.
 * - **Server-rendered comments stay readable without us.** When SSR is on, the
 *   markup is already there and correct; this script enhances it and never
 *   clears it before it has something to put back.
 * - **Nothing user-written leaves in telemetry.** The event payloads below
 *   carry counts, durations and error codes. No comment text, no subject ids,
 *   no tokens.
 */
(function (global) {
  "use strict";

  var MODULE_VERSION = "0.1.0-mvp";
  var API_VERSION = "v1";
  var instances = new WeakMap();

  // ---------------------------------------------------------------- utils

  function noop() {}

  /**
   * Run `fn`; never let it escape into the host page — but never hide it either.
   *
   * The first version of this swallowed the exception silently, and the widget
   * promptly failed to mount with no message anywhere: the page was intact and
   * entirely undebuggable. Not breaking the host page and leaving no trace are
   * different goals, and only the first one is worth having. So the error is
   * reported to the console and to telemetry, and only then dropped.
   */
  function guard(fn, onError) {
    return function () {
      try {
        return fn.apply(this, arguments);
      } catch (err) {
        try {
          if (global.console && console.warn) {
            console.warn("[comments] " + (err && err.message ? err.message : String(err)), err);
          }
          (onError || noop)(err);
        } catch (_ignored) {
          // Even the error handler must not throw into the page.
        }
        return undefined;
      }
    };
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "text") {
          // textContent, never innerHTML: this path handles values we build.
          node.textContent = attrs[key];
        } else if (attrs[key] !== null && attrs[key] !== undefined) {
          node.setAttribute(key, String(attrs[key]));
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child) node.appendChild(child);
    });
    return node;
  }

  /**
   * One cookie by name, or "".
   *
   * Only the CSRF token is ever read this way, and it is the one cookie
   * deliberately not marked HttpOnly — that is the entire double-submit
   * mechanism. The guest pseudonym and the cohort token are HttpOnly and this
   * function cannot see them, which is the point.
   */
  function readCookie(name) {
    try {
      var parts = (document.cookie || "").split(";");
      for (var i = 0; i < parts.length; i += 1) {
        var pair = parts[i].trim();
        if (pair.indexOf(name + "=") === 0) return pair.slice(name.length + 1);
      }
    } catch (_ignored) {
      // A document without cookies is not an error worth breaking a page for.
    }
    return "";
  }

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      var self = this;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(self, args);
      }, wait);
    };
  }

  // -------------------------------------------------------------- config

  function normaliseConfig(raw) {
    var cfg = raw || {};
    // An empty apiBase means "same origin", which is the ordinary case when
    // the API is served from the site itself. Only an absent or non-string
    // value is a configuration error.
    if (cfg.apiBase === undefined || cfg.apiBase === null) {
      throw new Error("comments: apiBase is required (use \"\" for same origin)");
    }
    if (!cfg.resourceType || !cfg.canonicalContentId) {
      throw new Error("comments: resourceType and canonicalContentId are required");
    }
    // Note what is absent: tenant and site. The server derives them from the
    // request host. A widget that could name its own tenant would make the
    // whole isolation story a suggestion.
    return {
      apiBase: String(cfg.apiBase).replace(/\/+$/, ""),
      resourceType: String(cfg.resourceType),
      canonicalContentId: String(cfg.canonicalContentId),
      sort: cfg.sort || "new",
      pageSize: Math.max(1, Math.min(parseInt(cfg.pageSize, 10) || 20, 100)),
      locale: cfg.locale || "ru",
      theme: cfg.theme || "auto",
      readOnly: !!cfg.readOnly,
      maxLength: parseInt(cfg.maxLength, 10) || 4000,
      csrfHeader: cfg.csrfHeader || "X-CP-CSRF",
      // Explicit token wins; otherwise the double-submit cookie the gateway
      // issues is read at request time. Reading it per request rather than
      // once at mount matters: the very first response is what creates it.
      csrfToken: cfg.csrfToken || "",
      csrfCookie: cfg.csrfCookie || "cp_csrf",
      onEvent: typeof cfg.onEvent === "function" ? cfg.onEvent : noop,
      strings: Object.assign({}, DEFAULT_STRINGS, cfg.strings || {})
    };
  }

  var DEFAULT_STRINGS = {
    heading: "Комментарии",
    empty: "Пока никто не написал. Будьте первым.",
    loading: "Загружаем комментарии…",
    error: "Комментарии сейчас недоступны. Страница продолжает работать.",
    offline: "Нет связи. Комментарии появятся, когда соединение вернётся.",
    retry: "Повторить",
    more: "Показать ещё",
    submit: "Отправить",
    placeholder: "Ваш комментарий",
    reply: "Ответить",
    edit: "Изменить",
    remove: "Удалить",
    spoilerShow: "Показать спойлер",
    spoilerHide: "Скрыть спойлер",
    pending: "Комментарий отправлен и ждёт проверки модератора.",
    rateLimited: "Слишком часто. Попробуйте через минуту.",
    tooLong: "Слишком длинный комментарий.",
    sortNew: "Сначала новые",
    sortOld: "Сначала старые",
    sortPopular: "Популярные",
    countLabel: "комментариев"
  };

  // ------------------------------------------------------------- telemetry

  /**
   * Events carry shape, never content.
   *
   * The allowlist is explicit rather than a denylist: a new field added to a
   * call site cannot leak by being forgotten here, because it is simply not
   * copied.
   */
  var EVENT_FIELDS = [
    "phase", "ms", "count", "status", "code", "sort", "instance", "version"
  ];

  function emit(state, name, payload) {
    var safe = { event: name, version: MODULE_VERSION };
    var source = payload || {};
    EVENT_FIELDS.forEach(function (field) {
      if (Object.prototype.hasOwnProperty.call(source, field)) {
        safe[field] = source[field];
      }
    });
    try {
      state.config.onEvent(safe);
    } catch (_ignored) {
      // Telemetry must never break the widget that produces it.
    }
  }

  // ----------------------------------------------------------------- http

  function request(state, method, path, body) {
    var url = state.config.apiBase + "/api/comments/" + API_VERSION + path;
    var headers = { Accept: "application/json" };
    if (body) headers["Content-Type"] = "application/json";
    var csrf = state.config.csrfToken || readCookie(state.config.csrfCookie);
    if (csrf) headers[state.config.csrfHeader] = csrf;

    var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    if (controller) state.pending.push(controller);

    var started = Date.now();
    return fetch(url, {
      method: method,
      headers: headers,
      credentials: "include",
      body: body ? JSON.stringify(body) : undefined,
      signal: controller ? controller.signal : undefined
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            emit(state, "api", {
              phase: method,
              ms: Date.now() - started,
              status: response.status
            });
            if (!response.ok) {
              var err = new Error("api");
              err.status = response.status;
              err.code = (data.error && data.error.code) || "Unknown";
              err.retryAfter = (data.error && data.error.retry_after_seconds) || 0;
              throw err;
            }
            return data;
          });
      });
  }

  // ------------------------------------------------------------ rendering

  function renderComment(state, item) {
    var body = el("div", { class: "cp-comment__body" });
    // The server sends HTML that it escaped and rebuilt from the author's
    // plain text. It is the one value here that is inserted as markup, and it
    // is safe by construction on that side — see sanitize.render_html.
    body.innerHTML = item.body_html || "";

    var article = el("article", {
      class: "cp-comment" + (item.is_own ? " cp-comment--own" : ""),
      id: item.anchor || "comment-" + item.comment_id,
      "data-cp-id": item.comment_id,
      "data-cp-depth": item.depth || 0,
      // Indent by depth through a custom property rather than inline margins,
      // so the stylesheet keeps control of the scale at narrow widths.
      style: "--cp-depth:" + (item.depth || 0)
    });

    var header = el("header", { class: "cp-comment__head" }, [
      el("span", { class: "cp-comment__author", text: (item.author && item.author.subject_id) || "" }),
      el("time", {
        class: "cp-comment__time",
        datetime: item.created_at || "",
        text: formatTime(item.created_at, state.config.locale)
      })
    ]);

    if (item.state && item.state !== "published" && item.state !== "restored") {
      header.appendChild(
        el("span", {
          class: "cp-comment__status",
          "data-cp-state": item.state,
          text: state.config.strings.pending
        })
      );
    }

    var footer = el("footer", { class: "cp-comment__meta" }, [
      el("span", {
        class: "cp-comment__reactions",
        text: String(item.reaction_count || 0)
      })
    ]);

    article.appendChild(header);
    article.appendChild(body);
    article.appendChild(footer);
    return article;
  }

  function formatTime(iso, locale) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString(locale);
    } catch (_ignored) {
      return iso;
    }
  }

  /**
   * Show or hide the composing surface, on the server's word alone.
   *
   * `canWrite` comes from the thread response. There is no client-side
   * inference and no default of true: an unanswered or failed request leaves
   * the form off, which is the safe direction.
   */
  function setWritable(state, canWrite) {
    var slot = state.nodes.formSlot;
    if (!slot) return;
    var shouldShow = !!canWrite && !state.config.readOnly;
    var attached = slot.firstChild === state.nodes.form;
    if (shouldShow && !attached) {
      slot.appendChild(state.nodes.form);
      var draft = restoreDraft(state);
      if (draft) state.nodes.textarea.value = draft;
    } else if (!shouldShow && attached) {
      slot.removeChild(state.nodes.form);
    }
  }

  function setStatus(state, kind, message) {
    var box = state.nodes.status;
    box.textContent = message || "";
    box.setAttribute("data-cp-status", kind);
    // A live region, so a screen reader hears "sent, awaiting moderation"
    // rather than silently receiving a DOM change nobody announced.
    box.hidden = !message;
  }

  /** Put the widget on the page, once, when we know it belongs there. */
  function reveal(state) {
    if (!state.nodes.pendingContainer) return;
    state.nodes.root.appendChild(state.nodes.pendingContainer);
    state.nodes.pendingContainer = null;
  }

  /** Leave the page untouched: this caller gets no comments at all. */
  function stayHidden(state) {
    if (state.nodes.container && state.nodes.container.parentNode) {
      state.nodes.container.parentNode.removeChild(state.nodes.container);
      state.nodes.pendingContainer = state.nodes.container;
    }
  }

  function renderList(state, items, append) {
    var list = state.nodes.list;
    if (!append) list.textContent = "";
    items.forEach(function (item) {
      list.appendChild(renderComment(state, item));
    });
    state.nodes.empty.hidden = list.children.length !== 0;
  }

  /**
   * Occupy the space the thread is about to need, before the fetch returns.
   *
   * Without this the container starts at zero height and then expands, which
   * measured at CLS 0.45 in the harness — the whole page below the widget
   * jumped by about 300px. Per-comment `min-height` was not enough on its own:
   * it reserves each row once a row exists, and before the response there are
   * no rows at all.
   *
   * The placeholders are `aria-hidden` and carry no text: a screen reader
   * should hear the status message, not three empty articles.
   */
  function renderSkeleton(state, rows) {
    var list = state.nodes.list;
    list.textContent = "";
    for (var i = 0; i < rows; i += 1) {
      list.appendChild(
        el("div", { class: "cp-skeleton", "aria-hidden": "true" })
      );
    }
    state.nodes.empty.hidden = true;
  }

  // -------------------------------------------------------------- loading

  function load(state, append) {
    var query =
      "?resource_type=" + encodeURIComponent(state.config.resourceType) +
      "&canonical_content_id=" + encodeURIComponent(state.config.canonicalContentId) +
      "&sort=" + encodeURIComponent(state.sort) +
      "&limit=" + state.config.pageSize +
      (append && state.cursor ? "&cursor=" + encodeURIComponent(state.cursor) : "");

    state.nodes.root.setAttribute("data-cp-loading", "1");
    if (!append) {
      setStatus(state, "loading", state.config.strings.loading);
      // Only when the list is empty. Replacing already-rendered comments with
      // placeholders on a sort change would be a worse shift than the one this
      // avoids, and would blank content the reader was looking at.
      if (state.nodes.list.children.length === 0) {
        renderSkeleton(state, Math.min(state.config.pageSize, 3));
      }
    }

    return request(state, "GET", "/threads" + query)
      .then(function (data) {
        state.cursor = data.next_cursor || "";
        reveal(state);
        setWritable(state, data.can_write);
        state.nodes.more.hidden = !data.has_more;
        renderList(state, data.items || [], append);
        state.nodes.count.textContent = String(data.total_count || 0);
        setStatus(state, "ok", "");
        emit(state, "ready", { count: (data.items || []).length, sort: state.sort });
      })
      .catch(function (err) {
        // The page keeps working. That is the whole contract of this branch.
        // A failed read tells us nothing about write permission, so the form
        // stays off rather than being left over from a previous answer.
        setWritable(state, false);

        // 503 is the designed answer for "comments are not enabled for you".
        // It is not an error to show a reader — it is the site as it is, and
        // the widget withdraws rather than leaving a notice behind.
        if (err && err.status === 503) {
          stayHidden(state);
          emit(state, "not_enabled", { status: 503 });
          return;
        }
        reveal(state);
        var offline = typeof navigator !== "undefined" && navigator.onLine === false;
        setStatus(
          state,
          offline ? "offline" : "error",
          offline ? state.config.strings.offline : state.config.strings.error
        );
        state.nodes.retry.hidden = false;
        emit(state, "error", { code: (err && err.code) || "Network", status: (err && err.status) || 0 });
      })
      .then(function () {
        state.nodes.root.removeAttribute("data-cp-loading");
      });
  }

  // ------------------------------------------------------------ composing

  function submit(state) {
    var textarea = state.nodes.textarea;
    var value = textarea.value;
    if (!value.trim()) return Promise.resolve();

    state.nodes.submit.disabled = true;
    setStatus(state, "sending", state.config.strings.loading);

    return request(state, "POST", "/comments", {
      resource_type: state.config.resourceType,
      canonical_content_id: state.config.canonicalContentId,
      body: value
    })
      .then(function (data) {
        // Only clear the box once the server has the text. Wiping it on submit
        // and then failing loses what somebody wrote, which is the single most
        // enraging bug this kind of widget can have.
        textarea.value = "";
        saveDraft(state, "");
        var held = !!(data.moderation && data.moderation.held);
        // Refresh first, *then* say what happened. Setting the notice before
        // the reload meant `load` overwrote it with its own status a moment
        // later, so an author whose comment went to the queue was told nothing
        // at all — they saw an unchanged list and assumed the site ate it.
        return load(state, false).then(function () {
          setStatus(state, held ? "pending" : "ok", held ? state.config.strings.pending : "");
        });
      })
      .catch(function (err) {
        var message = state.config.strings.error;
        if (err && err.status === 429) message = state.config.strings.rateLimited;
        if (err && err.code === "ValidationFailed") message = state.config.strings.tooLong;
        if (err && err.code === "PolicyViolation") message = state.config.strings.error;
        setStatus(state, "error", message);
        // The text stays in the box, and stays in the draft.
        emit(state, "submit_error", { code: (err && err.code) || "Network" });
      })
      .then(function () {
        state.nodes.submit.disabled = false;
      });
  }

  function draftKey(state) {
    return "cp:draft:" + state.config.resourceType + ":" + state.config.canonicalContentId;
  }

  function saveDraft(state, value) {
    try {
      if (value) {
        localStorage.setItem(draftKey(state), value);
      } else {
        localStorage.removeItem(draftKey(state));
      }
    } catch (_ignored) {
      // Private mode, blocked storage, quota. A lost draft is a small loss;
      // a thrown exception here would be a broken page.
    }
  }

  function restoreDraft(state) {
    try {
      return localStorage.getItem(draftKey(state)) || "";
    } catch (_ignored) {
      return "";
    }
  }

  // ------------------------------------------------------------- spoilers

  function bindSpoilers(root, strings) {
    root.addEventListener("click", function (event) {
      var spoiler = event.target.closest("[data-cp-spoiler]");
      if (!spoiler) return;
      toggleSpoiler(spoiler, strings);
    });
    root.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      var spoiler = event.target.closest("[data-cp-spoiler]");
      if (!spoiler) return;
      // Space scrolls the page by default; a control that swallows it must
      // actually do something in exchange.
      event.preventDefault();
      toggleSpoiler(spoiler, strings);
    });
  }

  function toggleSpoiler(spoiler, strings) {
    var open = spoiler.getAttribute("aria-expanded") === "true";
    spoiler.setAttribute("aria-expanded", open ? "false" : "true");
    spoiler.setAttribute("aria-label", open ? strings.spoilerShow : strings.spoilerHide);
  }

  // ---------------------------------------------------------------- build

  function build(state) {
    var strings = state.config.strings;
    var root = state.nodes.root;

    var heading = el("h2", { class: "cp-heading", id: state.ids.heading }, [
      el("span", { text: strings.heading + " " }),
      el("span", { class: "cp-count", id: state.ids.count, text: "0" })
    ]);

    var sortControl = el("div", { class: "cp-sort", role: "group", "aria-label": strings.heading });
    [["new", strings.sortNew], ["old", strings.sortOld], ["popular", strings.sortPopular]].forEach(
      function (pair) {
        var button = el("button", {
          type: "button",
          class: "cp-sort__button",
          "data-cp-sort": pair[0],
          "aria-pressed": pair[0] === state.sort ? "true" : "false",
          text: pair[1]
        });
        sortControl.appendChild(button);
      }
    );

    var status = el("p", {
      class: "cp-status",
      id: state.ids.status,
      role: "status",
      "aria-live": "polite",
      hidden: "hidden"
    });

    var list = el("div", {
      class: "cp-list",
      id: state.ids.list,
      "aria-labelledby": state.ids.heading
    });
    var empty = el("p", { class: "cp-empty", text: strings.empty, hidden: "hidden" });
    var more = el("button", {
      type: "button",
      class: "cp-more",
      text: strings.more,
      hidden: "hidden"
    });
    var retry = el("button", {
      type: "button",
      class: "cp-retry",
      text: strings.retry,
      hidden: "hidden"
    });

    var textarea = el("textarea", {
      class: "cp-form__input",
      id: state.ids.textarea,
      rows: "3",
      maxlength: String(state.config.maxLength),
      placeholder: strings.placeholder,
      "aria-describedby": state.ids.status
    });
    var label = el("label", {
      class: "cp-form__label",
      for: state.ids.textarea,
      text: strings.placeholder
    });
    var submitButton = el("button", { type: "submit", class: "cp-form__submit", text: strings.submit });
    var form = el("form", { class: "cp-form", novalidate: "novalidate" }, [
      label,
      textarea,
      el("div", { class: "cp-form__actions" }, [submitButton])
    ]);

    // The compose form sits above the thread, not below it. That is partly a
    // convention readers already know from large sites, and partly measured:
    // with the form underneath, every growth of the list moved it, which was
    // the largest single layout shift in this widget (0.118 of a total 0.197).
    // A control that walks down the page while you are reaching for it is a
    // worse problem than an unconventional order.
    //
    // It is NOT attached here. The server decides who may write, and until it
    // has said so the widget offers no writing surface at all. Building the
    // box first and discovering on submit that the answer is no shows a
    // visitor an invitation the site never meant to extend — which is exactly
    // what an owner-only pilot must not do.
    var children = [heading, sortControl, status, list, empty, more, retry];

    var formSlot = el("div", { class: "cp-form-slot" });
    // Third child: immediately after the status line, above the list.
    children.splice(3, 0, formSlot);

    var container = el("section", {
      class: "cp-widget",
      "data-cp-theme": state.config.theme,
      lang: state.config.locale
    }, children);

    // Server-rendered comments, if any, are adopted rather than discarded.
    var prerendered = root.querySelector(".cp-thread");
    if (prerendered) {
      Array.prototype.slice.call(prerendered.children).forEach(function (child) {
        list.appendChild(child);
      });
      prerendered.remove();
    }

    // Not appended yet. Nothing of the widget reaches the page until the
    // server has said what this caller may see. For an ordinary visitor
    // during an owner-only pilot the answer is "nothing", and the page must
    // then look exactly as it does without comments — no container, no
    // notice, no reserved gap. That requirement outranks the layout-shift
    // reservation this code used to make, which only ever helped the one
    // person who can see the widget.
    state.nodes.pendingContainer = container;

    // Except when the server already rendered comments into the page. SSR is
    // the server saying "these belong here"; holding them back until a fetch
    // returns would blank content that was readable a moment ago, including
    // for a reader with no JavaScript at all.
    state.hadPrerendered = !!prerendered;

    Object.assign(state.nodes, {
      container: container,
      list: list,
      empty: empty,
      more: more,
      retry: retry,
      status: status,
      count: heading.querySelector(".cp-count"),
      form: form,
      formSlot: formSlot,
      textarea: textarea,
      submit: submitButton,
      sort: sortControl
    });

    empty.hidden = list.children.length !== 0;
    if (state.hadPrerendered) reveal(state);
  }

  function bind(state) {
    var handlers = [];

    function on(node, type, handler, options) {
      node.addEventListener(type, handler, options);
      handlers.push(function () {
        node.removeEventListener(type, handler, options);
      });
    }

    on(state.nodes.sort, "click", function (event) {
      var button = event.target.closest("[data-cp-sort]");
      if (!button) return;
      state.sort = button.getAttribute("data-cp-sort");
      state.cursor = "";
      Array.prototype.forEach.call(state.nodes.sort.children, function (child) {
        child.setAttribute(
          "aria-pressed",
          child.getAttribute("data-cp-sort") === state.sort ? "true" : "false"
        );
      });
      load(state, false);
    });

    on(state.nodes.more, "click", function () {
      load(state, true);
    });
    on(state.nodes.retry, "click", function () {
      state.nodes.retry.hidden = true;
      load(state, false);
    });

    if (state.nodes.form) {
      on(state.nodes.form, "submit", function (event) {
        event.preventDefault();
        submit(state);
      });
      on(
        state.nodes.textarea,
        "input",
        debounce(function () {
          saveDraft(state, state.nodes.textarea.value);
        }, 400)
      );
    }

    bindSpoilers(state.nodes.container, state.config.strings);
    state.teardown = handlers;
  }

  // ------------------------------------------------------------------ api

  var counter = 0;

  function mount(rootOrSelector, rawConfig) {
    var root =
      typeof rootOrSelector === "string"
        ? document.querySelector(rootOrSelector)
        : rootOrSelector;
    if (!root) throw new Error("comments: mount target not found");

    // Idempotent: mounting an already-mounted node returns the live instance
    // rather than stacking a second widget on top of the first.
    var existing = instances.get(root);
    if (existing) return existing.handle;

    var id = ++counter;
    var state = {
      config: normaliseConfig(rawConfig),
      sort: (rawConfig && rawConfig.sort) || "new",
      cursor: "",
      pending: [],
      teardown: [],
      nodes: { root: root },
      ids: {
        heading: "cp-h-" + id,
        count: "cp-n-" + id,
        list: "cp-l-" + id,
        status: "cp-s-" + id,
        textarea: "cp-t-" + id
      }
    };

    build(state);
    bind(state);

    var handle = {
      version: MODULE_VERSION,
      update: guard(function (patch) {
        Object.assign(state.config, normaliseConfig(Object.assign({}, state.config, patch || {})));
        state.cursor = "";
        return load(state, false);
      }),
      reload: guard(function () {
        state.cursor = "";
        return load(state, false);
      }),
      destroy: guard(function () {
        // Idempotent: a second destroy finds nothing registered and returns.
        if (!instances.has(root)) return;
        state.pending.forEach(function (controller) {
          try {
            controller.abort();
          } catch (_ignored) {
            noop();
          }
        });
        state.teardown.forEach(function (off) {
          off();
        });
        if (state.nodes.container && state.nodes.container.parentNode === root) {
          root.removeChild(state.nodes.container);
        }
        instances.delete(root);
      })
    };

    instances.set(root, { state: state, handle: handle });
    load(state, false);
    return handle;
  }

  function mountAll(selector, config) {
    var found = document.querySelectorAll(selector || "[data-cp-comments]");
    return Array.prototype.map.call(found, function (node) {
      var perNode = Object.assign({}, config);
      // Each root carries its own content reference, so several discussions on
      // one page stay independent.
      if (node.dataset.cpResourceType) perNode.resourceType = node.dataset.cpResourceType;
      if (node.dataset.cpContentId) perNode.canonicalContentId = node.dataset.cpContentId;
      return mount(node, perNode);
    });
  }

  global.SiteFactoryComments = {
    version: MODULE_VERSION,
    apiVersion: API_VERSION,
    mount: guard(mount),
    mountAll: guard(mountAll),
    // Exposed for tests; not part of the integration contract.
    _internals: { normaliseConfig: normaliseConfig, EVENT_FIELDS: EVENT_FIELDS }
  };
})(typeof window !== "undefined" ? window : this);
