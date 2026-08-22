'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { PLAYER_ELEMENT, type PlayerAttributes } from '../player/contract'

/**
 * Прямое встраивание <video-player> — без iframe и без обёрток чужого сайта.
 *
 * Скрипт подключается один раз на страницу. Событие noData из контракта
 * переводит блок в состояние «серия недоступна»: подменять недоступное видео
 * другим запрещено, поэтому вместо плеера показывается честный статус.
 *
 * Кнопка «Повторить» меняет ключ монтирования: элемент пересоздаётся и загрузка
 * повторяется. Снять текст ошибки, не перезапустив плеер, — это имитация retry,
 * а не retry.
 */
export const Player = ({
  attributes,
  scriptUrl,
  season,
  episode,
  unavailableText,
}: {
  attributes: PlayerAttributes
  scriptUrl: string
  season?: number | null
  episode?: number | null
  unavailableText: string
}) => {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'no-data' | 'script-error'>('loading')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    let cancelled = false
    const element = document.createElement(PLAYER_ELEMENT)
    for (const [name, value] of Object.entries(attributes)) {
      if (value !== undefined) element.setAttribute(name, value)
    }

    const onNoData = () => setState('no-data')
    element.addEventListener('noData', onNoData)
    host.replaceChildren(element)

    // Скрипт провайдера подключается один раз: повторная вставка тега при retry
    // создала бы второе определение custom element и сломала уже живые плееры.
    const selector = `script[data-player-script="${scriptUrl}"]`
    let script = document.querySelector<HTMLScriptElement>(selector)
    const onError = () => {
      if (!cancelled) setState('script-error')
    }
    if (!script) {
      script = document.createElement('script')
      script.src = scriptUrl
      script.async = true
      script.dataset.playerScript = scriptUrl
      script.addEventListener('error', onError)
      document.head.appendChild(script)
    } else if (script.dataset.playerFailed === 'true') {
      onError()
    }

    // Готовность определяется по контракту: элемент считается рабочим, когда
    // браузер его определил, а не через таймер «наверное, уже загрузился».
    customElements
      .whenDefined(PLAYER_ELEMENT)
      .then(() => {
        if (!cancelled) setState((current) => (current === 'loading' ? 'ready' : current))
      })
      .catch(onError)

    return () => {
      cancelled = true
      element.removeEventListener('noData', onNoData)
      script?.removeEventListener('error', onError)
      element.remove()
    }
  }, [attributes, scriptUrl, attempt])

  useEffect(() => {
    if (state !== 'ready') return
    const element = hostRef.current?.querySelector(PLAYER_ELEMENT) as
      | (HTMLElement & { selectSeason?: (n: number) => void; selectEpisode?: (n: number) => void })
      | null
    if (!element) return
    // Вызываются только методы контракта и только если плеер их предоставил.
    if (typeof season === 'number' && typeof element.selectSeason === 'function') element.selectSeason(season)
    if (typeof episode === 'number' && typeof element.selectEpisode === 'function') element.selectEpisode(episode)
  }, [season, episode, state, attempt])

  const retry = useCallback(() => {
    setState('loading')
    // Смена ключа попытки заставляет эффект пересоздать элемент и повторить загрузку.
    setAttempt((value) => value + 1)
  }, [])

  if (state === 'no-data' || state === 'script-error') {
    return (
      <div className="player-frame player-frame--message">
        <p className="notice" role="status" data-testid="player-status">
          {state === 'no-data' ? unavailableText : 'Плеер не загрузился. Проверьте соединение и попробуйте ещё раз.'}
        </p>
        <button className="button" type="button" onClick={retry} data-testid="player-retry">
          Повторить
        </button>
      </div>
    )
  }

  return <div className="player-frame" ref={hostRef} data-testid="player-host" key={attempt} />
}
