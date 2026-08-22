'use client'

import { useState } from 'react'

/**
 * Форма комментария. Отправка идёт на серверный endpoint: клиент не может
 * ни опубликовать комментарий напрямую, ни обойти премодерацию.
 */
export const CommentForm = ({
  targetType,
  targetId,
  targetUrl,
  formToken,
  allowGuests,
  rulesText,
  maxLength,
}: {
  targetType: string
  targetId: string
  targetUrl: string
  formToken: string
  allowGuests: boolean
  rulesText: string
  maxLength: number
}) => {
  const [state, setState] = useState<{ kind: 'idle' | 'sending' | 'done' | 'error'; message?: string }>({
    kind: 'idle',
  })

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setState({ kind: 'sending' })

    const response = await fetch('/api/comments/submit', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        targetType,
        targetId,
        targetUrl,
        formToken,
        body: data.get('body'),
        guestName: data.get('guestName'),
        guestEmail: data.get('guestEmail'),
        website: data.get('website'),
        parent: data.get('parent') || undefined,
      }),
    })
    const payload = (await response.json().catch(() => ({}))) as { message?: string; error?: string }

    if (response.ok) {
      form.reset()
      setState({ kind: 'done', message: payload.message ?? 'Комментарий отправлен.' })
    } else {
      setState({ kind: 'error', message: payload.error ?? 'Не удалось отправить комментарий.' })
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: 'grid', gap: '0.75rem', maxWidth: '70ch' }}>
      {allowGuests ? (
        <>
          <label>
            Имя
            <input name="guestName" required minLength={2} maxLength={60} style={{ width: '100%', minHeight: 44 }} />
          </label>
          <label>
            E-mail (не публикуется, необязательно)
            <input name="guestEmail" type="email" style={{ width: '100%', minHeight: 44 }} />
          </label>
        </>
      ) : null}

      {/* Поле-ловушка: скрыто от человека и от программы чтения с экрана. */}
      <div aria-hidden="true" style={{ position: 'absolute', left: '-9999px' }}>
        <label>
          Не заполняйте это поле
          <input name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>

      <label>
        Комментарий
        <textarea name="body" required minLength={2} maxLength={maxLength} rows={5} style={{ width: '100%' }} />
      </label>

      <p className="card__meta">{rulesText}</p>

      <div>
        <button className="button" type="submit" disabled={state.kind === 'sending'}>
          {state.kind === 'sending' ? 'Отправляем…' : 'Отправить'}
        </button>
      </div>

      {state.message ? (
        <p className="notice" role="status">
          {state.message}
        </p>
      ) : null}
    </form>
  )
}
