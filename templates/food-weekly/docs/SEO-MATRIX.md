# SEO-матрица food-weekly

Preview закрыт: `X-Robots-Tag` и мета `noindex, nofollow` на всех ответах, `robots.txt` — `Disallow: /`.
Production — отдельный переключатель, требует домен (сейчас ошибка BLOCKED_INPUT). Проверки — `tests/test_food_weekly.py`.

| тип | пример | title / H1 | canonical | production | sitemap | schema |
| --- | --- | --- | --- | --- | --- | --- |
| главная | `/` | «Меню на неделю — готовые планы и список покупок» | себя | index | да | — |
| каталог меню | `/menyu/` | «Планы меню на неделю» | себя | index | да | BreadcrumbList |
| неделя | `/menyu/bystraya-nedelya-dlya-dvoih/` | название плана | себя | index | да | BreadcrumbList |
| неделя с заменами | `/menyu/…/?s=d1-dinner-0:plov-s-kuricej` | то же | **нет** | noindex, follow; `Disallow: /*?` | нет | BreadcrumbList |
| день | `/menyu/…/den-3/` | «<план>: среда» | себя | index | да | BreadcrumbList |
| список покупок | `/menyu/…/pokupki/` | «Список покупок: <план>» | себя (без замен) | index | да | BreadcrumbList |
| инструкция | `/kak-planirovat/` | «Как пользоваться планом меню» | себя | index | да | BreadcrumbList |
| подборка | `/podborki/supy-dlya-obedov/` | название подборки | себя | index (≥3 блюд, иначе 404) | да | BreadcrumbList |
| 404 | любой неизвестный, `den-8`, неизвестный план | «Страница не найдена» | нет | 404 | нет | — |

Ссылки на рецепты — внешние на сайт food-daily по реестру `config/network.yaml`; копий рецептов
и Recipe-разметки здесь нет (рецепт индексируется на своём сайте). Повторяющиеся дни разных
планов — разные страницы с уникальными title. Рисков дублей с food-daily нет: тексты рецептов не выводятся.
