#!/usr/bin/env bash
# Из чего исполняется служба: из неизменяемого артефакта или из рабочего дерева git.
#
# Юнит, чей ExecStart указывает внутрь git-checkout, исполняет то, что там
# сейчас лежит. `git checkout` в этом каталоге молча меняет поведение боевой
# службы: ни выкатки, ни отката, ни записи о работающей версии. Установщик
# unit'ов уже предупреждает об этом словами — «служба запускается и молча
# исполняет чужой код», — но узнать, случилось ли это, было нечем.
#
# Измерено 2026-09-03: три контентных юнита YummyAnime исполнялись из дерева на
# ветке claude/night-yummy-schedule-12, тогда как веб-контейнеры работали с
# образа, собранного из другой ревизии. Расхождение существовало и ничем не
# сообщалось.
#
# Проверка намеренно не чинит и ничего не меняет: она отвечает на вопрос
# «откуда исполняется» и печатает ветку, если ответ — «из дерева».
#
# Аргументы: имена юнитов (`site-factory-backup.service`), строка ExecStart
# целиком или отдельные пути. Имя юнита разрешается через `systemctl cat`.
#
# Имена юнитов принимаются потому, что вызывать проверку хочется именно так.
# Пока принималась только строка ExecStart, вызов с именем юнита не падал, а
# отвечал «ни одного пути в аргументах — проверять нечего» с кодом 0, то есть
# успокаивающе. Поймано 2026-09-04 на site-factory-backup.service: юнит
# исполняется из /srv/site-factory/repo, а проверка отрапортовала, что смотреть
# не на что.
#
# Проверяются ВСЕ похожие на путь аргументы, а не первый. Первый — обычно
# интерпретатор (`/usr/bin/node`, `/usr/bin/python3`), он лежит в /usr/bin и
# всегда выглядит неизменяемым. Смотреть только на него значит выдать
# «из артефакта» для службы, которая исполняет скрипт из рабочего дерева, —
# то есть получить ложно-безопасный ответ. Ровно на этом инструмент и был
# пойман при первом же прогоне на настоящих юнитах.
#
# Код возврата — число путей, ведущих в рабочее дерево git. Отдельно: 64, если
# проверять было нечего, и 65, если юнит не найден. Нулём отвечает только
# настоящая проверка, ничего не нашедшая, — не отказ и не опечатка.
set -uo pipefail

worktree_root() {
  # Ближайший каталог вверх по дереву, содержащий .git. Пусто, если такого нет.
  local dir="$1"
  [ -d "$dir" ] || dir="$(dirname "$dir")"
  while [ "$dir" != "/" ] && [ -n "$dir" ]; do
    if [ -e "$dir/.git" ]; then
      printf '%s' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

strip_modifiers() {
  # systemd допускает перед путём модификаторы: `-` `@` `+` `!` `:`.
  local w="$1"
  while [ -n "$w" ]; do
    case "$w" in
      [-@+!:]*) w="${w#?}" ;;
      *) break ;;
    esac
  done
  printf '%s' "$w"
}

args=()
missing_unit=0
for a in "$@"; do
  case "$a" in
    *.service|*.timer|*.socket|*.path|*.mount|*.target)
      if ! unit_text="$(systemctl cat "$a" 2>/dev/null)" || [ -z "$unit_text" ]; then
        printf 'НЕТ ЮНИТА    %s\n' "$a" >&2
        missing_unit=1
        continue
      fi
      while IFS= read -r line; do
        line="${line#ExecStart=}"
        line="${line#ExecStartPre=}"
        line="${line#ExecStartPost=}"
        for w in $line; do
          args+=("$(strip_modifiers "$w")")
        done
      done < <(printf '%s\n' "$unit_text" | grep -E '^ExecStart(Pre|Post)?=')
      ;;
    *)
      args+=("$a")
      ;;
  esac
done

mutable=0
checked=0
for path in ${args[@]+"${args[@]}"}; do
  # Не-пути (флаги, значения переменных) пропускаем молча: ExecStart содержит
  # и их, а сообщение о каждом утопило бы настоящие находки.
  case "$path" in
    /*) ;;
    *) continue ;;
  esac
  checked=$((checked + 1))
  if [ ! -e "$path" ]; then
    printf 'ОТСУТСТВУЕТ  %s\n' "$path"
    continue
  fi
  if root="$(worktree_root "$path")"; then
    # symbolic-ref знает имя ветки и до первого коммита; rev-parse --abbrev-ref
    # на такой ветке печатает «HEAD» и при этом возвращает ошибку, отчего в
    # вывод попадало и «HEAD», и запасное «?». Отсоединённую голову
    # symbolic-ref не разрешает — там остаётся короткий sha.
    branch="$(git -C "$root" symbolic-ref --short HEAD 2>/dev/null)"
    [ -n "$branch" ] || branch="$(git -C "$root" rev-parse --short HEAD 2>/dev/null)"
    [ -n "$branch" ] || branch="?"
    dirty="$(git -C "$root" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    printf 'ИЗ ДЕРЕВА    %s\n             дерево %s, ветка %s, изменённых файлов %s\n' \
      "$path" "$root" "$branch" "$dirty"
    mutable=$((mutable + 1))
  else
    printf 'ИЗ АРТЕФАКТА %s\n' "$path"
  fi
done

if [ "$missing_unit" -eq 1 ] && [ "$checked" -eq 0 ]; then
  printf 'юнит не найден — проверка не выполнена\n' >&2
  exit 65
fi

if [ "$checked" -eq 0 ]; then
  printf 'ни одного пути в аргументах — проверка не выполнена\n' >&2
  printf 'ожидались имя юнита, строка ExecStart или абсолютные пути\n' >&2
  exit 64
fi

if [ "$mutable" -gt 0 ]; then
  printf '\nслужб, исполняемых из рабочего дерева: %d\n' "$mutable" >&2
  printf 'такая служба меняет поведение при git checkout, без выкатки и без отката\n' >&2
fi
exit "$mutable"
