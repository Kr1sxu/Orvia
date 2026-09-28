/** 仅主窗口顶层 frame 的精确本地页面可以调用健康检查。 */
export function mayCheckHealth(isMainWindow: boolean, isTopFrame: boolean, senderUrl: string, expectedUrl: string, args: unknown[]): boolean {
  return isMainWindow && isTopFrame && senderUrl === expectedUrl && args.length === 0;
}
