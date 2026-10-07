"""V4-011 程序证据封印；只读已有事实，不访问用户文件或恢复执行授权。"""
import hashlib
import json

from ..computer.paths import ToolError


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def require(condition):
    if not condition:raise ToolError('STEP_NOT_VERIFIED','当前目标缺少准确且仍有效的程序证据；不能标为完成')


async def rows(db,sql,args=()):
    async with db.execute(sql,args) as cursor:return await cursor.fetchall()


async def source(db,cid,kind,eid):
    """全文版本与有效关联均核验，历史原文或索引存在不能重新授予资料使用权。"""
    require(kind in {'browser','document'})
    require(not await rows(db,'SELECT 1 FROM m20_removed_sources WHERE conversation_id=? AND kind=? AND evidence_id=?',(cid,kind,eid)))
    require(await rows(db,"SELECT 1 FROM m20_materials WHERE conversation_id=? AND kind=? AND evidence_id=? AND status='ready'",(cid,kind,eid)))
    table={'browser':'browser_evidence','document':'document_evidence'}[kind]
    values=await rows(db,f'SELECT evidence_json FROM {table} WHERE mission_id=? AND id=?',(cid,eid))
    require(values)
    value=json.loads(values[0][0]);require(not value.get('error'))
    require(value.get('evidence_id')==eid)
    if kind=='browser':require(hashlib.sha256(value.get('content','').encode()).hexdigest()==value.get('content_hash'))
    return digest(value)


async def snapshot(db,row,index,item,context=None):
    """每个已完成目标绑定具体结果与本目标规范；退出0/模型自述不构成动作完成。"""
    cid,rid=row['conversation_id'],row['request_id'];steps=json.loads(row['plan_json'])['steps'];step=steps[index]
    kind=step['kind'];ref=item.get('result_id');require(ref)
    result={'step':digest(step),'result_id':ref,'kind':kind,'facts':{}}
    context=context or {};result['context']=context
    if kind in {'desktop','browser'} and item['status']!='accepted':
        await automation(db,cid,kind,item,context,result)
        return result
    messages=await rows(db,"SELECT sequence,message_json FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.id')=?",(cid,ref))
    require(messages);sequence,body=messages[0];message=json.loads(body);data=message.get('data') or {}
    require(sequence>item.get('baseline',0));result['facts']['message']=digest(message)
    if item['status']=='accepted':
        require(message['kind']=='task_acceptance' and message['role']=='user' and data.get('request_id')==rid and data.get('position')==index and data.get('step_revision')==digest(step) and data.get('continuation_id')==context.get('continuation_id') and bool(data.get('continuation_id')))
        return result
    if kind in {'list','search','space'}:
        require(message['kind']=='directory_result')
        records=await rows(db,'SELECT request_id,operation,state,summary_json FROM m20_scans WHERE conversation_id=? AND id=?',(cid,data.get('scan_id')))
        require(records);record=records[0];summary=json.loads(record[3])
        require(record[0]==rid and record[1]==kind and record[2]=='completed' and summary.get('complete') is True and not summary.get('truncated') and not summary.get('errors') and summary.get('scope')==step['path'] and summary.get('depth')==step['depth'])
        require(data.get('task_step_revision')==digest(step) and data.get('task_step_index')==index)
        result['facts']['scan']=digest(list(record))
    elif kind in {'answer','task_summary'}:
        require(message['kind']==('task_summary' if kind=='task_summary' else 'natural_answer') and message['role']=='assistant' and message['text'].strip() and data.get('request_id')==rid)
        require(data.get('task_step_revision')==digest(step) and data.get('task_step_index')==index)
    elif kind in {'read_url','web_search','material_quote'}:
        require(message['kind'] in {'source','document'} and not data.get('error'))
        expected={'read_url':'read','web_search':'search','material_quote':'ask'}[kind];require(data.get('operation')==expected)
        if kind!='material_quote':
            request=await rows(db,'SELECT text,status FROM chat_requests WHERE conversation_id=? AND request_id=?',(cid,data.get('request_id')))
            require(request and request[0][1]=='completed')
            text=request[0][0];prefix='chat.browser.read' if kind=='read_url' else 'chat.browser.search'
            require(text.startswith(prefix));args=json.loads(text[len(prefix):]);require(args.get('url' if kind=='read_url' else 'query')==step['url' if kind=='read_url' else 'query'])
            result['facts']['request']=digest(list(request[0]))
        else:require(data.get('task_step_revision')==digest(step) and data.get('task_step_index')==index)
        for entry in data.get('items',[]):
            eid=entry.get('evidence_id');origin='document' if message['kind']=='document' else 'browser'
            result['facts'][origin+':'+eid]=await source(db,cid,origin,eid)
            if kind=='read_url':
                full=await rows(db,'SELECT evidence_json FROM browser_evidence WHERE mission_id=? AND id=?',(cid,eid))
                value=json.loads(full[0][0]);require(not value.get('truncated') and bool(value.get('content','').strip()))
            if kind=='material_quote':
                table={'browser':'browser_evidence','document':'document_evidence'}[origin]
                full=await rows(db,f'SELECT evidence_json FROM {table} WHERE mission_id=? AND id=?',(cid,eid));value=json.loads(full[0][0])
                if origin=='browser':require(entry.get('content','').strip() and entry['content'] in value.get('content',''))
                else:
                    require(entry.get('units'))
                    for unit in entry['units']:require(unit.get('text','').strip() and any(u['number']==unit['number'] and unit['text'] in u['text'] for u in value.get('units',[])))
        require(kind=='web_search' or bool(data.get('items')))
    elif kind=='material_answer':
        require(message['kind']=='synthesis' and data.get('revision')==context.get('input',{}).get('revision'))
        expected={(s['kind'],s['evidence_id']) for s in context['input']['sources']}
        require({(s['kind'],s['evidence_id']) for s in data.get('coverage',[])}==expected)
        require(not any(s.get('source_truncated') or s.get('missing_units') for s in data['coverage']))
        for origin,eid in expected:result['facts'][origin+':'+eid]=await source(db,cid,origin,eid)
        require(bool(data.get('claims')) and bool(data.get('citations')))
    elif kind=='publication':
        require(message['kind']=='publication' and data.get('message_id')==context.get('input',{}).get('message_id') and data.get('format')==step['format'])
        originals=await rows(db,"SELECT message_json FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.id')=? AND json_extract(message_json,'$.kind')='synthesis'",(cid,data['message_id']))
        require(originals)
        from ..publication.service import _digest,prepare_publication
        from types import SimpleNamespace
        original=json.loads(originals[0][0]);require(_digest(original['data'])==data.get('source_revision'))
        prepared=prepare_publication(original,SimpleNamespace(**context['input']))
        require(prepared['revision']==data.get('revision') and data.get('pages')==len(prepared['pages']))
        saved_request=await rows(db,'SELECT status FROM chat_requests WHERE conversation_id=? AND request_id=?',(cid,data.get('request_id')))
        require(saved_request and saved_request[0][0]=='completed')
        for entry in original['data'].get('coverage',[]):result['facts'][entry['kind']+':'+entry['evidence_id']]=await source(db,cid,entry['kind'],entry['evidence_id'])
        result['facts']['answer']=digest(original)
    elif kind=='files':
        require(message['kind']=='result' and data.get('success') is True and data.get('verify',{}).get('complete') is True and data.get('operation_id')==context.get('input',{}).get('operation_id'))
        records=await rows(db,'SELECT mission_id,status,plan_json FROM operation_tasks WHERE id=?',(data['operation_id'],));require(records and records[0][0]==cid and records[0][1]=='completed')
        plan=json.loads(records[0][2]);require(plan.get('revision')==context['input'].get('revision'))
        entries=await rows(db,'SELECT sequence,status,after_json FROM operation_entries WHERE task_id=? ORDER BY sequence',(data['operation_id'],));require(entries and all(e[1]=='completed' and e[2] for e in entries))
        checks=data['verify'].get('checks',[])
        require(len(checks)==len(entries) and sorted(c.get('sequence',-1) for c in checks)==[e[0] for e in entries] and all(e.get('destination_exists') is True and e.get('source_absent') is True for e in checks))
        result['facts']['operation']=digest([list(records[0]),[list(e) for e in entries]])
    elif kind=='cleanup':
        require(message['kind']=='cleanup' and data.get('plan_id')==context.get('input',{}).get('plan_id'))
        records=await rows(db,'SELECT status,plan_json FROM m17_cleanup WHERE conversation_id=? AND id=?',(cid,data['plan_id']));require(records and records[0][0]=='completed')
        plan=json.loads(records[0][1]);require(plan.get('revision')==context['input'].get('revision') and plan.get('entries') and all(e['status']=='moved' and e.get('quarantine_identity',{}).get('sha256')==e['identity']['sha256'] for e in plan['entries']))
        result['facts']['cleanup']=digest(list(records[0]))
    else:require(False)  # script退出0、未保存原需求准确绑定的development均只能明确接受有限事实。
    return result


async def automation(db,cid,kind,item,context,result):
    """复核准确操作和原生外发回执；一条成功摘要不能代替多个必要效果。"""
    rule=context.get('input',{}).get('success_rule',{});ids=context.get('operation_ids',[])
    require(ids and len(ids)<=100)
    operations=[]
    for oid in sorted(set(ids)):
        records=await rows(db,'SELECT kind,status,audit_json,revision,created_at,updated_at FROM m18_operations WHERE conversation_id=? AND id=?',(cid,oid));require(records)
        record=records[0];audit=json.loads(record[2]);evidence=audit.get('evidence',{})
        require(record[0]==kind and record[1] in {'verified','completed'} and evidence.get('verified') is True and record[4]>=rule.get('created_after','~'))
        if kind=='desktop':
            require(audit.get('category')=='local' and audit.get('action')==rule.get('action') and evidence.get('verification')==('ui_state_changed' if rule['action']=='invoke' else 'control_state'))
            if rule.get('value_sha256'):require(audit.get('value_sha256')==rule['value_sha256'])
            if rule.get('target_name'):require(audit.get('target_name')==rule['target_name'])
        else:require(audit.get('origin')==rule.get('origin'))
        result['facts']['operation:'+oid]=digest(list(record));operations.append((record,audit,evidence))
    if kind=='desktop':return
    for action in rule.get('control_actions',[]):require(any(a.get('action')==action and e.get('action')==action and e.get('control_matched') is True for _,a,e in operations))
    approvals=await rows(db,"SELECT message_json FROM chat_messages WHERE conversation_id=? AND sequence>? AND json_extract(message_json,'$.kind')='automation' AND json_extract(message_json,'$.data.kind')='browser-request' LIMIT 100",(cid,context.get('baseline',0)))
    for category in rule.get('categories',[]):
        matched=False
        for record,audit,evidence in operations:
            if audit.get('category')!=category or evidence.get('matched') is not True or type(evidence.get('http_status')) is not int or not 200<=evidence['http_status']<300:continue
            import re
            if not all(re.fullmatch('[0-9a-f]{64}',str(evidence.get(key,''))) for key in ('request_sha256','response_sha256','expected_sha256','page_sha256')):continue
            for body, in approvals:
                approval=json.loads(body);meta=approval['data'].get('request_meta',{})
                if approval['data'].get('approved') is True and record[4]<=approval['created_at']<=record[5] and meta.get('origin')==rule['origin'] and meta.get('category')==category and meta.get('body_sha256')==evidence['request_sha256']:
                    result['facts']['approval:'+approval['id']]=digest(approval);matched=True
        require(matched)
