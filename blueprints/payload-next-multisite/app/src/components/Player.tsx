'use client'

import { useEffect, useRef, useState } from 'react'

import { PLAYER_ELEMENT, type PlayerAttributes } from '../player/contract'

/**
 * Прямое встраивание <video-player> — без iframe и без обёрток чужого сайта.
 *
 * Скрипт подключается один раз на страницу. Событие noData из контракта
 * переводит блок в состояние «серия недоступна»: подменять недоступное видео
 * другим запрещено, поэтому вместо плеера показывается честный статус.
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
  const [unavailable, setUnavailable] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const element = document.createElement(PLAYER_ELEMENT)
    for (const [name, value] of Object.entries(attributes)) {
      if (value !== undefined) element.setAttribute(name, value)
    }

    const onNoData = () => setUnavailable(true)
    element.addEventListener('noData', onNoData)
    host.appendChild(element)

    const existing = document.querySelector<HTMLScriptElement>(`script[data-player-script="${scriptUrl}"]`)
    let script = existing
    if (!script) {
      script = document.createElement('script')
      script.src = scriptUrl
      script.async = true
      script.dataset.playerScript = scriptUrl
      script.addEventListener('error', () => setFailed(true))
      document.head.appendChild(script)
    }

    return () => {
      element.removeEventListener('noData', onNoData)
      element.remove()
    }
  }, [attributes, scriptUrl])

  useEffect(() => {
    const element = hostRef.current?.querySelector(PLAYER_ELEMENT) as
      | (HTMLElement & { selectSeason?: (n: number) => void; selectEpisode?: (n: number) => void })
      | null
    if (!element) return
    // Методы вызываются только те, что есть в контракте, и только если плеер их предоставил.
    if (typeof season === 'number' && typeof element.selectSeason === 'function') element.selectSeason(season)
    if (typeof episode === 'number' && typeof element.selectEpisode === 'function') element.selectEpisode(episode)
  }, [season, episode])

  if (unavailable || failed) {
    return (
      <div className="notice" role="status">
        {unavailableText}
      </div>
    )
  }

  return <div className="player-frame" ref={hostRef} data-testid="player-host" />
}
