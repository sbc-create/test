set -u
# Прогон списка проверок с ПАУЗОЙ на ближайший такт :x0/:x5 после каждых двух
# стендов. Повод измеренный: шлюз фонового редактора соседней линии не
# стартовал четыре такта подряд, потому что мои стенды шли подряд по ~4 минуты
# и перекрывали каждый такт. Просьба соседней линии 28.10: не дожидаться её
# просьбы, а ставить паузу самому.
s=/tmp/claude-1001/-home-claude-wt-nova-publish-memory-02/c1416a86-4527-43b4-94e6-35e0f08a27d0/scratchpad
repo="$1"; shift
pause_after=2
done_count=0
pause_to_tick() {
  python3 /home/claude/wt-nova-publish-memory-02/automation/host/_orphan_stands.py >/dev/null 2>&1 || true
  mem=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  now_min=$(date -u +%M)
  rest=$((now_min % 5))
  target=$(( (now_min - rest + 5 + 1) % 60 ))
  printf 'ПАУЗА: свободно %s МиБ, стенд не поднимается до :%02d (такт :%02d)\n' "$mem" "$target" "$(( (target + 59) % 60 ))"
  # Окно объявляется открытым только по ЧИСЛУ. Измерено 28.10: останов снял
  # стенды, а оставшаяся проверка держала 551 МиБ, и при 1982 МиБ против порога
  # 2048 шлюз соседней линии не стартовал — а я доложил окно открытым.
  if [ "$mem" -lt 2048 ]; then
    printf 'ПАУЗА: свободно %s МиБ — НИЖЕ порога 2048, окно ложное; ищу, кто держит\n' "$mem"
    python3 /home/claude/wt-nova-publish-memory-02/automation/host/_orphan_stands.py --list 2>&1 | head -6
  fi
  while [ "$(date -u +%M)" != "$(printf '%02d' "$target")" ]; do sleep 5; done
  printf 'ПАУЗА: такт пройден в %sZ\n' "$(date -u +%H:%M:%S)"
}
cd /home/claude/wt-nova-publish-memory-02
for name in "$@"; do
  python3 automation/host/apply-animedia-data-dir-codes.py --repo "var/site-repos/$repo" --only "$name"
  done_count=$((done_count + 1))
  if [ "$done_count" -lt "$#" ] && [ $((done_count % pause_after)) -eq 0 ]; then
    pause_to_tick
  fi
done
echo "ЭТАП с паузами завершён: $repo, проверок $done_count"
