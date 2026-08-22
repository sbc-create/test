# Backtests

Каждый файл — проверка паттерна на исторических экспериментах **вне** обучающего набора
(`learning/registry.py: backtest`). Вердикты: `holds`, `unstable`, `contradicted`,
`insufficient_data`.

Пусто: исторических экспериментов нет.
