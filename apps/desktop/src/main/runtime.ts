import path from 'node:path';

export interface PackagedRuntime { resourcesPath: string }

/** 发布路径只由 Electron 主进程传入；不读取 PATH、renderer 参数或解释器覆盖环境变量。 */
export function backendLaunch(root: string, packaged?: PackagedRuntime) {
  const env: NodeJS.ProcessEnv = {};
  for (const key of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP']) if (process.env[key]) env[key] = process.env[key];
  if (packaged) {
    if (!path.isAbsolute(packaged.resourcesPath)) throw new Error('安装资源路径必须是绝对路径');
    const directory = path.join(packaged.resourcesPath, 'backend');
    env.PLAYWRIGHT_BROWSERS_PATH = path.join(packaged.resourcesPath, 'chromium');
    env.PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1';
    return { executable: path.join(directory, 'orvia-backend.exe'), args: [] as string[], cwd: directory, env };
  }
  return { executable: path.join(root, 'backend', '.venv', 'Scripts', 'python.exe'),
    args: ['-I', '-u', '-X', 'utf8', '-m', 'orvia_backend'], cwd: path.join(root, 'backend'), env };
}
