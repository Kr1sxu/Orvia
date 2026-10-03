// 固定Main真实测试使用产品后端与Vault；只有主进程启动路径，不替换模型或网络。
const path=require('node:path');
require(path.resolve(__dirname,'../../apps/desktop/dist/main/main.js'));
