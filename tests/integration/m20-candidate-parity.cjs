// 只读两个实际ASAR的业务文件；安装身份/包元数据允许不同，dist字节必须逐个相同。
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),asar=require('@electron/asar');
const root=path.resolve(__dirname,'../..'),result=path.join(root,'artifacts/test-results/M20');
const resources=kind=>path.join(result,kind,'win-unpacked/resources');
const left=resources('release'),right=resources('production-release');
const archive=directory=>path.join(directory,'app.asar');
const files=directory=>asar.listPackage(archive(directory)).map(raw=>raw.replaceAll('\\','/').replace(/^\//,''))
  .filter(name=>name.startsWith('dist/')&&!asar.statFile(archive(directory),path.normalize(name)).files).sort();
const names=files(left);assert(names.length>20);assert.deepEqual(names,files(right));
for(const name of names){
  const bytes=asar.extractFile(archive(left),path.normalize(name));assert(bytes.equals(asar.extractFile(archive(right),path.normalize(name))),name);
  assert(bytes.equals(fs.readFileSync(path.join(root,'apps/desktop',name))),`current build: ${name}`);
}
assert(fs.readFileSync(path.join(left,'runtime-manifest.json')).equals(fs.readFileSync(path.join(right,'runtime-manifest.json'))));
const report={identicalBusinessFiles:names.length,currentBuildVerified:true,runtimeManifestIdentical:true,
  renderer:names.filter(name=>/^dist\/renderer\/assets\/index-.+\.js$/.test(name)),ordinaryIdentityInstalled:false};
fs.writeFileSync(path.join(result,'candidate-business-parity-verified.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
