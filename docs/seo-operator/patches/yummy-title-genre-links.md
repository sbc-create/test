# Yummy: жанры в карточке — ссылки на разделы жанров (подготовлено 2026-10-11)

Проект: `sbc-create/yummyani` (Next.js), база — `origin/claude/yummy-actual-shelf-01`
(самая свежая ветка; какой коммит собран в живой образ, из сессии SEO не видно).
Из сессии SEO клонировать проект не разрешено профилем прав — правку должен
внести владелец конвейера Yummy.

## Что не так (проверено на живых страницах 11.10)

`https://yummyani.site/anime/proschay-lara`: «Жанры: Фэнтези, Романтика, Аниме» —
простой текст (`MetaRow` в `src/components/catalog/title-page-view.tsx`,
`title.genres.join(", ")`). То же на yummyani.org/.biz/7.site/7.info. Разделы
`/catalog/genre/<slug>` существуют (200, H1 «Аниме в жанре «Боевик»», 24
карточки) — переход из карточки в раздел жанра невозможен.

Политику индексации разделов (`isGenreLandingIndexable`, курируемый список
`CURATED_LANDING_ALLOWLIST`) правка не меняет: закрытые разделы остаются
`noindex, follow`, но становятся достижимы обычной ссылкой.

## Правка

```tsx
// src/components/catalog/title-page-view.tsx
import Link from "next/link";
import { Fragment } from "react";
import { canonicalGenreSlug, isCanonicalKnownSlug } from "@/modules/catalog/genre-canonical";

function GenreRow({ genres }: { genres: readonly string[] }) {
  if (!genres.length) {
    return null;
  }
  return (
    <li>
      <span>Жанры:</span>{" "}
      {genres.map((genre, index) => {
        const slug = canonicalGenreSlug(genre);
        return (
          <Fragment key={genre}>
            {index ? ", " : ""}
            {slug && isCanonicalKnownSlug(slug) ? (
              <Link href={`/catalog/genre/${slug}`}>{genre}</Link>
            ) : (
              genre
            )}
          </Fragment>
        );
      })}
    </li>
  );
}

// вместо
// <MetaRow label="Жанры:" value={title?.genres.length ? title.genres.join(", ") : null} />
<GenreRow genres={title?.genres ?? []} />
```

Регрессия (Playwright/unit, по принятому в проекте): на странице произведения с
жанром «Боевик» есть `<a href="/catalog/genre/action">`; переход открывает
раздел с H1 «Аниме в жанре «Боевик»» и карточками; из раздела карточка ведёт
на `/anime/<slug>`. Неизвестный ярлык остаётся текстом.
