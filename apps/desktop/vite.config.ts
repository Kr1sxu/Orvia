import { defineConfig } from 'vite';

// 品牌资源保持本地独立文件；不为Vite自动内联data URI而放宽现有img-src 'self' CSP。
export default defineConfig({ base: './', build: { outDir: 'dist/renderer', emptyOutDir: true, assetsInlineLimit: 0 } });
