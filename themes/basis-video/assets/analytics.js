/* Сгенерировано `python3 -m factory analytics codegen` из factory/analytics/events.py.
 * Руками не редактируется: правка теряется при следующей генерации, а описание
 * событий и цели Метрики разойдутся. Меняй events.py и перегенерируй. */
(function () {
  'use strict';

  var EVENT_SPEC = {
  "comment_submit": {
    "length_bucket": {
      "kind": "enum",
      "values": [
        "short",
        "medium",
        "long"
      ]
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  },
  "episode_select": {
    "episode_number": {
      "kind": "int"
    },
    "season_number": {
      "kind": "int"
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  },
  "filter_apply": {
    "filter_name": {
      "kind": "enum",
      "values": [
        "genre",
        "year",
        "status",
        "season",
        "voice",
        "sort"
      ]
    },
    "value_count": {
      "kind": "int"
    }
  },
  "player_error": {
    "episode_id": {
      "kind": "id",
      "maxLength": 64
    },
    "error_code": {
      "kind": "enum",
      "values": [
        "no_data",
        "rights_missing",
        "network",
        "decode",
        "timeout",
        "unknown"
      ]
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  },
  "player_ready": {
    "episode_id": {
      "kind": "id",
      "maxLength": 64
    },
    "player": {
      "kind": "enum",
      "values": [
        "vk_white",
        "cdnvideohub",
        "unavailable"
      ]
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  },
  "player_start": {
    "episode_id": {
      "kind": "id",
      "maxLength": 64
    },
    "player": {
      "kind": "enum",
      "values": [
        "vk_white",
        "cdnvideohub",
        "unavailable"
      ]
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  },
  "search": {
    "results_bucket": {
      "kind": "enum",
      "values": [
        "none",
        "1-10",
        "11-50",
        "51+"
      ]
    },
    "source": {
      "kind": "enum",
      "values": [
        "header",
        "page",
        "suggest"
      ]
    }
  },
  "season_select": {
    "season_number": {
      "kind": "int"
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  },
  "title_view": {
    "category": {
      "kind": "id",
      "maxLength": 64
    },
    "title_id": {
      "kind": "id",
      "maxLength": 64
    }
  }
};

  var FORBIDDEN = ["access_token", "api_key", "body", "comment", "comment_text", "cookie", "e_mail", "email", "ip", "keyword", "login", "mail", "message", "name", "nickname", "oauth", "password", "phone", "publisher_id", "publisherid", "q", "query", "search_query", "secret", "session", "tel", "text", "token", "uid", "user_id", "user_name", "username"];

  function sanitize(eventId, params) {
  var out = {};
  var spec = EVENT_SPEC[eventId];
  if (!spec) { return null; }
  if (!params) { return out; }
  for (var key in params) {
    if (!Object.prototype.hasOwnProperty.call(params, key)) { continue; }
    var lower = String(key).toLowerCase();
    // Запрещённое имя отбрасывается до сверки со списком разрешённых:
    // список разрешённых когда-нибудь расширят по ошибке, этот — нет.
    if (FORBIDDEN.indexOf(lower) !== -1) { continue; }
    var rule = spec[key];
    if (!rule) { continue; }
    var value = params[key];
    if (rule.kind === 'enum') {
      if (rule.values.indexOf(String(value)) === -1) { continue; }
      out[key] = String(value);
    } else if (rule.kind === 'int') {
      var num = parseInt(value, 10);
      if (!isFinite(num)) { continue; }
      out[key] = num;
    } else if (rule.kind === 'bool') {
      out[key] = value === true || value === 'true';
    } else if (rule.kind === 'id') {
      var id = String(value);
      // Идентификатор — это слаг или число. Всё, что похоже на текст, адрес
      // или произвольную строку, идентификатором не является и не отправляется.
      if (!/^[A-Za-z0-9_-]+$/.test(id) || id.length > rule.maxLength) { continue; }
      out[key] = id;
    }
  }
  return out;
  }

  function decide(config, hostname) {
  if (!config) { return { active: false, reason: 'нет конфигурации' }; }
  if (config.enabled === false) { return { active: false, reason: 'ANALYTICS_ENABLED=false' }; }
  if (!config.counterId) { return { active: false, reason: 'counter ID не задан' }; }
  if (config.environment !== 'production' && !config.collectionAuthorized) {
    return { active: false, reason: 'окружение ' + config.environment + ', сбор не разрешён' };
  }
  if (!config.allowedHosts || config.allowedHosts.length === 0) {
    return { active: false, reason: 'список разрешённых hostname пуст' };
  }
  if (config.allowedHosts.indexOf(hostname) === -1) {
    return { active: false, reason: 'hostname ' + hostname + ' не совпал с разрешённым' };
  }
  return { active: true, reason: 'разрешено' };
  }

  function readConfig() {
    var el = document.currentScript || document.querySelector('script[data-analytics-provider]');
    if (!el) { return null; }
    var hosts = (el.getAttribute('data-allowed-hosts') || '').split(',')
      .map(function (h) { return h.trim().toLowerCase(); })
      .filter(Boolean);
    return {
      counterId: parseInt(el.getAttribute('data-counter-id') || '', 10) || 0,
      allowedHosts: hosts,
      environment: el.getAttribute('data-environment') || 'staging',
      collectionAuthorized: el.getAttribute('data-collection-authorized') === 'true',
      enabled: el.getAttribute('data-analytics-enabled') !== 'false'
    };
  }

  var config = readConfig();
  var verdict = decide(config, (window.location.hostname || '').toLowerCase());

  // Публичный интерфейс существует всегда: страницы вызывают track() без
  // проверок, и в выключенном состоянии он обязан молча ничего не делать.
  window.siteAnalytics = {
    active: verdict.active,
    reason: verdict.reason,
    track: function (eventId, params) {
      if (!verdict.active) { return false; }
      var clean = sanitize(eventId, params);
      if (clean === null) { return false; }
      window.ym(config.counterId, 'reachGoal', eventId, clean);
      return true;
    }
  };

  if (!verdict.active) {
    // Тег не загружается вовсе: на staging в странице нет ни одного запроса
    // к Метрике, а не «загрузились и не отправляем».
    return;
  }

  (function (m, e, t, r, i, k, a) {
    m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
    m[i].l = 1 * new Date();
    k = e.createElement(t); a = e.getElementsByTagName(t)[0];
    k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
  })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym');

  window.ym(config.counterId, 'init', { clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: false });
})();
