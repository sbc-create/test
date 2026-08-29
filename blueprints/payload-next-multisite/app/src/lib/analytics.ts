/* Сгенерировано `python3 -m factory analytics codegen` из factory/analytics/events.py.
 * Руками не редактируется: правка теряется при следующей генерации, а описание
 * событий и цели Метрики разойдутся. Меняй events.py и перегенерируй. */

export type AnalyticsEventId =
  | 'search'
  | 'filter_apply'
  | 'title_view'
  | 'season_select'
  | 'episode_select'
  | 'player_start'
  | 'player_ready'
  | 'player_error'
  | 'comment_submit';

export interface AnalyticsEventParams {
  'search': {
    /** Сколько нашлось, интервалом */
    results_bucket?: 'none' | '1-10' | '11-50' | '51+';
    /** Откуда запущен поиск */
    source?: 'header' | 'page' | 'suggest';
  };
  'filter_apply': {
    /** Какой фильтр применён */
    filter_name?: 'genre' | 'year' | 'status' | 'season' | 'voice' | 'sort';
    /** Сколько значений выбрано */
    value_count?: number;
  };
  'title_view': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Слаг раздела каталога */
    category?: string;
  };
  'season_select': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Номер сезона */
    season_number?: number;
  };
  'episode_select': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Номер сезона */
    season_number?: number;
    /** Номер серии */
    episode_number?: number;
  };
  'player_start': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Технический идентификатор эпизода */
    episode_id?: string;
    /** Какой плеер встроен */
    player?: 'vk_white' | 'cdnvideohub' | 'unavailable';
  };
  'player_ready': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Технический идентификатор эпизода */
    episode_id?: string;
    /** Какой плеер встроен */
    player?: 'vk_white' | 'cdnvideohub' | 'unavailable';
  };
  'player_error': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Технический идентификатор эпизода */
    episode_id?: string;
    /** Категория ошибки */
    error_code?: 'no_data' | 'rights_missing' | 'network' | 'decode' | 'timeout' | 'unknown';
  };
  'comment_submit': {
    /** Технический идентификатор тайтла из каталога пакета */
    title_id?: string;
    /** Длина комментария интервалом */
    length_bucket?: 'short' | 'medium' | 'long';
  };
}

export interface AnalyticsConfig {
  counterId: number;
  allowedHosts: string[];
  environment: string;
  collectionAuthorized?: boolean;
  enabled: boolean;
}

export interface AnalyticsVerdict {
  active: boolean;
  reason: string;
}

const EVENT_SPEC: Record<string, Record<string, any>> = {
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

const FORBIDDEN: string[] = ["access_token", "api_key", "body", "comment", "comment_text", "cookie", "e_mail", "email", "ip", "keyword", "login", "mail", "message", "name", "nickname", "oauth", "password", "phone", "publisher_id", "publisherid", "q", "query", "search_query", "secret", "session", "tel", "text", "token", "uid", "user_id", "user_name", "username"];

export function sanitize(eventId: string, params?: Record<string, unknown>)
    : Record<string, string | number | boolean> | null {
  const out: Record<string, string | number | boolean> = {};
  const spec = EVENT_SPEC[eventId];
  if (!spec) { return null; }
  if (!params) { return out; }
  for (const key of Object.keys(params)) {
    const lower = key.toLowerCase();
    // Запрещённое имя отбрасывается до сверки со списком разрешённых:
    // список разрешённых когда-нибудь расширят по ошибке, этот — нет.
    if (FORBIDDEN.indexOf(lower) !== -1) { continue; }
    const rule = spec[key];
    if (!rule) { continue; }
    const value = params[key];
    if (rule.kind === 'enum') {
      if (rule.values.indexOf(String(value)) === -1) { continue; }
      out[key] = String(value);
    } else if (rule.kind === 'int') {
      const num = parseInt(String(value), 10);
      if (!isFinite(num)) { continue; }
      out[key] = num;
    } else if (rule.kind === 'bool') {
      out[key] = value === true || value === 'true';
    } else if (rule.kind === 'id') {
      const id = String(value);
      // Идентификатор — это слаг или число. Всё, что похоже на текст, адрес
      // или произвольную строку, идентификатором не является и не отправляется.
      if (!/^[A-Za-z0-9_-]+$/.test(id) || id.length > rule.maxLength) { continue; }
      out[key] = id;
    }
  }
  return out;
}

/** Решение принимается до загрузки тега: выключено — значит не загружаем. */
export function decide(config: AnalyticsConfig | null, hostname: string): AnalyticsVerdict {
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

declare global {
  interface Window { ym?: (...args: unknown[]) => void }
}

let verdict: AnalyticsVerdict = { active: false, reason: 'не инициализирован' };
let counterId = 0;

/** Загружает тег Метрики, но только когда выполнены все условия. */
export function initAnalytics(config: AnalyticsConfig | null, hostname: string): AnalyticsVerdict {
  verdict = decide(config, hostname.toLowerCase());
  if (!verdict.active || !config) { return verdict; }
  counterId = config.counterId;
  (function (m, e, t, r, i, k, a) {
    m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
    m[i].l = 1 * new Date();
    k = e.createElement(t); a = e.getElementsByTagName(t)[0];
    k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
  })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym');
  window.ym!(counterId, 'init', { clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: false });
  return verdict;
}

/** Отправка события. Типы не дают ни назвать чужое событие, ни передать лишнее. */
export function track<E extends AnalyticsEventId>(
  eventId: E,
  params?: AnalyticsEventParams[E],
): boolean {
  if (!verdict.active || typeof window === 'undefined' || !window.ym) { return false; }
  const clean = sanitize(eventId, params as Record<string, unknown> | undefined);
  if (clean === null) { return false; }
  window.ym(counterId, 'reachGoal', eventId, clean);
  return true;
}
