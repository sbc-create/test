/**
 * Структурированные данные. `<` экранируется: иначе строка внутри JSON может
 * закрыть тег script и превратиться в разметку страницы.
 */
export const JsonLd = ({ data }: { data: unknown }) => (
  <script
    type="application/ld+json"
    dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }}
  />
)
