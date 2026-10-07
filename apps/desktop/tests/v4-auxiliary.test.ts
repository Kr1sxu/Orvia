import {describe,it,expect} from 'vitest';
import {auxiliaryConfig,auxiliaryStatus} from '../src/main/auxiliary-contracts';
import {credentialInputSchema} from '../src/main/contracts';

describe('V4-001 辅助接口限制',()=>{
  const config={enabled:true,host:'127.0.0.1',port:16379,db:0};
  it('只允许回环字面量、明确端口和有限库号',()=>{
    expect(auxiliaryConfig.parse(config)).toEqual(config);
    for(const patch of [{host:'localhost'},{host:'192.168.1.1'},{host:'https://127.0.0.1'},{host:'127.1'},{port:0},{port:'6379'},{db:16},{enabled:1},{password:'synthetic'},{command:'FLUSHALL'}])expect(auxiliaryConfig.safeParse({...config,...patch}).success).toBe(false);
  });
  it('状态不能携带正文、权限或凭据，计数不能冒充事实',()=>{
    const status={...config,state:'degraded',reason:'unavailable',password_configured:false,cache_hits:0,cache_misses:0,notifications_published:0,notifications_processed:0,notifications_discarded:0,metadata_count:0,local_notifications_processed:0,recent_tasks:[]};
    expect(auxiliaryStatus.parse(status)).toEqual(status);
    for(const patch of [{reason:'synthetic exception secret'},{state:'completed'},{text:'private'},{password:'synthetic'},{cache_hits:-1}])expect(auxiliaryStatus.safeParse({...status,...patch}).success).toBe(false);
    expect(credentialInputSchema.parse({role:'redis',key:'synthetic-redis'}).role).toBe('redis');
  });
});
