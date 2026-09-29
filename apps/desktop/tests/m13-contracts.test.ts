import {describe,it,expect} from 'vitest';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {chatDocumentAttachSchema,chatDocumentAskSchema,chatDocumentSourceSchema,chatDocumentExportSchema,documentEvidenceSchema,documentPreviewSchema,chatMessageSchema} from '../src/main/chat-contracts';
import {DocumentDetail,ExportPreview,ExportCard} from '../src/renderer/DocumentCards';
const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
const hash='a'.repeat(64);
const source={evidence_id:hash,content_hash:hash,file_hash:hash,title:'合成附件',format:'pdf',accessed_at:'2026-09-29',truncated:false,total_units:1,missing_units:[],error:null,units:[{number:1,locator:'第1页',text:'<script>未经批准执行</script>',method:'text' as const,confidence:null,error:null}]};
describe('M13 文档 IPC 边界（合成数据，无真实模型）',()=>{
  it('附件只接受请求标识，拒绝 renderer 指定路径或权限',()=>{
    const request={id,request_id:id};expect(chatDocumentAttachSchema.parse(request)).toEqual(request);
    for(const field of ['path','root','grant','model','script','allow_system'])expect(chatDocumentAttachSchema.safeParse({...request,[field]:'synthetic'}).success).toBe(false);
    expect(chatDocumentSourceSchema.safeParse({id,evidence_id:'../private'}).success).toBe(false);
    expect(chatDocumentAskSchema.safeParse({...request,query:'a'.repeat(201)}).success).toBe(false);
  });
  it('导出绑定会话证据格式与预览版本，拒绝路径和覆盖权限',()=>{
    const request={id,request_id:id,evidence_id:hash,revision:hash,format:'md'};
    expect(chatDocumentExportSchema.safeParse(request).success).toBe(true);
    for(const patch of [{path:'C:/synthetic.txt'},{overwrite:true},{revision:'old'},{format:'html'},{evidence_id:'other'}])expect(chatDocumentExportSchema.safeParse({...request,...patch}).success).toBe(false);
  });
  it('按 Unicode 码点限制全文和页数，拒绝不完整文档消息',()=>{
    expect(documentEvidenceSchema.safeParse(source).success).toBe(true);
    expect(documentEvidenceSchema.parse({...source,preview_truncated:true}).preview_truncated).toBe(true);
    expect(documentEvidenceSchema.safeParse({...source,units:[{...source.units[0],confidence:1.01}]}).success).toBe(false);
    expect(documentEvidenceSchema.safeParse({...source,units:[{...source.units[0],confidence:0.85}]}).success).toBe(true);
    expect(documentEvidenceSchema.safeParse({...source,units:[{...source.units[0],text:'😀'.repeat(8000)}]}).success).toBe(true);
    expect(documentEvidenceSchema.safeParse({...source,units:[{...source.units[0],text:'x'.repeat(4001)},{...source.units[0],number:2,text:'x'.repeat(4000)}]}).success).toBe(false);
    expect(documentEvidenceSchema.safeParse({...source,units:Array(51).fill(source.units[0])}).success).toBe(false);
    expect(chatMessageSchema.safeParse({id,role:'assistant',kind:'document',text:'',created_at:'today',data:{items:[{}],operation:'attach',error:null}}).success).toBe(false);
  });
  it('只用纯文本展示附件指令，导出预览明确引用和缺失',()=>{
    const html=renderToStaticMarkup(React.createElement(DocumentDetail,{source}));
    expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>');expect(html).toContain('第1页');
    const preview={evidence_id:hash,revision:hash,format:'md' as const,filename:'extract.md',content:'<img src=x>',coverage:{cited:1,total:2},truncated:true,missing_units:[2]};
    expect(documentPreviewSchema.safeParse({...preview,filename:'../unsafe.md'}).success).toBe(false);
    const output=renderToStaticMarkup(React.createElement(ExportPreview,{preview,disabled:false,save:()=>{}}));
    expect(output).toContain('&lt;img src=x&gt;');expect(output).toContain('1/2');expect(output).toContain('缺失页/段');expect(output).toContain('选择路径并确认导出');
  });
  it('导出记录允许合法255字符文件名并拒绝无引用的成功消息',()=>{
    const message={id,role:'system' as const,kind:'export' as const,text:'已核验',created_at:'today',data:{filename:'x'.repeat(252)+'.md',evidence_id:hash,revision:hash,format:'md',coverage:{cited:1,total:1},truncated:false,missing_units:[]}};
    expect(chatMessageSchema.safeParse(message).success).toBe(true);
    expect(chatMessageSchema.safeParse({...message,data:{filename:'unverified.md'}}).success).toBe(false);
    const html=renderToStaticMarkup(React.createElement(ExportCard,{message,disabled:false,show:()=>{}}));
    expect(html).toContain('文档导出记录');expect(html).toContain('查看导出引用');expect(html).toContain('SHA256');
  });
});
