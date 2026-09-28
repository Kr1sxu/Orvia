/** 仅主窗口顶层 frame 的精确本地页面可以调用健康检查。 */
export function mayCheckHealth(isMainWindow: boolean, isTopFrame: boolean, senderUrl: string, expectedUrl: string, args: unknown[]): boolean {
  return isMainWindow && isTopFrame && senderUrl === expectedUrl && args.length === 0;
}

/** 不同业务能力固定参数个数；参数内容再由主进程各入口的 schema 校验。 */
export function mayInvoke(isMainWindow: boolean, isTopFrame: boolean, senderUrl: string, expectedUrl: string, args: unknown[], count: number): boolean {
  return isMainWindow && isTopFrame && senderUrl === expectedUrl && args.length === count;
}
