# poster-above-placeholder-1lordserials1-online.patch

Заготовка правки, сохранённая как `.md`, а не `.patch`: файлы `.patch` в
репозитории запрещены (`tests/unit/test_repo_hygiene.py::test_no_dle_core_patches`,
смысл запрета — «ядро DLE не модифицируется, в репозитории нет ни патчей, ни
копий ядра»). Содержимое ниже — дословное, применяется обычным
`git apply`/`patch -p1` после извлечения блока.

```diff
From 72dbfebf2a2a2b252b0976d9697f4befc7ca0f07 Mon Sep 17 00:00:00 2001
From: sbc-create <319062147+sbc-create@users.noreply.github.com>
Date: Sat, 17 Oct 2026 20:23:25 +0000
Subject: [PATCH] =?UTF-8?q?=D0=BF=D0=BE=D1=81=D1=82=D0=B5=D1=80=20=D1=80?=
 =?UTF-8?q?=D0=B8=D1=81=D1=83=D0=B5=D1=82=D1=81=D1=8F=20=D0=BF=D0=BE=D0=B2?=
 =?UTF-8?q?=D0=B5=D1=80=D1=85=20=D0=B1=D1=83=D0=BA=D0=B2=D1=8B-=D0=B7?=
 =?UTF-8?q?=D0=B0=D0=B3=D0=BB=D1=83=D1=88=D0=BA=D0=B8?=
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit

Буква-заглушка позиционирована и по правилам наложения рисовалась поверх
непозиционированной картинки, даже стоя раньше в разметке. Измерено
2026-10-17 на живой витрине: заглушка видна поверх загруженного постера.

Та же причина и та же правка, что уже выпущены на восьми витринах партии K2.
Заглушка остаётся под картинкой и показывается только когда картинки нет.

Проверено до выпуска: у всех правил картинки карточки есть подъём, заглушка
по-прежнему позиционирована (иначе проверка потеряла бы смысл).
---
 overlay/assets.py | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/overlay/assets.py b/overlay/assets.py
index afeeafc..1dd3f92 100644
--- a/overlay/assets.py
+++ b/overlay/assets.py
@@ -265,7 +265,11 @@ border-radius:4px;overflow:hidden;height:100%;color:inherit}
 .nsc:focus-visible{outline:3px solid var(--s-acc);outline-offset:2px}
 .nsc__p{display:block;position:relative;aspect-ratio:2/3;overflow:hidden;
 background:linear-gradient(160deg,var(--s-ph1),var(--s-ph2));flex:0 0 auto}
-.nsc__p img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
+/* position:relative;z-index:1 обязателен: заглушка .nsc__ph
+   позиционирована и по правилам наложения рисуется поверх
+   непозиционированной картинки. Без этой строки буква видна поверх
+   загруженного постера — измерено 2026-10-17 на живой витрине. */
+.nsc__p img{position:relative;z-index:1;width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
 .nsc__ph{position:absolute;inset:0;display:grid;place-items:center;padding:8px;
 text-align:center;color:var(--s-phink);font-size:22px;font-weight:800}
 .nsc__tag{position:absolute;z-index:2;top:6px;left:6px;background:var(--s-accfill);color:#fff;
-- 
2.34.1

```
