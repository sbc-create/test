/*
 * Локальная заглушка плеера для стенда.
 *
 * Она НЕ повторяет и не эмулирует реализацию провайдера: реализует ровно то, что
 * описано контрактом — пользовательский элемент <video-player>, методы
 * selectSeason/selectEpisode и событие noData. Нужна для прогонов без сети;
 * в production подключение заглушки запрещено технически.
 */
;(function () {
  if (window.customElements && window.customElements.get('video-player')) return

  class MockVideoPlayer extends HTMLElement {
    connectedCallback() {
      this.style.display = 'flex'
      this.style.alignItems = 'center'
      this.style.justifyContent = 'center'
      this.style.width = '100%'
      this.style.height = '100%'
      this.style.color = '#fff'
      this.style.background = '#111'
      this.style.font = '14px/1.4 sans-serif'
      this.textContent = 'Заглушка плеера (стенд). Идентификатор: ' + (this.getAttribute('ident') || '—')

      if (this.getAttribute('data-title-id') === 'unavailable') {
        this.dispatchEvent(new CustomEvent('noData'))
      }
    }

    selectSeason(number) {
      this.setAttribute('season', String(number))
    }

    selectEpisode(number) {
      this.setAttribute('episode', String(number))
    }
  }

  window.customElements.define('video-player', MockVideoPlayer)
})()
