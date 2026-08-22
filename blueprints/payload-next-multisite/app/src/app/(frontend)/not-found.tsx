import Link from 'next/link'

/** 404 отдаётся именно со статусом 404: страница «ничего не найдено» со статусом 200 — soft 404. */
const NotFound = () => (
  <>
    <h1>Страница не найдена</h1>
    <p style={{ maxWidth: '70ch' }}>
      Такого адреса на сайте нет. Возможно, материал удалён или адрес набран с ошибкой.
    </p>
    <nav className="row">
      <Link className="button" href="/">
        На главную
      </Link>
      <Link className="button button--ghost" href="/catalog/">
        В каталог
      </Link>
    </nav>
  </>
)

export default NotFound
