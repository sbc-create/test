/** Минимальный прогон проверок: без внешнего раннера, но с честным exit code. */
export type Result = { name: string; ok: boolean; detail?: string }

const results: Result[] = []

export const check = async (name: string, fn: () => Promise<void> | void): Promise<void> => {
  try {
    await fn()
    results.push({ name, ok: true })
    console.log(`PASS  ${name}`)
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    results.push({ name, ok: false, detail })
    console.log(`FAIL  ${name}\n      ${detail}`)
  }
}

export const assert = (condition: unknown, message: string): void => {
  if (!condition) throw new Error(message)
}

export const assertEqual = (actual: unknown, expected: unknown, message: string): void => {
  if (actual !== expected) throw new Error(`${message}: получено ${String(actual)}, ожидалось ${String(expected)}`)
}

/** Проверка, что операция действительно ЗАПРЕЩЕНА, а не «тихо ничего не сделала». */
export const assertRejects = async (fn: () => Promise<unknown>, message: string): Promise<void> => {
  let value: unknown
  try {
    value = await fn()
  } catch {
    return
  }
  throw new Error(`${message}: операция завершилась успешно и вернула ${JSON.stringify(value)?.slice(0, 200)}`)
}

export const summary = (): number => {
  const failed = results.filter((result) => !result.ok)
  console.log(`\n${results.length - failed.length}/${results.length} проверок пройдено`)
  if (failed.length > 0) {
    console.log('Провалено:')
    for (const item of failed) console.log(`  - ${item.name}: ${item.detail}`)
  }
  return failed.length === 0 ? 0 : 1
}
